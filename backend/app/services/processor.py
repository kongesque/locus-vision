import time
from app.core.detector import detection
from app.services.db import update_job
from app.services.file_handler import clear_all_uploads

def run_processing_pipeline(taskID, job, zones, confidence, model='yolo11n.pt', tracker_config=None):
    """
    Run video processing pipeline with multiple zones.
    
    Args:
        taskID: Task identifier
        job: Job data from database
        zones: List of zone objects [{id, points, classId, color}, ...]
        confidence: Detection confidence threshold (1-100)
        model: YOLO model name
        tracker_config: ByteTrack configuration dict
    """
    # Default tracker config if not provided
    if tracker_config is None:
        tracker_config = {
            'track_high_thresh': 0.45,
            'track_low_thresh': 0.1,
            'match_thresh': 0.8,
            'track_buffer': 30
        }
    
    start_time = time.time()
    
    last_progress = 0
    final_detection_events = []
    final_dwell_events = []
    final_line_crossing_counts = {}
    final_heatmap_data = None
    
    for frame, progress, detection_events, dwell_events, line_crossing_counts, heatmap_data in detection(
        job['video_path'], 
        zones,
        (job['frame_width'], job['frame_height']), 
        taskID, 
        confidence,
        model,
        tracker_config
    ):
        final_detection_events = detection_events
        final_dwell_events = dwell_events
        final_line_crossing_counts = line_crossing_counts
        final_heatmap_data = heatmap_data
        # Update progress in DB every 5% to avoid too many writes
        if progress >= last_progress + 5 or progress == 100:
            update_job(taskID, progress=progress)
            last_progress = progress
        
    end_time = time.time()
    process_time = round(end_time - start_time, 2)
    
    update_job(taskID, process_time=process_time, status='completed', 
               detection_data=final_detection_events, dwell_data=final_dwell_events,
               line_crossing_data=final_line_crossing_counts, heatmap_data=final_heatmap_data)
    
    # clear_all_uploads()  # Commented out to prevent deleting frames needed by the frontend for results/editing

