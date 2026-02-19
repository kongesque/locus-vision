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

CACHE_DIR = "data/videos"
MODELS_DIR = "data/models"
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# COCO Class mapping (simplified for demo)
# In reality, you'd want a robust mapping or pass class IDs directly from frontend
COCO_CLASSES = {
    "person": 0, "bicycle": 1, "car": 2, "motorcycle": 3, "airplane": 4, "bus": 5, "train": 6, "truck": 7, "boat": 8,
    "traffic light": 9, "fire hydrant": 10, "stop sign": 11, "parking meter": 12, "bench": 13, "bird": 14, "cat": 15,
    "dog": 16, "horse": 17, "sheep": 18, "cow": 19, "elephant": 20, "bear": 21, "zebra": 22, "giraffe": 23,
    "backpack": 24, "umbrella": 25, "handbag": 26, "tie": 27, "suitcase": 28, "frisbee": 29, "skis": 30,
    "snowboard": 31, "sports ball": 32, "kite": 33, "baseball bat": 34, "baseball glove": 35, "skateboard": 36,
    "surfboard": 37, "tennis racket": 38, "bottle": 39, "wine glass": 40, "cup": 41, "fork": 42, "knife": 43,
    "spoon": 44, "bowl": 45, "banana": 46, "apple": 47, "sandwich": 48, "orange": 49, "broccoli": 50, "carrot": 51,
    "hot dog": 52, "pizza": 53, "donut": 54, "cake": 55, "chair": 56, "couch": 57, "potted plant": 58, "bed": 59,
    "dining table": 60, "toilet": 61, "tv": 62, "laptop": 63, "mouse": 64, "remote": 65, "keyboard": 66, "cell phone": 67,
    "microwave": 68, "oven": 69, "toaster": 70, "sink": 71, "refrigerator": 72, "book": 73, "clock": 74, "vase": 75,
    "scissors": 76, "teddy bear": 77, "hair drier": 78, "toothbrush": 79
}

def get_class_ids(class_names: List[str]) -> List[int]:
    ids = []
    for name in class_names:
        if name in COCO_CLASSES:
            ids.append(COCO_CLASSES[name])
    return ids

# Cache models to avoid reloading
loaded_models = {}

def get_model(model_name: str):
    if model_name not in loaded_models:
        print(f"Loading model: {model_name}")
        model_path = os.path.join(MODELS_DIR, f"{model_name}.pt")
        
        # If model doesn't exist in data/models, try to load it normally (which might download to CWD)
        # then move it? Or just let ultralytics handle it?
        # Ultralytics downloads to CWD by default.
        # Let's try to specifying the full path for loading.
        # If it doesn't exist, we might need to download it manually or let ultralytics download to CWD and move it.
        # Simpler approach: Just use CWD for download, then start using it. 
        # But user wants organization.
        
        try:
             # Check if we have it in our models dir
             if os.path.exists(model_path):
                 loaded_models[model_name] = YOLO(model_path)
             else:
                 # It's not there. Let YOLO download it.
                 # YOLO(model_name) usually downloads to current dir.
                 print(f"Model {model_name} not found in {MODELS_DIR}, downloading...")
                 temp_model = YOLO(f"{model_name}.pt") 
                 # Move the downloaded file to models dir
                 if os.path.exists(f"{model_name}.pt"):
                     os.rename(f"{model_name}.pt", model_path)
                     # Reload from new path to be sure
                     loaded_models[model_name] = YOLO(model_path)
                 else:
                     loaded_models[model_name] = temp_model

        except Exception as e:
            print(f"Error loading {model_name}, falling back to yolov8n. Error: {e}")
            loaded_models[model_name] = YOLO("yolov8n.pt")
            
    return loaded_models[model_name]

def process_video_task(
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
    model = get_model(model_name)
    
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
    
    # Prepare zones
    parsed_zones = []
    for zone in zones:
        pts = np.array([[p['x'], p['y']] for p in zone['points']], np.int32)
        parsed_zones.append({
            "poly": pts,
            "color": (0, 255, 0), # Default color
            "id": zone.get("id"),
            "classes": get_class_ids(zone.get("classes", []))
        })
        
    full_frame_class_ids = get_class_ids(full_frame_classes)

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

@router.get("/{task_id}/result")
async def get_result(task_id: str):
    """
    Check if result exists and return it (or stream it).
    """
    output_path = os.path.join(CACHE_DIR, f"output_{task_id}.mp4")
    if os.path.exists(output_path):
        return FileResponse(output_path, media_type="video/mp4", filename=f"result_{task_id}.mp4")
    
    return JSONResponse({"status": "pending"}, status_code=202)
