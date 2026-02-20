import asyncio
import threading
import cv2
import json
import time
import sqlite3
import os
from ultralytics import YOLO

# Import the WS connection registry
from routers.cameras import active_connections

# Define models directory (matching video processing setup)
MODELS_DIR = "data/models"
os.makedirs(MODELS_DIR, exist_ok=True)

loaded_models = {}

def get_yolo_model(model_name: str):
    """
    Load YOLO model synchronously for background thread usage.
    """
    if model_name not in loaded_models:
        print(f"[CameraWorker] Loading model: {model_name}")
        model_path = os.path.join(MODELS_DIR, f"{model_name}.pt")
        try:
             if os.path.exists(model_path):
                 loaded_models[model_name] = YOLO(model_path)
             else:
                 print(f"[CameraWorker] Model {model_name} not found locally, downloading...")
                 # YOLO downloads to CWD, move it to models dir
                 temp_model = YOLO(f"{model_name}.pt") 
                 if os.path.exists(f"{model_name}.pt"):
                     os.rename(f"{model_name}.pt", model_path)
                     loaded_models[model_name] = YOLO(model_path)
                 else:
                     loaded_models[model_name] = temp_model
        except Exception as e:
            print(f"[CameraWorker] Error loading {model_name}, falling back to yolov8n. Error: {e}")
            loaded_models[model_name] = YOLO("yolov8n.pt")
            
    return loaded_models[model_name]

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

class CameraWorker:
    def __init__(self, camera_id: str, loop: asyncio.AbstractEventLoop, db_path: str = "locusvision.db"):
        self.camera_id = camera_id
        self.loop = loop
        self.db_path = db_path
        self.is_running = False
        self.thread = None

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            print(f"[{self.camera_id}] Started Camera Worker Thread")

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            print(f"[{self.camera_id}] Stopped Camera Worker Thread")

    def _broadcast_to_websockets(self, message: str):
        """
        Thread-safe method to push WebSocket messages into FastAPI's event loop.
        """
        if self.camera_id not in active_connections or not active_connections[self.camera_id]:
            return

        async def send_all():
            disconnected = []
            for ws in active_connections.get(self.camera_id, []):
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)
            
            for ws in disconnected:
                if ws in active_connections.get(self.camera_id, []):
                    active_connections[self.camera_id].remove(ws)

        # Schedule the async broadcast on the main FastAPI event loop
        asyncio.run_coroutine_threadsafe(send_all(), self.loop)

    def _run_loop(self):
        # 1. Fetch camera configuration via synchronous SQLite
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cameras WHERE id = ?", (self.camera_id,))
            camera = cursor.fetchone()
            conn.close()
        except Exception as e:
            print(f"[{self.camera_id}] DB Error: {e}")
            self.is_running = False
            return

        if not camera:
            print(f"[{self.camera_id}] Camera not found in DB.")
            self.is_running = False
            return

        model_name = camera.get("model_name", "yolo11n")
        cam_type = camera.get("type", "webcam")
        url = camera.get("url")
        device_id = camera.get("device_id")

        # 2. Setup OpenCV Video Capture
        source = target_fps = 15
        if cam_type == "webcam":
            # If default webcam
            source = 0
            # If explicit device ID, sometimes OpenCV can't use UUID strings natively, but we'll try 0 as fallback
            # In a real environment, you'd enumerate /dev/videoX identifiers
            if device_id and device_id.isdigit():
                source = int(device_id)
        elif cam_type == "rtsp":
            if not url:
                print(f"[{self.camera_id}] Missing RTSP URL.")
                self.is_running = False
                return
            source = url

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"[{self.camera_id}] Failed to open OpenCV stream on {source}.")
            self.is_running = False
            return
            
        # Optional: Optimize resolution if local webcam
        if cam_type == "webcam":
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # 3. Load YOLO in thread
        model = get_yolo_model(model_name)
        print(f"[{self.camera_id}] Engine Ready. Starting Inference Loop.")

        frame_time = 1.0 / target_fps

        while self.is_running and cap.isOpened():
            loop_start = time.time()
            
            ret, frame = cap.read()
            if not ret:
                print(f"[{self.camera_id}] Stream disconnected. Attempting reconnect...")
                time.sleep(2)
                cap = cv2.VideoCapture(source)
                continue

            # Only run inference if there's someone actually watching the stream!
            # This saves massive CPU overhead when the dashboard is closed.
            if self.camera_id in active_connections and len(active_connections[self.camera_id]) > 0:
                
                # YOLO tracking (persist=True enables ByteTrack ID assignments)
                results = model.track(frame, persist=True, verbose=False)
                
                boxes_data = []
                if results and len(results) > 0 and results[0].boxes:
                    boxes = results[0].boxes.xywh.cpu().numpy()
                    class_indices = results[0].boxes.cls.cpu().numpy()
                    track_ids = results[0].boxes.id
                    
                    if track_ids is not None:
                        track_ids = track_ids.int().cpu().tolist()
                        for box, track_id, cls_idx in zip(boxes, track_ids, class_indices):
                            # YOLO xywh format: center X, center Y, width, height
                            cx, cy, w, h = box
                            boxes_data.append({
                                "id": int(track_id),
                                "x": float(cx - w/2), # Convert center to top-left for frontend canvas
                                "y": float(cy - h/2),
                                "w": float(w),
                                "h": float(h),
                                "class": int(cls_idx),
                                "cx": float(cx),      # Provide pure center for zone intersection math
                                "cy": float(cy),
                            })
                
                # Prepare resolution scaling metadata for the frontend
                # So the frontend canvas can perfectly map the boxes over the CSS-scaled video element
                video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                payload = json.dumps({
                    "event": "analytics",
                    "resolution": {"w": video_w, "h": video_h},
                    "boxes": boxes_data
                })
                
                # Fire and forget WS broadcast
                self._broadcast_to_websockets(payload)

            # Cap frame rate to target_fps to prevent 100% CPU lock
            elapsed = time.time() - loop_start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()
        print(f"[{self.camera_id}] Engine Offline.")

class CameraWorkerManager:
    """
    Singleton manager to keep track of active background workers.
    """
    def __init__(self):
        self.workers: Dict[str, CameraWorker] = {}
        self.loop = None

    def initialize(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def spawn_worker(self, camera_id: str):
        if camera_id in self.workers:
            # Already running, could restart if needed
            self.workers[camera_id].stop()
            
        worker = CameraWorker(camera_id, self.loop)
        self.workers[camera_id] = worker
        worker.start()

    def kill_worker(self, camera_id: str):
        if camera_id in self.workers:
            self.workers[camera_id].stop()
            del self.workers[camera_id]
            
    def shutdown_all(self):
        for worker in self.workers.values():
            worker.stop()
        self.workers.clear()

# Global Singleton
camera_manager = CameraWorkerManager()
