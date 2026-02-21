import json
import time
import asyncio
import httpx
from urllib.parse import quote, unquote, urljoin
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse
from typing import List, Dict

from database import get_db
from models import Camera, CameraCreate, CameraUpdate

router = APIRouter(
    prefix="/api/cameras",
    tags=["cameras"],
    responses={404: {"description": "Not found"}},
)

# In-memory registry of active WebSocket connections for camera analytics
# Format: { "camera_id": [WebSocket, ...] }
active_connections: Dict[str, List[WebSocket]] = {}

# Shared HTTP client for HLS proxying (connection pooling)
_http_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

@router.get("/hls-proxy")
async def hls_proxy(request: Request, url: str = Query(..., description="Remote HLS URL to proxy")):
    """
    CORS proxy for HLS manifests and segments.
    Streams video segments to reduce latency and memory usage.
    For .m3u8 manifests, rewrites segment URLs.
    """
    # Forward some harmless headers to avoid being blocked/throttled by CDNs
    fwd_headers = {
        "User-Agent": request.headers.get("user-agent", "Mozilla/5.0"),
        "Accept": "*/*",
        "Accept-Language": request.headers.get("accept-language", "en-US,en;q=0.9"),
        "Origin": "https://www.youtube.com",
    }
    
    try:
        req = _http_client.build_request("GET", url, headers=fwd_headers)
        resp = await _http_client.send(req, stream=True)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Upstream error: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")

    content_type = resp.headers.get("content-type", "application/octet-stream")

    # If this is a manifest, we must read the whole thing to rewrite it.
    if "mpegurl" in content_type.lower() or url.endswith(".m3u8"):
        await resp.aread()
        text = resp.text
        lines = text.splitlines()
        rewritten = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                abs_url = urljoin(url, stripped)
                proxied = f"/api/cameras/hls-proxy?url={quote(abs_url, safe='')}"
                rewritten.append(proxied)
            else:
                rewritten.append(line)
        body = "\n".join(rewritten).encode("utf-8")
        
        return Response(
            content=body,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
            }
        )
    
    # If it's a video segment (.ts, .m4s), stream it directly to the client
    # This prevents the stream from stuttering by lowering Time-To-First-Byte
    async def stream_generator():
        async for chunk in resp.aiter_bytes():
            yield chunk

    return StreamingResponse(
        stream_generator(),
        media_type=content_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
        }
    )


