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

router = APIRouter(
    prefix="/api/video",
    tags=["video"],
    responses={404: {"description": "Not found"}},
)

# Global model instance to avoid reloading
# In a real production app, consider using a dependency injection or a singleton pattern properly
try:
    model = YOLO('yolov8n.pt')
except Exception as e:
    print(f"Failed to load YOLO model: {e}")
    model = None

CACHE_DIR = "static/files/output"
os.makedirs(CACHE_DIR, exist_ok=True)

def process_video_task(
    input_path: str,
    output_path: str,
    zones: List[Dict],
    task_id: str,
    target_fps: int = 12
):
    """
    Background task to process video.
    Optimized version of the user provided script.
    """
    if model is None:
        print("Model not loaded, skipping processing")
        return

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error opening video file {input_path}")
        return

    # Video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Calculate frame skipping
    new_fps = min(fps, target_fps)
    skip_interval = max(1, int(fps / new_fps))
    
    # Output setup
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(output_path, fourcc, new_fps, (width, height))

    # Tracking state
    track_history = defaultdict(lambda: [])
    crossed_objects = {} # track_id -> bool (True if counted)
    
    # Prepare zones (convert to numpy arrays for polylinetest)
    # Zone format from frontend: { points: [{x, y}, ...], ... }
    parsed_zones = []
    for zone in zones:
        pts = np.array([[p['x'], p['y']] for p in zone['points']], np.int32)
        parsed_zones.append({
            "poly": pts,
            "color": (0, 255, 0), # Default color
            "id": zone.get("id")
        })

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
        # Persist=True is important for tracking
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        
        if results and results[0].boxes:
            boxes = results[0].boxes.xywh.cpu().numpy()
            track_ids = results[0].boxes.id
            
            if track_ids is not None:
                track_ids = track_ids.int().cpu().tolist()
                
                # Annotate frame
                # frame = results[0].plot() # Using built-in plot or custom drawing
                
                for box, track_id in zip(boxes, track_ids):
                    x, y, w, h = box
                    center = (int(x), int(y))
                    
                    track = track_history[track_id]
                    track.append(center)
                    if len(track) > 30:
                        track.pop(0)

                    # Check zones
                    is_inside_any = False
                    for zone in parsed_zones:
                        # pointPolygonTest returns +1 (inside), -1 (outside), 0 (on edge)
                        dist = cv2.pointPolygonTest(zone["poly"], center, False)
                        
                        if dist >= 0:
                            is_inside_any = True
                            if track_id not in crossed_objects:
                                crossed_objects[track_id] = True
                    
                    # Custom Drawing
                    color = (244, 133, 66) if is_inside_any else (54, 67, 234) # Blue vs Red
                    if is_inside_any:
                         cv2.circle(frame, center, 9, (244, 133, 66), -1) 
                    elif track_id in crossed_objects:
                         cv2.circle(frame, center, 9, (83, 168, 51), -1) # Green (Already counted)
                    else:
                         cv2.circle(frame, center, 9, (54, 67, 234), -1)

                    # Draw trails
                    # points = np.hstack(track).astype(np.int32).reshape((-1, 1, 2))
                    # cv2.polylines(frame, [points], isClosed=False, color=(230, 230, 230), thickness=2)

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


@router.post("/{task_id}/process")
async def process_video(
    task_id: str,
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    zones: str = Form(...) # JSON string
):
    """
    Upload a video and start processing in the background.
    """
    try:
        zones_data = json.loads(zones)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid zones JSON")

    input_path = os.path.join(CACHE_DIR, f"input_{task_id}.mp4")
    output_path = os.path.join(CACHE_DIR, f"output_{task_id}.mp4")
    
    # Save Uploaded File
    with open(input_path, "wb") as buffer:
        content = await video.read()
        buffer.write(content)
        
    # Start Background Processing
    background_tasks.add_task(
        process_video_task,
        input_path,
        output_path,
        zones_data,
        task_id
    )
    
    return JSONResponse({
        "status": "processing",
        "task_id": task_id,
        "message": "Video uploaded and processing started."
    })

@router.get("/{task_id}/result")
async def get_result(task_id: str):
    """
    Check if result exists and return it (or stream it).
    """
    output_path = os.path.join(CACHE_DIR, f"output_{task_id}.mp4")
    if os.path.exists(output_path):
        return FileResponse(output_path, media_type="video/mp4", filename=f"result_{task_id}.mp4")
    
    return JSONResponse({"status": "pending"}, status_code=202)
