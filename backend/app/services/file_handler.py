"""
File Handler Utilities for Video/Image Processing
"""
import os
import uuid
import shutil
import cv2
from werkzeug.utils import secure_filename
from app.core.vision_utils import extract_frame
from app.services.db import create_job, update_job


def handle_upload_file(file, upload_folder):
    """
    Handles video file upload from FastAPI UploadFile object.
    """
    taskID = str(uuid.uuid4())
    original_filename = secure_filename(file.filename) if file.filename else "video.mp4"
    filename = taskID + "_" + original_filename
    filepath = os.path.join(upload_folder, filename)
    
    # Save the uploaded file
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Init Job in DB
    create_job(taskID, original_filename, filepath)
    
    # Ensure frame directory exists
    frame_dir = "uploads/frames"
    os.makedirs(frame_dir, exist_ok=True)
    
    frame_path = os.path.join(frame_dir, "frame_" + taskID + ".jpg")
    
    first_frame = extract_frame(filepath, 0)
    if first_frame is not None:
         cv2.imwrite(frame_path, first_frame)
         frame_size = first_frame.shape[1], first_frame.shape[0]  # width, height
         update_job(taskID, frame_path=frame_path, frame_width=frame_size[0], frame_height=frame_size[1])
    
    return taskID


def handle_rtsp_source(stream_url, source_type='rtsp'):
    """
    Creates a job for RTSP/webcam source by capturing a single frame for zone setup.
    
    Args:
        stream_url: RTSP URL string or webcam index as string (e.g., "0")
        source_type: "rtsp" or "webcam"
    
    Returns:
        taskID: Generated task ID
        
    Raises:
        ValueError: If unable to connect to stream
    """
    taskID = str(uuid.uuid4())
    
    # Connect to stream - webcam uses integer index
    if source_type == 'webcam':
        cap = cv2.VideoCapture(int(stream_url))
    else:
        cap = cv2.VideoCapture(stream_url)
    
    # Try to grab a frame (with timeout-like attempt)
    success = False
    for _ in range(30):  # Try for ~1 second
        success, frame = cap.read()
        if success:
            break
    
    if not success:
        cap.release()
        raise ValueError(f"Could not connect to stream: {stream_url}")
    
    # Get frame dimensions
    height, width = frame.shape[:2]
    
    # Ensure frame directory exists
    frame_dir = "uploads/frames"
    os.makedirs(frame_dir, exist_ok=True)
    
    # Save frame for zone selection
    frame_path = os.path.join(frame_dir, f"frame_{taskID}.jpg")
    cv2.imwrite(frame_path, frame)
    
    cap.release()
    
    # Create job with stream info (no video_path for live sources)
    create_job(taskID, "Live Stream", None)
    update_job(taskID, 
               source_type=source_type, 
               stream_url=stream_url,
               frame_path=frame_path,
               frame_width=width,
               frame_height=height)
    
    return taskID


def safe_remove_file(file_path):
    """
    Safely removes a file if it exists, ignoring errors.
    """
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass


def clear_all_uploads():
    """
    Removes all files in the frames folder (keeps videos).
    """
    frame_dir = "uploads/frames"
    
    if os.path.exists(frame_dir):
        for filename in os.listdir(frame_dir):
            file_path = os.path.join(frame_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except OSError:
                pass
