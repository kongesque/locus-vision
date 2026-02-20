import json
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
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

    For webcam cameras: the browser sends JPEG frames (as binary), we run YOLO
    and send back bounding-box JSON.

    For RTSP cameras: we spawn a background thread that reads the RTSP stream
    and pushes results into this WebSocket.
    """
    await websocket.accept()

    if camera_id not in active_connections:
        active_connections[camera_id] = []
    active_connections[camera_id].append(websocket)

    # Look up the camera type from DB
    db = await get_db()
    try:
        cursor = await db.execute("SELECT type, model_name FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()

    cam_type = row["type"] if row else "webcam"
    model_name = row["model_name"] if row else "yolo11n"

    # For RTSP, spin up the background thread
    if cam_type == "rtsp":
        from services.camera_worker import camera_manager
        camera_manager.spawn_rtsp_worker(camera_id)

    try:
        while True:
            if cam_type == "webcam":
                # Browser sends binary JPEG frames
                data = await websocket.receive_bytes()
                from services.camera_worker import process_frame_bytes
                result = process_frame_bytes(data, model_name)
                await websocket.send_json(result)
            else:
                # RTSP: the background thread pushes messages; we just keep alive
                _msg = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if camera_id in active_connections and websocket in active_connections[camera_id]:
            active_connections[camera_id].remove(websocket)
        if not active_connections.get(camera_id):
            active_connections.pop(camera_id, None)
            if cam_type == "rtsp":
                from services.camera_worker import camera_manager
                camera_manager.kill_worker(camera_id)

