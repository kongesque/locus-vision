"""
Live detection module for continuous stream processing (RTSP/webcam).
Unlike the file-based detector, this yields frames continuously without saving to file.
"""

import cv2
import os
import tempfile
import time
import shutil
import colorsys
import numpy as np
from collections import defaultdict
from ultralytics import YOLO


def get_color_from_class_id(class_id):
    """
    Generate a distinct color based on class ID using Golden Angle Approximation.
    Matches the frontend logic in zone.js.
    """
    hue = ((class_id * 137.508) % 360) / 360.0
    saturation = 0.85
    lightness = 0.55
    
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
    return (int(b * 255), int(g * 255), int(r * 255))


def check_line_crossing(prev_pos, curr_pos, line_start, line_end):
    """Check if movement from prev_pos to curr_pos crosses the line segment."""
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
    
    A, B = prev_pos, curr_pos
    C, D = line_start, line_end
    
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


# Global state management for live streams
_active_streams = {}


def stop_live_stream(task_id):
    """Signal a live stream to stop."""
    if task_id in _active_streams:
        _active_streams[task_id]['running'] = False


def is_stream_running(task_id):
    """Check if a stream is currently running."""
    return task_id in _active_streams and _active_streams[task_id].get('running', False)


def get_stream_counts(task_id):
    """Get current counts for a running stream."""
    if task_id in _active_streams:
        return _active_streams[task_id].get('counts', {})
    return {}


def get_stream_analytics(task_id):
    """Get comprehensive analytics data for a running stream."""
    if task_id not in _active_streams:
        return None
    
    stream = _active_streams[task_id]
    start_time = stream.get('start_time', time.time())
    elapsed = round(time.time() - start_time, 1)
    history = stream.get('history', [])
    counts = stream.get('counts', {})
    peaks = stream.get('peak_counts', {})
    
    # Calculate rates (objects per minute based on last 60 seconds)
    rates = {}
    if len(history) >= 2:
        # Get history from 60 seconds ago
        cutoff_time = elapsed - 60
        old_counts = {}
        for h in history:
            if h['time'] <= cutoff_time:
                old_counts = h['counts']
            else:
                break
        
        for zone_id, current_count in counts.items():
            old_count = old_counts.get(zone_id, 0)
            rate_per_minute = (current_count - old_count) * (60.0 / min(60, elapsed))
            rates[zone_id] = round(rate_per_minute, 1)
    
    return {
        'counts': counts,
        'peaks': peaks,
        'rates': rates,
        'history': history[-60:],  # Last 60 data points for chart
        'elapsed': elapsed,
        'running': stream.get('running', False)
    }


def live_detection(stream_url, zones, frame_size, task_id, conf=40, 
                   model_name='yolo11n.pt', tracker_config=None, source_type='rtsp'):
    """
    Generator yielding processed frames from live stream.
    
    Args:
        stream_url: RTSP URL or webcam index string
        zones: List of zone objects [{id, points, classId, color}, ...]
        frame_size: Tuple of (width, height)
        task_id: Task identifier for stream management
        conf: Confidence threshold (1-100)
        model_name: Name of the YOLO model file
        tracker_config: ByteTrack configuration dict
        source_type: "rtsp" or "webcam"
    
    Yields:
        (jpeg_bytes, counts_dict) - JPEG encoded frame and current counts per zone
    """
    # Default tracker config
    if tracker_config is None:
        tracker_config = {
            'track_high_thresh': 0.45,
            'track_low_thresh': 0.1,
            'match_thresh': 0.8,
            'track_buffer': 30
        }
    
    # Create temporary tracker YAML
    tracker_yaml_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    tracker_yaml_path = tracker_yaml_file.name
    
    tracker_yaml_content = f"""# Custom ByteTrack config for live stream {task_id}
tracker_type: bytetrack
track_high_thresh: {tracker_config.get('track_high_thresh', 0.45)}
track_low_thresh: {tracker_config.get('track_low_thresh', 0.1)}
new_track_thresh: {tracker_config.get('track_high_thresh', 0.45)}
track_buffer: {int(tracker_config.get('track_buffer', 30))}
match_thresh: {tracker_config.get('match_thresh', 0.8)}
fuse_score: True
"""
    tracker_yaml_file.write(tracker_yaml_content)
    tracker_yaml_file.close()
    
    # Initialize stream state with analytics history
    _active_streams[task_id] = {
        'running': True,
        'counts': {},
        'history': [],  # List of {time: seconds_since_start, counts: {zone_id: count}}
        'peak_counts': {},  # {zone_id: {count: N, time: T}}
        'start_time': time.time()
    }
    
    try:
        yield from _run_live_detection(
            stream_url, zones, frame_size, task_id, conf, 
            model_name, tracker_yaml_path, source_type
        )
    finally:
        # Cleanup
        if os.path.exists(tracker_yaml_path):
            os.remove(tracker_yaml_path)
        if task_id in _active_streams:
            del _active_streams[task_id]


