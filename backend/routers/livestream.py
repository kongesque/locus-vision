"""
Livestream router: MJPEG video stream and SSE events endpoints.

Loads camera configuration from the database before creating streams,
so zones, classes, and model settings are applied to the AI pipeline.
"""

import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from services.livestream_manager import livestream_manager
from database import get_db

router = APIRouter(
    prefix="/api/livestream",
    tags=["livestream"],
)


async def _load_camera_config(camera_id: str):
    """Load camera source/zones/classes/model/fps/conf from the database."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,))
        row = await cursor.fetchone()
        if not row:
            return None, None, None, "yolo11n", 24, 0.15

        cam = dict(row)
        raw_source = cam.get("device_id") or cam.get("url")
        source = int(raw_source) if isinstance(raw_source, str) and raw_source.isdigit() else raw_source
        zones = None
        classes = None
        model_name = cam.get("model_name", "yolo11n")
        fps = cam.get("fps", 24)
        conf_threshold = cam.get("confidence_threshold", 0.15)

        if cam.get("zones"):
            try:
                zones = json.loads(cam["zones"])
            except (json.JSONDecodeError, TypeError):
                pass

        if cam.get("classes"):
            try:
                classes = json.loads(cam["classes"])
            except (json.JSONDecodeError, TypeError):
                pass

        return source, zones, classes, model_name, fps, conf_threshold
    finally:
        await db.close()


@router.get("/{camera_id}/video")
async def video_feed(camera_id: str, request: Request):
    """
    Returns a continuous MJPEG stream.
    Loads camera config from DB to initialize zones/classes on first connect.
    """
    source, zones, classes, model_name, fps, conf_threshold = await _load_camera_config(camera_id)
    stream_ctx = livestream_manager.get_or_create_stream(
        camera_id, zones=zones, classes=classes, model_name=model_name, fps=fps, source=source, conf_threshold=conf_threshold
    )
    client_queue = asyncio.Queue(maxsize=30)
    stream_ctx.video_clients.append(client_queue)
    
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                frame_bytes = await client_queue.get()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        finally:
            stream_ctx.video_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/{camera_id}/events")
async def sse_events(camera_id: str, request: Request):
    """
    Returns a Server-Sent Events (SSE) stream of detection data.
    """
    source, zones, classes, model_name, fps, conf_threshold = await _load_camera_config(camera_id)
    stream_ctx = livestream_manager.get_or_create_stream(
        camera_id, zones=zones, classes=classes, model_name=model_name, fps=fps, source=source, conf_threshold=conf_threshold
    )
    client_queue = asyncio.Queue(maxsize=100)
    stream_ctx.event_clients.append(client_queue)

    async def sse_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                event_json = await client_queue.get()
                yield f"data: {event_json}\n\n"
        finally:
            stream_ctx.event_clients.remove(client_queue)

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@router.get("/{camera_id}/status")
async def stream_status(camera_id: str):
    """
    Get the current stream status including uptime (NVR-style).
    Returns server-side start time so uptime persists across page refreshes.
    """
    import time
    mgr = livestream_manager
    with mgr.lock:
        ctx = mgr.active_streams.get(camera_id)

    if not ctx:
        return {"is_active": False, "started_at": None, "uptime_seconds": 0}

    now = time.time()
    return {
        "is_active": ctx._running,
        "started_at": ctx.started_at,
        "uptime_seconds": round(now - ctx.started_at),
    }


@router.get("/{camera_id}/recent-events")
async def recent_events(camera_id: str, limit: int = 50):
    """
    Get recent detection events from the server-side ring buffer (NVR-style).
    Events persist across page refreshes so the Activity Feed is never empty.
    """
    limit = min(max(limit, 1), 200)
    mgr = livestream_manager
    with mgr.lock:
        ctx = mgr.active_streams.get(camera_id)

    if not ctx:
        return {"events": []}

    # Return the most recent `limit` events (newest first)
    events = list(ctx.recent_events)[-limit:]
    events.reverse()
    return {"events": events}
