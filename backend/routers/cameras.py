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
    WebSocket endpoint for streaming real-time YOLO analytics metadata to the frontend.
    """
    await websocket.accept()
    
    if camera_id not in active_connections:
        active_connections[camera_id] = []
    
    active_connections[camera_id].append(websocket)
    
    # As soon as the first client connects, spawn the heavy YOLO camera worker thread
    if len(active_connections[camera_id]) == 1:
        from services.camera_worker import camera_manager
        camera_manager.spawn_worker(camera_id)

    try:
        # We just wait for messages from the browser or standard health pings
        while True:
            data = await websocket.receive_text()
            # If the client sends updated zones, we could parse them here.
            # But normally PUT handles that, and the worker reloads from DB.
    except WebSocketDisconnect:
        active_connections[camera_id].remove(websocket)
        if not active_connections[camera_id]:
            del active_connections[camera_id]
            # Kill the worker to save CPU when no one is watching
            from services.camera_worker import camera_manager
            camera_manager.kill_worker(camera_id)

