import os
import json
import shutil
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from typing import List
from database import get_db
from models import VideoTask, VideoTaskUpdate
from services.job_queue import job_queue

router = APIRouter(
    prefix="/api/video",
    tags=["video"],
    responses={404: {"description": "Not found"}},
)

CACHE_DIR = "data/videos"
os.makedirs(CACHE_DIR, exist_ok=True)


@router.post("/{task_id}/process")
async def process_video(
    task_id: str,
    video: UploadFile = File(...),
    zones: str = Form("[]"),
    model: str = Form("yolo11n"),
    classes: str = Form("[]"),
):
    """
    Upload a video and enqueue it for background processing.
    The job queue worker will pick it up automatically.
    """
    try:
        zones_data = json.loads(zones)
        classes_data = json.loads(classes)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid zones or classes JSON")

    input_path = os.path.join(CACHE_DIR, f"input_{task_id}.mp4")

    with open(input_path, "wb") as buffer:
        content = await video.read()
        buffer.write(content)

    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO video_tasks
               (id, filename, status, progress, model_name, zones, classes)
               VALUES (?, ?, 'pending', 0, ?, ?, ?)""",
            (task_id, video.filename, model, json.dumps(zones_data), json.dumps(classes_data)),
        )
        await db.commit()
    finally:
        await db.close()

    return JSONResponse(
        {
            "status": "queued",
            "task_id": task_id,
            "message": "Video uploaded and queued for processing.",
        }
    )


@router.get("/queue/status")
async def get_queue_status():
    """Return the current state of the processing queue."""
    return JSONResponse(job_queue.get_queue_status())


@router.get("/history", response_model=List[VideoTask])
async def get_history():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM video_tasks ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [VideoTask(**dict(row)) for row in rows]
    finally:
        await db.close()


@router.get("/{task_id}/status")
async def get_task_status(task_id: str):
    """Get status and progress for a specific task."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM video_tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return VideoTask(**dict(row))
    finally:
        await db.close()


@router.get("/{task_id}/thumbnail")
async def get_thumbnail(task_id: str):
    thumb_path = os.path.join(CACHE_DIR, f"thumbnail_{task_id}.jpg")
    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")
    return JSONResponse({"detail": "Thumbnail not found"}, status_code=404)


@router.get("/{task_id}/result")
async def get_result(task_id: str):
    output_path = os.path.join(CACHE_DIR, f"output_{task_id}.mp4")
    if os.path.exists(output_path):
        return FileResponse(output_path, media_type="video/mp4", filename=f"result_{task_id}.mp4")
    return JSONResponse({"status": "pending"}, status_code=202)


@router.get("/{task_id}/data")
async def get_data(task_id: str):
    data_path = os.path.join(CACHE_DIR, f"data_{task_id}.json")
    if os.path.exists(data_path):
        return FileResponse(
            data_path, media_type="application/json", filename=f"insights_{task_id}.json"
        )
    return JSONResponse({"detail": "Raw data not found"}, status_code=404)


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its associated files."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM video_tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        # Don't allow deleting the currently processing task
        status = job_queue.get_queue_status()
        if status["processing"] and status["processing"]["task_id"] == task_id:
            raise HTTPException(status_code=409, detail="Cannot delete a task that is currently processing")

        await db.execute("DELETE FROM video_tasks WHERE id = ?", (task_id,))
        await db.commit()
    finally:
        await db.close()

    # Clean up files
    for prefix in ["input_", "output_", "thumbnail_", "data_"]:
        ext = ".json" if prefix == "data_" else (".jpg" if prefix == "thumbnail_" else ".mp4")
        path = os.path.join(CACHE_DIR, f"{prefix}{task_id}{ext}")
        if os.path.exists(path):
            os.remove(path)

    return JSONResponse({"message": "Task deleted"})


@router.put("/{task_id}")
async def update_task(task_id: str, update: VideoTaskUpdate):
    """Update a task's properties (e.g., rename)."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM video_tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        # Build update fields
        update_fields = []
        params = []
        if update.name is not None:
            update_fields.append("name = ?")
            params.append(update.name)

        if not update_fields:
            return VideoTask(**dict(row))

        params.append(task_id)
        await db.execute(
            f"UPDATE video_tasks SET {', '.join(update_fields)} WHERE id = ?",
            params
        )
        await db.commit()

        # Fetch and return updated task
        cursor = await db.execute("SELECT * FROM video_tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return VideoTask(**dict(row))
    finally:
        await db.close()
