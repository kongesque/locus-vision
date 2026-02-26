"""
Camera analytics worker.

Two modes:
1. RTSP mode  – A background thread pulls frames via OpenCV and broadcasts YOLO results.
2. Webcam mode – The browser sends JPEG frames over the WebSocket and we process them inline.

Both modes now use the shared AnalyticsEngine for zone-aware counting.
"""
import asyncio
import cv2
import json
import time
import sqlite3
import os
import multiprocessing
import ctypes
import numpy as np
from services.analytics_engine import AnalyticsEngine

from routers.cameras import active_connections
from config import settings

MODELS_DIR = "data/models"
os.makedirs(MODELS_DIR, exist_ok=True)

# Per-camera analytics engine instances (keyed by camera_id)
_camera_engines: dict[str, AnalyticsEngine] = {}


def get_camera_engine(camera_id: str, model_name: str = "yolo11n", zones: list = None, full_frame_classes: list = None) -> AnalyticsEngine:
    """Get or create an AnalyticsEngine for a specific camera."""
    if camera_id not in _camera_engines:
        _camera_engines[camera_id] = AnalyticsEngine(
            model_name=model_name,
            zones=zones,
            full_frame_classes=full_frame_classes,
        )
    else:
        # Dynamically update the config on the existing engine so it respects live database
        # changes without losing global counts/track history.
        engine = _camera_engines[camera_id]
        if zones is not None:
            engine.set_zones(zones)
        if full_frame_classes is not None:
            engine.full_frame_class_ids = engine._get_class_ids(full_frame_classes)
            
    return _camera_engines[camera_id]


def update_camera_engine(camera_id: str, zones: list = None, full_frame_classes: list = None):
    """Update zones or tracking filters on an existing camera engine."""
    get_camera_engine(camera_id, zones=zones, full_frame_classes=full_frame_classes)


# ── Webcam "inline" processor (runs per-frame, called from the WS handler) ──

def process_frame_bytes(jpeg_bytes: bytes, camera_id: str, model_name: str = "yolo11n", zones: list = None) -> dict:
    """
    Decode a JPEG frame, run YOLO tracking with zone-aware counting,
    return a dict ready to be sent as JSON via WebSocket.
    """
    engine = get_camera_engine(camera_id, model_name, zones)

    # Decode JPEG → OpenCV BGR
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return {"event": "error", "message": "Bad frame"}

    result = engine.process_frame(frame)

    return {
        "event": "analytics",
        "resolution": result.resolution,
        "boxes": result.boxes,
        "count": result.total_count,
        "zone_counts": result.zone_counts,
    }


# ── RTSP Multiprocessing Worker ──────────────────────────────

def _dict_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def camera_process_run(
    camera_id: str,
    db_path: str,
    event_queue: multiprocessing.Queue,
    frame_array: multiprocessing.Array,
    frame_size_value: multiprocessing.Value
):
    """
    The entrypoint for the isolated child process.
    Connects to the stream, runs YOLO+Motion Detection via the AnalyticsEngine,
    and pushes results back to the FastAPI parent via IPC Queues/Shared Memory.
    """
    # 1. Fetch config from DB
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = _dict_factory
        cam = conn.cursor().execute("SELECT * FROM cameras WHERE id = ?", (camera_id,)).fetchone()
        conn.close()
    except Exception as e:
        print(f"[RTSP-Worker-{camera_id}] DB error: {e}")
        return

    if not cam or not cam.get("url"):
        print(f"[RTSP-Worker-{camera_id}] No URL configured.")
        return

    # Parse zones and classes
    zones = json.loads(cam.get("zones", "[]")) if isinstance(cam.get("zones"), str) else cam.get("zones", [])
    classes_raw = cam.get("classes", "[]")
    full_frame_classes = json.loads(classes_raw) if isinstance(classes_raw, str) else classes_raw
    model_name = cam.get("model_name", "yolo11n")

    # Initialize isolated Analytics Engine
    engine = AnalyticsEngine(model_name, zones, full_frame_classes)

    # 2. Open Stream
    cap = cv2.VideoCapture(cam["url"])
    # Minimize internal OpenCV buffer to prevent lag accumulation
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print(f"[RTSP-Worker-{camera_id}] Cannot open stream: {cam['url']}")
        return

    target_fps = 10
    frame_time = 1.0 / target_fps
    last_process_time = 0

    print(f"[RTSP-Worker-{camera_id}] Starting AI processing loop...")

    try:
        while True:
            # Continuously drain the buffer.
            # cv2.grab() is fast and just pulls the frame off the network stack.
            grabbed = cap.grab()
            if not grabbed:
                time.sleep(0.01)
                continue

            current_time = time.time()
            if current_time - last_process_time >= frame_time:
                last_process_time = current_time
                
                # Actually decode the frame from the buffer
                ret, frame = cap.retrieve()
                if not ret or frame is None:
                    continue

                # Standardize processing resolution
                MAX_WIDTH = 1280
                h, w = frame.shape[:2]
                scale_factor = 1.0
                if w > MAX_WIDTH:
                    scale_factor = MAX_WIDTH / w
                    frame = cv2.resize(frame, (MAX_WIDTH, int(h * scale_factor)), interpolation=cv2.INTER_AREA)

                # Run Analytics (Includes Motion Detection + YOLO)
                result = engine.process_frame(frame, scale=scale_factor)

                # 1. Send JSON Analytics event to parent (for WebSockets)
                payload = json.dumps({
                    "event": "analytics",
                    "count": result.total_count,
                    "zone_counts": result.zone_counts,
                    "boxes": result.boxes,
                    "resolution": result.resolution,
                })
                try:
                    # Put it on the queue without blocking forever
                    event_queue.put_nowait((camera_id, payload))
                except Exception:
                    pass  # Queue full, skip frame

                # 2. Burn annotations and update Shared Memory MJPEG (for live video feed)
                engine.draw_annotations(frame, result)
                # Encode as JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                jpeg_bytes = buffer.tobytes()
                
                size = len(jpeg_bytes)
                # Ensure we do not overflow the shared memory buffer (e.g. 2MB)
                if size <= len(frame_array):
                    with frame_size_value.get_lock():
                        frame_size_value.value = size
                        ctypes.memmove(frame_array.get_obj(), jpeg_bytes, size)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        print(f"[RTSP-Worker-{camera_id}] Stopped.")