@router.post("/preview")
async def preview_stream(body: dict):
    """
    Grab a single snapshot frame from an RTSP/HTTP stream URL.
    Returns the frame as a base64 JPEG data URI for frontend preview.
    """
    import cv2
    import base64
    import numpy as np

    url = body.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        cap = cv2.VideoCapture(url)
        # Give the stream a moment to connect
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            raise HTTPException(status_code=422, detail="Could not connect to stream")

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            raise HTTPException(status_code=422, detail="Failed to read frame from stream")

        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        b64 = base64.b64encode(buffer).decode('utf-8')

        h, w = frame.shape[:2]
        return JSONResponse({
            "status": "ok",
            "image": f"data:image/jpeg;base64,{b64}",
            "resolution": {"w": w, "h": h}
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.get("/stream/{camera_id}")
async def stream_camera(camera_id: str):
    """
    Optimized MJPEG live stream — Frigate-style threaded frame grabber.

    Key optimizations vs naive MJPEG:
    1. Dedicated reader thread: always grabs the latest frame, discards stale buffer
    2. grab()/retrieve() pattern: drains OpenCV's internal 5-frame buffer
    3. Downscale to 720p max: reduces JPEG encode time + bandwidth
    4. Frame-ready signaling: no busy-waiting or unnecessary CPU
    """
    import cv2
    import threading
    from fastapi.responses import StreamingResponse

    db = await get_db()
    try:
        cursor = await db.execute("SELECT url, type, device_id FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()

    if not row:
        raise HTTPException(status_code=404, detail="Camera not found")

    if row["type"] == "webcam":
        raise HTTPException(status_code=400, detail="Webcam streams use browser getUserMedia")

    url = row["url"]
    if not url:
        raise HTTPException(status_code=422, detail="No stream URL configured")

    # ── Threaded frame grabber (Frigate-style) ──
    # OpenCV's VideoCapture has an internal buffer of ~5 frames.
    # If we read() in the generator, we always get the OLDEST buffered frame = lag.
    # Solution: a background thread continuously drains the buffer, keeping only the latest.

    class FrameGrabber:
        def __init__(self, src):
            self.cap = cv2.VideoCapture(src)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.latest_frame = None
            self.lock = threading.Lock()
            self.running = True
            self.frame_ready = threading.Event()
            self.thread = threading.Thread(target=self._grab_loop, daemon=True)
            self.thread.start()

        def _grab_loop(self):
            """Continuously drain the buffer — only keep the latest frame."""
            while self.running:
                if not self.cap.isOpened():
                    break
                # grab() is faster than read() — it just advances the buffer
                # without decoding. We only retrieve() on the LAST grab.
                grabbed = self.cap.grab()
                if not grabbed:
                    time.sleep(0.01)
                    continue
                ret, frame = self.cap.retrieve()
                if ret and frame is not None:
                    with self.lock:
                        self.latest_frame = frame
                    self.frame_ready.set()

        def get_frame(self):
            """Get the most recent frame (never stale)."""
            self.frame_ready.wait(timeout=2.0)
            with self.lock:
                frame = self.latest_frame
            self.frame_ready.clear()
            return frame

        def stop(self):
            self.running = False
            self.thread.join(timeout=2)
            self.cap.release()

    grabber = FrameGrabber(url)

    if not grabber.cap.isOpened():
        grabber.stop()
        raise HTTPException(status_code=422, detail="Could not connect to stream")

    TARGET_FPS = 24
    frame_interval = 1.0 / TARGET_FPS
    JPEG_QUALITY = 75
    MAX_WIDTH = 1280  # Downscale to 720p max for bandwidth

    def generate_frames():
        try:
            while grabber.running:
                t0 = time.time()
                frame = grabber.get_frame()
                if frame is None:
                    break

                # Downscale if too large
                h, w = frame.shape[:2]
                if w > MAX_WIDTH:
                    scale = MAX_WIDTH / w
                    frame = cv2.resize(frame, (MAX_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)

                _, buffer = cv2.imencode(
                    '.jpg', frame,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
                frame_bytes = buffer.tobytes()

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n"
                    b"\r\n" + frame_bytes + b"\r\n"
                )

                elapsed = time.time() - t0
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
        finally:
            grabber.stop()

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        }
    )


@router.post("/", response_model=Camera)
async def create_camera(camera: CameraCreate):
    """
    Register a new camera (RTSP or Webcam) and optionally its initial zones/model.
    """
    db = await get_db()
    try:
        # Check if ID already exists
        cursor = await db.execute("SELECT id FROM cameras WHERE id = ?", (camera.id,))
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Camera ID already exists")

        zones_json = json.dumps(camera.zones) if camera.zones is not None else "[]"
        classes_json = json.dumps(camera.classes) if camera.classes is not None else "[]"

        await db.execute(
            """
            INSERT INTO cameras (id, name, type, url, device_id, status, zones, model_name, classes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                camera.id,
                camera.name,
                camera.type,
                camera.url,
                camera.device_id,
                "idle",
                zones_json,
                camera.model_name or "yolo11n",
                classes_json
            )
        )
        await db.commit()

        # Fetch it back
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera.id,))
        row = await cursor.fetchone()
        
        row_dict = dict(row)
        row_dict["zones"] = json.loads(row_dict["zones"]) if row_dict["zones"] else []
        row_dict["classes"] = json.loads(row_dict["classes"]) if row_dict["classes"] else []
        
        return Camera(**row_dict)
    finally:
        await db.close()


@router.put("/{camera_id}")
async def update_camera(camera_id: str, camera_update: CameraUpdate):
    """
    Update an existing camera's zones, model, or stream configuration.
    Usually called right before switching to the Livestream page.
    """
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Merge updates with existing DB row
        existing = dict(row)
        
        name = camera_update.name if camera_update.name is not None else existing['name']
        type_str = camera_update.type if camera_update.type is not None else existing['type']
        url = camera_update.url if camera_update.url is not None else existing['url']
        device_id = camera_update.device_id if camera_update.device_id is not None else existing['device_id']
        model_name = camera_update.model_name if camera_update.model_name is not None else existing['model_name']
        
        zones_json = json.dumps(camera_update.zones) if camera_update.zones is not None else existing['zones']
        classes_json = json.dumps(camera_update.classes) if camera_update.classes is not None else existing['classes']

        await db.execute(
            """
            UPDATE cameras 
            SET name = ?, type = ?, url = ?, device_id = ?, zones = ?, model_name = ?, classes = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                name,
                type_str,
                url,
                device_id,
                zones_json,
                model_name,
                classes_json,
                camera_id
            )
        )
        await db.commit()

        return JSONResponse({"status": "success", "message": "Camera updated"})
    finally:
        await db.close()


@router.get("/{camera_id}", response_model=Camera)
async def get_camera(camera_id: str):
    """
    Get a specific camera by ID.
    """
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Camera not found")

        row_dict = dict(row)
        row_dict["zones"] = json.loads(row_dict["zones"]) if row_dict["zones"] else []
        row_dict["classes"] = json.loads(row_dict["classes"]) if row_dict["classes"] else []
        return Camera(**row_dict)
    finally:
        await db.close()


@router.get("/", response_model=List[Camera])
async def list_cameras():
    """
    List all configured cameras.
    """
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        
        cameras = []
        for row in rows:
            row_dict = dict(row)
            row_dict["zones"] = json.loads(row_dict["zones"]) if row_dict["zones"] else []
            row_dict["classes"] = json.loads(row_dict["classes"]) if row_dict["classes"] else []
            cameras.append(Camera(**row_dict))
            
        return cameras
    finally:
        await db.close()


@router.websocket("/{camera_id}/ws")
async def websocket_endpoint(websocket: WebSocket, camera_id: str):
    """
    WebSocket endpoint for real-time YOLO analytics.

    Both webcam and RTSP/HLS streams send their visible frames
    to this websocket directly from the browser's <video> element.
    Uses the shared AnalyticsEngine for zone-aware counting.
    """
    await websocket.accept()

    if camera_id not in active_connections:
        active_connections[camera_id] = []
    active_connections[camera_id].append(websocket)

    # Look up camera config (type, model, zones) from DB
    db = await get_db()
    try:
        cursor = await db.execute("SELECT type, model_name, zones FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()

    model_name = row["model_name"] if row else "yolo11n"
    
    # Parse zones from DB
    raw_zones = row["zones"] if row else "[]"
    zones = json.loads(raw_zones) if isinstance(raw_zones, str) else (raw_zones or [])

    try:
        while True:
            # Client sends binary JPEG frames
            data = await websocket.receive_bytes()
            from services.camera_worker import process_frame_bytes
            result = process_frame_bytes(data, camera_id, model_name, zones)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
    finally:
        if camera_id in active_connections and websocket in active_connections[camera_id]:
            active_connections[camera_id].remove(websocket)
        if not active_connections.get(camera_id):
            active_connections.pop(camera_id, None)

