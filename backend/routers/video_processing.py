import os
import cv2
import time
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Dict
import json
from services.analytics_engine import AnalyticsEngine
from database import get_db
from models import VideoTask
from datetime import datetime
import shutil

router = APIRouter(
    prefix="/api/video",
    tags=["video"],
    responses={404: {"description": "Not found"}},
)

CACHE_DIR = "data/videos"
MODELS_DIR = "data/models"
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)


async def process_video_task(
    input_path: str,
    output_path: str,
    zones: List[Dict],
    task_id: str,
    model_name: str = "yolov8n",
    full_frame_classes: List[str] = [],
    target_fps: int = 12
):
    """
    Background task to process video using the shared AnalyticsEngine.
    """
    # 1. Update status to processing
    db = await get_db()
    try:
        await db.execute(
            "UPDATE video_tasks SET status = 'processing' WHERE id = ?",
            (task_id,)
        )
        await db.commit()
    except Exception as e:
        print(f"Error updating status for {task_id}: {e}")
    finally:
        await db.close()

    try:
        # Initialize the shared analytics engine
        engine = AnalyticsEngine(
            model_name=model_name,
            zones=zones,
            full_frame_classes=full_frame_classes,
        )
        
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            print(f"Error opening video file {input_path}")
            db = await get_db()
            try:
                await db.execute("UPDATE video_tasks SET status = 'failed' WHERE id = ?", (task_id,))
                await db.commit()
            finally:
                await db.close()
            return

        # Video properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total_frames / fps if fps > 0 else 0
        duration_str = time.strftime('%H:%M:%S', time.gmtime(duration_sec))

        # Generate Thumbnail (middle frame)
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
        ret, thumb_frame = cap.read()
        if ret:
            thumb_path = os.path.join(CACHE_DIR, f"thumbnail_{task_id}.jpg")
            cv2.imwrite(thumb_path, thumb_frame)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # Calculate frame skipping
        new_fps = min(fps, target_fps)
        skip_interval = max(1, int(fps / new_fps))
        
        # Output setup
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, new_fps, (width, height))

        frame_count = 0
        start_time = time.time()

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
    
            frame_count += 1
            if frame_count % skip_interval != 0:
                continue

            # Single call to the shared engine handles detection + tracking + counting
            result = engine.process_frame(frame)

            # Draw annotations (zones, boxes, count text)
            engine.draw_annotations(frame, result)

            out.write(frame)

        cap.release()
        out.release()

        # Cleanup input
        if os.path.exists(input_path):
            os.remove(input_path)
    
        print(f"Processing complete for {task_id}. Time: {time.time() - start_time:.2f}s")

        # Update status to completed
        db = await get_db()
        try:
            await db.execute(
                """
                UPDATE video_tasks 
                SET status = 'completed', 
                    completed_at = datetime('now'),
                    duration = ?,
                    format = 'mp4'
                WHERE id = ?
                """,
                (duration_str, task_id)
            )
            await db.commit()
        except Exception as e:
            print(f"Error updating completion status for {task_id}: {e}")
        finally:
            await db.close()

    except Exception as e:
        print(f"Error processing {task_id}: {e}")
        db = await get_db()
        try:
            await db.execute("UPDATE video_tasks SET status = 'failed' WHERE id = ?", (task_id,))
            await db.commit()
        finally:
            await db.close()


@router.post("/{task_id}/process")
async def process_video(
    task_id: str,
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    zones: str = Form(...),
    model: str = Form("yolo11n"),
    classes: str = Form("[]")
):
    """
    Upload a video and start processing in the background.
    """
    try:
        zones_data = json.loads(zones)
        classes_data = json.loads(classes)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid zones or classes JSON")

    input_path = os.path.join(CACHE_DIR, f"input_{task_id}.mp4")
    output_path = os.path.join(CACHE_DIR, f"output_{task_id}.mp4")
    
    with open(input_path, "wb") as buffer:
        content = await video.read()
        buffer.write(content)
        
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO video_tasks (id, filename, model_name) VALUES (?, ?, ?)",
            (task_id, video.filename, model)
        )
        await db.commit()
    finally:
        await db.close()

    background_tasks.add_task(
        process_video_task,
        input_path,
        output_path,
        zones_data,
        task_id,
        model,
        classes_data
    )
    
    return JSONResponse({
        "status": "processing",
        "task_id": task_id,
        "message": "Video uploaded and processing started."
    })

@router.get("/history", response_model=List[VideoTask])
async def get_history():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM video_tasks ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [VideoTask(**dict(row)) for row in rows]
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
