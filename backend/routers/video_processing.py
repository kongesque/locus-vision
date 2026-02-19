import os
import cv2
import time
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Dict
import json
from collections import defaultdict
from ultralytics import YOLO
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

def get_class_ids(model, class_names: List[str]) -> List[int]:
    """
    Get class IDs from model definition based on class names.
    """
    if not class_names:
        return []
        
    # Invert model.names: {id: name} -> {name: id}
    # Ensure names are lowercased for comparison if needed, or exact match
    # class_names from frontend might be loose, but usually match model.names
    name_to_id = {v: k for k, v in model.names.items()}
    
    ids = []
    for name in class_names:
        if name in name_to_id:
            ids.append(name_to_id[name])
    return ids

# Cache models to avoid reloading
loaded_models = {}

def get_model(model_name: str):
    if model_name not in loaded_models:
        print(f"Loading model: {model_name}")
        model_path = os.path.join(MODELS_DIR, f"{model_name}.pt")
        
        
        try:
             # Check if we have it in our models dir
             if os.path.exists(model_path):
                 loaded_models[model_name] = YOLO(model_path)
             else:
                 print(f"Model {model_name} not found in {MODELS_DIR}, downloading...")
                 # YOLO downloads to CWD, move it to models dir
                 temp_model = YOLO(f"{model_name}.pt") 
                 if os.path.exists(f"{model_name}.pt"):
                     os.rename(f"{model_name}.pt", model_path)
                     loaded_models[model_name] = YOLO(model_path)
                 else:
                     loaded_models[model_name] = temp_model

        except Exception as e:
            print(f"Error loading {model_name}, falling back to yolov8n. Error: {e}")
            loaded_models[model_name] = YOLO("yolov8n.pt")
            
    return loaded_models[model_name]

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
    Background task to process video.
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
        model = get_model(model_name)
        
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            print(f"Error opening video file {input_path}")
            # Update status to failed
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
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # Reset

        # Calculate frame skipping
        new_fps = min(fps, target_fps)
        skip_interval = max(1, int(fps / new_fps))
        
        # Output setup
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, new_fps, (width, height))

        # Tracking state
        track_history = defaultdict(lambda: [])
        crossed_objects = {} # track_id -> bool (True if counted)

        # Prepare zones
        parsed_zones = []
        for zone in zones:
            pts = np.array([[p['x'], p['y']] for p in zone['points']], np.int32)
            parsed_zones.append({
                "poly": pts,
                "color": (0, 255, 0), # Default color
                "id": zone.get("id"),
                "classes": get_class_ids(model, zone.get("classes", []))
            })
    
        full_frame_class_ids = get_class_ids(model, full_frame_classes)

        frame_count = 0
        start_time = time.time()

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
    
            frame_count += 1
            if frame_count % skip_interval != 0:
                continue

            # YOLO Inference
            # Filter classes if provided (and if we want to filter globally for tracking efficiency)
            # Note: If zones have different classes, we generally need to track ALL relevant classes globally first.
            # We collect all unique class IDs required across all zones + full frame
            required_classes = set(full_frame_class_ids)
            for z in parsed_zones:
                if not z["classes"]: # Empty means ALL
                   required_classes = None # None means track everything
                   break
                required_classes.update(z["classes"])
        
            classes_arg = list(required_classes) if required_classes is not None else None
    
            results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False, classes=classes_arg)
    
            if results and results[0].boxes:
                boxes = results[0].boxes.xywh.cpu().numpy()
                track_ids = results[0].boxes.id
                class_indices = results[0].boxes.cls.cpu().numpy() # Get detected class indices
        
                if track_ids is not None:
                    track_ids = track_ids.int().cpu().tolist()
            
                    for box, track_id, cls_idx in zip(boxes, track_ids, class_indices):
                        cls_idx = int(cls_idx)
                        x, y, w, h = box
                        center = (int(x), int(y))
                
                        track = track_history[track_id]
                        track.append(center)
                        if len(track) > 30:
                            track.pop(0)

                        # Check zones
                        is_inside_target_zone = False
                
                        for zone in parsed_zones:
                            # Check if this object's class matches the zone's filter
                            # If zone.classes is empty, it matches ALL
                            if zone["classes"] and cls_idx not in zone["classes"]:
                                continue
                        
                            # pointPolygonTest returns +1 (inside), -1 (outside), 0 (on edge)
                            dist = cv2.pointPolygonTest(zone["poly"], center, False)
                    
                            if dist >= 0:
                                is_inside_target_zone = True
                                if track_id not in crossed_objects:
                                    crossed_objects[track_id] = True
                
                        # Also check if it matches full frame filter (visualize differently?)
                        # For now just simple coloring logic
                        is_relevant = is_inside_target_zone or (not parsed_zones and (not full_frame_class_ids or cls_idx in full_frame_class_ids))

                        # Custom Drawing
                        if is_inside_target_zone:
                             cv2.circle(frame, center, 9, (244, 133, 66), -1) 
                        elif track_id in crossed_objects:
                             cv2.circle(frame, center, 9, (83, 168, 51), -1) # Green (Already counted)
                        else:
                             cv2.circle(frame, center, 9, (54, 67, 234), -1)

            # Draw Zones
            for zone in parsed_zones:
                cv2.polylines(frame, [zone["poly"]], True, zone["color"], 3)

            # Draw Count
            count_text = f"Count: {len(crossed_objects)}"
            cv2.putText(frame, count_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

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
    zones: str = Form(...), # JSON string
    model: str = Form("yolo11n"),
    classes: str = Form("[]") # JSON string of list of class names (for full frame)
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
    
    # Save Uploaded File
    with open(input_path, "wb") as buffer:
        content = await video.read()
        buffer.write(content)
        
    # Create pending task record
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO video_tasks (id, filename, model_name)
            VALUES (?, ?, ?)
            """,
            (task_id, video.filename, model)
        )
        await db.commit()
    finally:
        await db.close()

    # Start Background Processing
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
    """
    Get list of video processing tasks.
    """
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM video_tasks ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [VideoTask(**dict(row)) for row in rows]
    finally:
        await db.close()

@router.get("/{task_id}/thumbnail")
async def get_thumbnail(task_id: str):
    """
    Get video thumbnail.
    """
    thumb_path = os.path.join(CACHE_DIR, f"thumbnail_{task_id}.jpg")
    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")
    
    # Return placeholder if not found (or 404)
    # For now, let's return a 404 so frontend can handle fallback
    return JSONResponse({"detail": "Thumbnail not found"}, status_code=404)

@router.get("/{task_id}/result")
async def get_result(task_id: str):
    """
    Check if result exists and return it (or stream it).
    """
    output_path = os.path.join(CACHE_DIR, f"output_{task_id}.mp4")
    if os.path.exists(output_path):
        return FileResponse(output_path, media_type="video/mp4", filename=f"result_{task_id}.mp4")
    
    return JSONResponse({"status": "pending"}, status_code=202)