def _run_live_detection(stream_url, zones, frame_size, task_id, conf, 
                        model_name, tracker_yaml_path, source_type):
    """Internal generator for live detection processing."""
    
    width, height = frame_size
    
    # Font settings (scaled based on frame size)
    font = cv2.FONT_ITALIC
    BASE_FONT_SIZE = 1.2
    font_scale = min(width, height) / 1000 * BASE_FONT_SIZE
    BASE_FONT_THICKNESS = 2
    font_thickness = max(1, max(width, height) // 1000 * BASE_FONT_THICKNESS)
    
    # Load model
    model_path = f"weights/{model_name}"
    if not os.path.exists(model_path):
        print(f"Model {model_name} not found in weights/. Attempting auto-download...")
        try:
            temp_model = YOLO(model_name)
            if os.path.exists(model_name):
                os.makedirs("weights", exist_ok=True)
                shutil.move(model_name, model_path)
            model = YOLO(model_path)
        except Exception as e:
            print(f"Failed to auto-download {model_name}: {e}. Falling back to yolo11n.pt")
            model = YOLO('weights/yolo11n.pt')
    else:
        model = YOLO(model_path)
    
    # Connect to stream
    if source_type == 'webcam':
        cap = cv2.VideoCapture(int(stream_url))
    else:
        cap = cv2.VideoCapture(stream_url)
    
    if not cap.isOpened():
        raise ValueError(f"Could not open stream: {stream_url}")
    
    # Tracking state
    track_history = defaultdict(lambda: [])
    crossed_objects_per_zone = {z['id']: {} for z in zones}
    
    # Preprocess zones
    zone_data = []
    all_class_ids = set()
    for zone in zones:
        points = zone.get('points', [])
        if len(points) < 2:
            continue
        
        area = [(p['x'], p['y']) for p in points]
        area_np = np.array(area, np.int32)
        
        class_ids = zone.get('classIds', [19])  # Array of class IDs
        for class_id in class_ids:
            all_class_ids.add(class_id)
        
        zone_color = zone.get('color', [255, 255, 0])
        bgr_color = (zone_color[2], zone_color[1], zone_color[0])
        
        zone_data.append({
            'id': zone['id'],
            'area': area,
            'area_np': area_np,
            'class_ids': class_ids,  # Store as array
            'color': bgr_color,
            'is_line': len(points) == 2,
            'label': zone.get('label', f'Zone {len(zone_data) + 1}')
        })
    
    ClassIDs = list(all_class_ids) if all_class_ids else [19]
    conf_float = conf / 100.0
    
    frame_count = 0
    target_fps = 15  # Limit FPS for streaming
    frame_interval = 1.0 / target_fps
    last_frame_time = 0
    
    while _active_streams.get(task_id, {}).get('running', False):
        success, frame = cap.read()
        if not success:
            # Try to reconnect
            cap.release()
            time.sleep(1)
            if source_type == 'webcam':
                cap = cv2.VideoCapture(int(stream_url))
            else:
                cap = cv2.VideoCapture(stream_url)
            continue
        
        frame_count += 1
        
        # Control frame rate
        current_time = time.time()
        if current_time - last_frame_time < frame_interval:
            continue
        last_frame_time = current_time
        
        # Resize if needed
        if frame.shape[1] != width or frame.shape[0] != height:
            frame = cv2.resize(frame, (width, height))
        
        # Run detection
        results = model.track(frame, classes=ClassIDs, persist=True, save=False, 
                             tracker=tracker_yaml_path, conf=conf_float, verbose=False)
        boxes = results[0].boxes.xywh.cpu()
        track_ids = (results[0].boxes.id.int().cpu().tolist() 
                    if results[0].boxes is not None and results[0].boxes.id is not None else [])
        detected_classes = (results[0].boxes.cls.int().cpu().tolist() 
                           if results[0].boxes is not None else [])
        
        frame = results[0].plot()
        
        # Process detections per zone
        for i, (box, track_id) in enumerate(zip(boxes, track_ids)):
            x, y, w, h = box
            center_x, center_y = int(x), int(y)
            detected_class = detected_classes[i] if i < len(detected_classes) else -1
            
            track = track_history[track_id]
            track.append((float(x), float(y)))
            if len(track) > 30:
                track.pop(0)
            
            for zd in zone_data:
                # Only check if detection matches any of zone's target classes
                if detected_class not in zd['class_ids']:
                    continue
                
                zone_id = zd['id']
                in_zone = False
                
                if zd['is_line']:
                    if len(track) >= 2:
                        prev_pos = track[-2]
                        curr_pos = track[-1]
                        line_pt1 = (int(zd['area'][0][0]), int(zd['area'][0][1]))
                        line_pt2 = (int(zd['area'][1][0]), int(zd['area'][1][1]))
                        in_zone = check_line_crossing(prev_pos, curr_pos, line_pt1, line_pt2)
                else:
                    result = cv2.pointPolygonTest(zd['area_np'], (center_x, center_y), False)
                    in_zone = result >= 0
                
                if in_zone:
                    if track_id not in crossed_objects_per_zone[zone_id]:
                        crossed_objects_per_zone[zone_id][track_id] = True
                    cv2.circle(frame, (center_x, center_y), 9, (244, 133, 66), -1)
                else:
                    if track_id in crossed_objects_per_zone[zone_id]:
                        cv2.circle(frame, (center_x, center_y), 9, (83, 168, 51), -1)
                    else:
                        cv2.circle(frame, (center_x, center_y), 9, (54, 67, 234), -1)
        
        # Draw zones
        for zd in zone_data:
            if zd['is_line']:
                pt1 = (int(zd['area'][0][0]), int(zd['area'][0][1]))
                pt2 = (int(zd['area'][1][0]), int(zd['area'][1][1]))
                cv2.line(frame, pt1, pt2, zd['color'], 3)
            else:
                cv2.polylines(frame, [zd['area_np']], True, zd['color'], 3)
        
        # Draw counts
        y_offset = int(height * 0.05)
        counts = {}
        for idx, zd in enumerate(zone_data):
            zone_id = zd['id']
            count = len(crossed_objects_per_zone.get(zone_id, {}))
            counts[zone_id] = count
            text_color = get_color_from_class_id(zd['class_ids'][0])  # Use first class for display color
            zone_label = zd.get('label', f'Zone {idx + 1}')
            count_text = f"{zone_label}: {count}"
            text_position = (int(width * 0.02), y_offset + int(idx * height * 0.05))
            cv2.putText(frame, count_text, text_position, font, font_scale, text_color, font_thickness)
        
        # Update global state with history and peaks (safely)
        if task_id not in _active_streams:
            break  # Stream was stopped, exit loop
            
        stream_state = _active_streams[task_id]
        stream_state['counts'] = counts
        
        # Record history snapshot (for rolling chart)
        elapsed_time = round(time.time() - stream_state['start_time'], 1)
        stream_state['history'].append({
            'time': elapsed_time,
            'counts': counts.copy()
        })
        
        # Keep only last 120 seconds of history (2 minutes)
        max_history_time = 120
        stream_state['history'] = [
            h for h in stream_state['history'] 
            if h['time'] > elapsed_time - max_history_time
        ]
        
        # Track peaks
        for zone_id, count in counts.items():
            if zone_id not in stream_state['peak_counts']:
                stream_state['peak_counts'][zone_id] = {'count': 0, 'time': 0}
            if count > stream_state['peak_counts'][zone_id]['count']:
                stream_state['peak_counts'][zone_id] = {'count': count, 'time': elapsed_time}
        
        # Encode as JPEG
        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        jpeg_bytes = jpeg.tobytes()
        
        yield jpeg_bytes, counts
    
    cap.release()
