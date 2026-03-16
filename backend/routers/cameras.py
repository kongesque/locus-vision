"""CRUD router for camera management."""

import uuid
import asyncio
import threading
import cv2
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List
from database import get_db
from models import CameraCreate, CameraUpdate, CameraResponse
from services.discovery_service import discovery_service

router = APIRouter(
    prefix="/api/cameras",
    tags=["cameras"],
    responses={404: {"description": "Not found"}},
)


@router.get("/discover")
async def discover_cameras():
    """Discover local and network cameras."""
    return await discovery_service.discover_all()


@router.get("/snapshot")
async def camera_snapshot(source: str):
    """Capture a single JPEG frame from a camera source for preview."""
    import cv2
    from fastapi.responses import Response

    try:
        # Try as integer index first (local camera)
        src = int(source) if source.isdigit() else source
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            raise HTTPException(status_code=404, detail="Could not open camera")

        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=500, detail="Failed to capture frame")

        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        return Response(content=buffer.tobytes(), media_type="image/jpeg")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source")


@router.get("/{camera_id}/preview-stream")
async def camera_preview_stream(camera_id: str, request: Request):
    """Raw MJPEG stream for the create/configure page — no inference, just raw frames."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT type, url, device_id FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Camera not found")
        cam = dict(row)
    finally:
        await db.close()

    src = cam.get("device_id") or cam.get("url")
    if src is None:
        raise HTTPException(status_code=400, detail="Camera has no source configured")
    src = int(src) if isinstance(src, str) and src.isdigit() else src

    frame_queue: asyncio.Queue = asyncio.Queue(maxsize=4)
    loop = asyncio.get_event_loop()
    stop_event = threading.Event()

    def capture_loop():
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            stop_event.set()
            return
        try:
            while not stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    break
                _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                if not frame_queue.full():
                    asyncio.run_coroutine_threadsafe(frame_queue.put(buf.tobytes()), loop)
        finally:
            cap.release()

    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    frame_bytes = await asyncio.wait_for(frame_queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    break
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        finally:
            stop_event.set()

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("", response_model=List[CameraResponse])
async def list_cameras():
    """List all cameras."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [CameraResponse(**dict(row)) for row in rows]
    finally:
        await db.close()


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: str):
    """Get a single camera by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Camera not found")
        return CameraResponse(**dict(row))
    finally:
        await db.close()


@router.post("", response_model=CameraResponse)
async def create_camera(camera: CameraCreate):
    """Create a new camera."""
    camera_id = camera.id or str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO cameras (id, name, type, url, device_id, model_name, fps, zones, classes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                camera_id,
                camera.name,
                camera.type,
                camera.url,
                camera.device_id,
                camera.model_name,
                camera.fps,
                camera.zones,
                camera.classes,
            ),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        return CameraResponse(**dict(row))
    finally:
        await db.close()


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(camera_id: str, update: CameraUpdate):
    """Update a camera's configuration."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Build dynamic SET clause for non-None fields
        existing = dict(row)
        updates = update.model_dump(exclude_none=True)
        if not updates:
            return CameraResponse(**existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        set_clause += ", updated_at = datetime('now')"
        values = list(updates.values()) + [camera_id]

        await db.execute(
            f"UPDATE cameras SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        return CameraResponse(**dict(row))
    finally:
        await db.close()


@router.delete("/{camera_id}")
async def delete_camera(camera_id: str):
    """Delete a camera."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Camera not found")

        await db.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
        await db.commit()
        return JSONResponse({"message": "Camera deleted"})
    finally:
        await db.close()