class IpCameraWorker:
    """
    Manages the lifecycle of a dedicated multiprocessing.Process for a specific camera.
    """
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.is_running = False
        self._process: multiprocessing.Process | None = None
        
        # IPC Mechanisms
        self.event_queue = multiprocessing.Queue(maxsize=100)
        # Allocate 2MB of shared memory for the current JPEG frame
        self.frame_array = multiprocessing.Array(ctypes.c_byte, 2 * 1024 * 1024)
        self.frame_size = multiprocessing.Value(ctypes.c_int, 0)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._process = multiprocessing.Process(
                target=camera_process_run,
                args=(
                    self.camera_id,
                    settings.database_path,
                    self.event_queue,
                    self.frame_array,
                    self.frame_size
                ),
                daemon=True # Dies if the parent FastAPI process dies
            )
            self._process.start()

    def stop(self):
        self.is_running = False
        if self._process:
            self._process.terminate()
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.kill()
            
    def get_annotated_frame(self) -> bytes | None:
        """Called by the FastAPI generator to stream the latest annotated JPEG."""
        with self.frame_size.get_lock():
            size = self.frame_size.value
            if size == 0:
                return None
            
            # Read bytes from shared memory
            frame_bytes = ctypes.string_at(self.frame_array.get_obj(), size)
            
        return frame_bytes


# ── Manager singleton ───────────────────────────────────────────

class CameraWorkerManager:
    def __init__(self):
        self._workers: dict[str, IpCameraWorker] = {}
        self.loop = None
        self._poll_task = None

    def initialize(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        # Start a background asyncio task in the main FastAPI process 
        # to constantly read from all the child process event queues
        self._poll_task = loop.create_task(self._poll_queues())

    async def _poll_queues(self):
        """Continuously pulls websocket events from all child processes and broadcasts them."""
        while True:
            try:
                # We need to quickly poll each active worker's queue
                # We use asyncio.sleep(0.01) to not block the main event loop
                for worker in list(self._workers.values()):
                    if not worker.is_running:
                        continue
                        
                    try:
                        while not worker.event_queue.empty():
                            cam_id, msg = worker.event_queue.get_nowait()
                            self._broadcast_event(cam_id, msg)
                    except Exception:
                        pass
                
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error polling camera queues: {e}")
                await asyncio.sleep(1)

    def _broadcast_event(self, camera_id: str, msg: str):
        """Sends the JSON analytics payload to all connected frontend WebSockets."""
        conns = active_connections.get(camera_id, [])
        if not conns:
            return
            
        async def _send():
            dead = []
            for ws in conns:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                if ws in conns:
                    conns.remove(ws)
                    
        asyncio.run_coroutine_threadsafe(_send(), self.loop)

    def spawn_worker(self, camera_id: str):
        if camera_id in self._workers:
            self._workers[camera_id].stop()
        w = IpCameraWorker(camera_id)
        self._workers[camera_id] = w
        w.start()

    def kill_worker(self, camera_id: str):
        if camera_id in self._workers:
            self._workers[camera_id].stop()
            del self._workers[camera_id]

    def shutdown_all(self):
        if self._poll_task:
            self._poll_task.cancel()
            
        for w in self._workers.values():
            w.stop()
        self._workers.clear()


camera_manager = CameraWorkerManager()
