import cv2
import os
import tempfile
import shutil
import colorsys
import time
import numpy as np
from collections import defaultdict
from ultralytics import YOLO

from app.services.gpu_utils import get_device, get_gpu_info

def get_color_from_class_id(class_id):
    """
    Generate a distinct color based on class ID using Golden Angle Approximation.
    Matches the frontend logic in zone.js.
    """
    hue = ((class_id * 137.508) % 360) / 360.0
    saturation = 0.85
    lightness = 0.55
    
    # colorsys.hls_to_rgb takes (h, l, s)
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
    
    # Convert to 0-255 and return as BGR (for OpenCV)
    return (int(b * 255), int(g * 255), int(r * 255))


def point_to_line_distance(point, line_start, line_end):
    """Calculate perpendicular distance from a point to a line segment."""
    px, py = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    # Line segment vector
    dx, dy = x2 - x1, y2 - y1
    
    # Handle degenerate case where line is a point
    if dx == 0 and dy == 0:
        return np.sqrt((px - x1)**2 + (py - y1)**2)
    
    # Parameter t for closest point on infinite line
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    
    # Closest point on the line segment
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    
    return np.sqrt((px - closest_x)**2 + (py - closest_y)**2)


def check_line_crossing(prev_pos, curr_pos, line_start, line_end):
    """
    Check if movement from prev_pos to curr_pos crosses the line segment.
    Returns: 1 = IN (crossed left-to-right), -1 = OUT (crossed right-to-left), 0 = no crossing
    """
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
    
    def cross_product(o, a, b):
        """Calculate cross product to determine which side of line a point is on."""
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    
    A, B = prev_pos, curr_pos
    C, D = line_start, line_end
    
    # Check if line segments intersect
    if ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D):
        # Crossed! Determine direction based on which side prev_pos was on
        cross = cross_product(C, D, A)
        return 1 if cross > 0 else -1  # 1=IN (left to right), -1=OUT (right to left)
    return 0


def detection(path_x, zones, frame_size, taskID, conf=40, model_name='yolo11n.pt', tracker_config=None):
    """
    Process video with multiple detection zones.
    
    Args:
        path_x: Path to source video
        zones: List of zone objects [{id, points, classId, color}, ...]
        frame_size: Tuple of (width, height)
        taskID: Task identifier for output file naming
        conf: Confidence threshold (1-100)
        model_name: Name of the YOLO model file (default: yolo11n.pt)
        tracker_config: ByteTrack configuration dict
    """
    # Default tracker config
    if tracker_config is None:
        tracker_config = {
            'track_high_thresh': 0.45,
            'track_low_thresh': 0.1,
            'match_thresh': 0.8,
            'track_buffer': 30
        }
    
    # Generate custom ByteTrack YAML using a temporary file
    tracker_yaml_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    tracker_yaml_path = tracker_yaml_file.name
    
    tracker_yaml_content = f"""# Custom ByteTrack config for task {taskID}
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

    try:
        yield from _run_detection(path_x, zones, frame_size, taskID, conf, model_name, tracker_yaml_path)
    finally:
        if os.path.exists(tracker_yaml_path):
            os.remove(tracker_yaml_path)
    
# Heatmap resolution constant
HEATMAP_RESOLUTION = 50

def _run_detection(path_x, zones, frame_size, taskID, conf, model_name, tracker_yaml_path):
    # Constants
    SOURCE_VIDEO = path_x
    DESTIN_VIDEO = 'uploads/outputs/' + 'output_' + taskID + '.mp4'

    font = cv2.FONT_ITALIC
    frame_counter = 0
    track_history = defaultdict(lambda: [])
    
    # Initialize heatmap grid for activity visualization
    heatmap_grid = np.zeros((HEATMAP_RESOLUTION, HEATMAP_RESOLUTION), dtype=np.float32)
    
    # Per-zone tracking: {zone_id: {track_id: {'in_zone': True/False, 'entry_time': timestamp}}}
    crossed_objects_per_zone = {z['id']: {} for z in zones}
    
    # Detection events for each zone
    detection_events = []
    
    # Dwell time events: [{zone_id, track_id, duration}]
    dwell_events = []
    
    # Line crossing counts: {zone_id: {'in': count, 'out': count}} for line zones
    line_crossing_counts = {z['id']: {'in': 0, 'out': 0} for z in zones if len(z.get('points', [])) == 2}

    width = frame_size[0]
    height = frame_size[1]

    BASE_FONT_SIZE = 1.2
    font_scale = min(width, height) / 1000 * BASE_FONT_SIZE
    BASE_FONT_THICKNESS = 2
    font_thickness = max(1, max(width, height) // 1000 * BASE_FONT_THICKNESS)

    model_path = f"weights/{model_name}"
    
    # Check if model exists in weights folder
    if not os.path.exists(model_path):
        print(f"Model {model_name} not found in weights/. Attempting auto-download...")
        try:
            # Download to current directory (default YOLO behavior)
            temp_model = YOLO(model_name) 
            
            # YOLO downloads to current directory
            if os.path.exists(model_name):
                os.makedirs("weights", exist_ok=True)
                shutil.move(model_name, model_path)
                print(f"Moved {model_name} to {model_path}")
                
            model = YOLO(model_path)
        except Exception as e:
            print(f"Failed to auto-download {model_name}: {e}. Falling back to yolo11n.pt")
            model = YOLO('weights/yolo11n.pt')
    else:
        model = YOLO(model_path)
    
    # Set device for GPU acceleration
    device = get_device()
    gpu_info = get_gpu_info()
    print(f"Using device: {device} ({gpu_info['name']})")

    cap = cv2.VideoCapture(SOURCE_VIDEO)

    targetFPS = 24
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    newFPS = targetFPS if fps > targetFPS else fps
    interval = fps / newFPS
    
    process_idx = 0
    
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(DESTIN_VIDEO, fourcc, newFPS, (width, height))
    
    if not out.isOpened():
        print("Failed to open video writer with avc1, falling back to mp4v")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(DESTIN_VIDEO, fourcc, newFPS, (width, height))
        
    if not out.isOpened():
        print("Failed to open video writer with mp4v")
        # Handle failure appropriately, maybe raise exception or continue without video
    
    start_time = time.time()

    # Preprocess zones
    zone_data = []
    all_class_ids = set()
    for zone in zones:
        points = zone.get('points', [])
        if len(points) < 2:
            continue
            
        # Convert points to proper format
        area = [(p['x'], p['y']) for p in points]
        area_np = np.array(area, np.int32)
        
        class_ids = zone.get('classIds', [19])  # Array of class IDs
        for class_id in class_ids:
            all_class_ids.add(class_id)
        
        # Get color from zone (already in RGB from frontend)
        zone_color = zone.get('color', [255, 255, 0])
        # Convert to BGR for OpenCV
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
    
    # Convert class IDs to list for YOLO
    ClassIDs = list(all_class_ids) if all_class_ids else [19]

    while cap.isOpened():
        
        target_frame_idx = round(interval * process_idx)
        
        # If the current frame matches the target frame 
        if (frame_counter + 1) != target_frame_idx:
             # If we passed the target (should process next)
             if (frame_counter + 1) > target_frame_idx:
                 process_idx += 1
                 target_frame_idx = round(interval * process_idx)
             
             if (frame_counter + 1) != target_frame_idx:
                success = cap.grab()
                if not success:
                    break
                frame_counter += 1
                continue
        
        # Target frame reached
        process_idx += 1
        success, frame = cap.read()
        
        if not success:
            break
        
        frame_counter += 1

        # Normalize confidence to 0.0-1.0 range
        conf_float = conf / 100.0
        results = model.track(frame, classes=ClassIDs, persist=True, save=False, tracker=tracker_yaml_path, conf=conf_float, device=device)
        boxes = results[0].boxes.xywh.cpu()
        track_ids = results[0].boxes.id.int().cpu().tolist() if results[0].boxes is not None and results[0].boxes.id is not None else []
        detected_classes = results[0].boxes.cls.int().cpu().tolist() if results[0].boxes is not None else []

        frame = results[0].plot()

        center_x, center_y = 0, 0
        
        # Process each detection
        for i, (box, track_id) in enumerate(zip(boxes, track_ids)):
            x, y, w, h = box
            center_x, center_y = int(x), int(y)
            detected_class = detected_classes[i] if i < len(detected_classes) else -1
            
            track = track_history[track_id]
            track.append((float(x), float(y)))
            if len(track) > 30:
                track.pop(0)
            
            # Update heatmap grid with object position
            grid_x = int((center_x / width) * HEATMAP_RESOLUTION)
            grid_y = int((center_y / height) * HEATMAP_RESOLUTION)
            grid_x = min(max(grid_x, 0), HEATMAP_RESOLUTION - 1)
            grid_y = min(max(grid_y, 0), HEATMAP_RESOLUTION - 1)
            heatmap_grid[grid_y, grid_x] += 1
            
            # Track object status across all zones to determine dot color
            is_active_in_any_zone = False
            is_counted_in_any_zone = False
            matches_any_zone_class = False

            # Check each zone
            for zd in zone_data:
                # Only check if detection matches any of zone's target classes
                if detected_class not in zd['class_ids']:
                    continue
                
                matches_any_zone_class = True
                zone_id = zd['id']
                
                # Check if object is in zone (different logic for line vs polygon)
                in_zone = False
                crossing_direction = 0
                
                if zd['is_line']:
                    # For 2-point line: check if object crosses the line
                    if len(track) >= 2:
                        prev_pos = track[-2]
                        curr_pos = track[-1]
                        line_pt1 = (int(zd['area'][0][0]), int(zd['area'][0][1]))
                        line_pt2 = (int(zd['area'][1][0]), int(zd['area'][1][1]))
                        crossing_direction = check_line_crossing(prev_pos, curr_pos, line_pt1, line_pt2)
                        
                        # For line zones, process crossing event
                        if crossing_direction != 0:
                            timestamp = round(frame_counter / fps, 2)
                            
                            # Check if this track already crossed in this direction
                            track_data = crossed_objects_per_zone[zone_id].get(track_id, {})
                            last_direction = track_data.get('last_direction', 0)
                            
                            # Only count if this is a new crossing (not same direction as last)
                            if last_direction != crossing_direction:
                                crossed_objects_per_zone[zone_id][track_id] = {
                                   'last_direction': crossing_direction,
                                    'timestamp': timestamp,
                                    'counted': True,
                                    'class_id': detected_class  # Store class
                                }
                                
                                # Update IN/OUT counts
                                if crossing_direction > 0:
                                    line_crossing_counts[zone_id]['in'] += 1
                                else:
                                    line_crossing_counts[zone_id]['out'] += 1
                                
                                # Log detection event with direction info
                                lc = line_crossing_counts[zone_id]
                                
                                # Calculate per-class counts
                                class_counts = {}
                                for track_data in crossed_objects_per_zone[zone_id].values():
                                    cls_id = track_data.get('class_id', -1)
                                    class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
                                
                                detection_events.append({
                                    "time": timestamp,
                                    "zone_id": zone_id,
                                    "class_id": zd['class_ids'][0],  # Use first class for event logging
                                    "class_counts": class_counts,  # Per-class breakdown
                                    "count": lc['in'] + lc['out'],
                                    "in_count": lc['in'],
                                    "out_count": lc['out'],
                                    "direction": "in" if crossing_direction > 0 else "out"
                                })
                            
                            # Mark as currently crossing (contributes to Blue status)
                            is_active_in_any_zone = True
                        else:
                            # Not crossing - check if previously counted (contributes to Green status)
                            if track_id in crossed_objects_per_zone[zone_id]:
                                is_counted_in_any_zone = True
                    continue  # Skip polygon logic for line zones
                else:
                    # For 3+ point polygon: use standard containment test
                    result = cv2.pointPolygonTest(zd['area_np'], ((center_x, center_y)), False)
                    in_zone = result >= 0

                timestamp = round(frame_counter / fps, 2)
                
                if in_zone:
                    if track_id not in crossed_objects_per_zone[zone_id]:
                        # First entry - track entry time
                        crossed_objects_per_zone[zone_id][track_id] = {
                            'in_zone': True,
                            'entry_time': timestamp,
                            'counted': True,
                            'class_id': detected_class  # Store class for per-class counting
                        }
                        # Log detection event with per-class breakdown
                        class_counts = {}
                        for track_data in crossed_objects_per_zone[zone_id].values():
                            cls_id = track_data.get('class_id', -1)
                            class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
                        
                        detection_events.append({
                            "time": timestamp,
                            "zone_id": zone_id,
                            "class_id": zd['class_ids'][0],  # Use first class for event logging
                            "class_counts": class_counts,  # Per-class breakdown
                            "count": len(crossed_objects_per_zone[zone_id])
                        })
                    elif not crossed_objects_per_zone[zone_id][track_id].get('in_zone', False):
                        # Re-entering zone
                        crossed_objects_per_zone[zone_id][track_id]['in_zone'] = True
                        crossed_objects_per_zone[zone_id][track_id]['entry_time'] = timestamp
                        
                    # Currently in zone -> Active (Blue)
                    is_active_in_any_zone = True

                else:
                    if track_id in crossed_objects_per_zone[zone_id]:
                        obj_data = crossed_objects_per_zone[zone_id][track_id]
                        if obj_data.get('in_zone', False):
                            # Object just exited - calculate dwell time
                            entry_time = obj_data.get('entry_time', timestamp)
                            dwell_duration = round(timestamp - entry_time, 2)
                            if dwell_duration > 0:
                                dwell_events.append({
                                    'zone_id': zone_id,
                                    'track_id': track_id,
                                    'entry_time': entry_time,
                                    'exit_time': timestamp,
                                    'duration': dwell_duration
                                })
                            obj_data['in_zone'] = False
                        
                        if obj_data.get('counted', False):
                            is_counted_in_any_zone = True
            
            # Draw dot based on priority: Active (Blue) > Counted (Green) > Detected (Red)
            if is_active_in_any_zone:
                cv2.circle(frame, (center_x, center_y), 9, (244, 133, 66), -1) # Blue (Active)
            elif is_counted_in_any_zone:
                cv2.circle(frame, (center_x, center_y), 9, (83, 168, 51), -1) # Green (Counted)
            elif matches_any_zone_class:
                cv2.circle(frame, (center_x, center_y), 9, (54, 67, 234), -1) # Red (Not Counted but Matched Class)

        # Draw all zones
        for zd in zone_data:
            if zd['is_line']:
                pt1 = (int(zd['area'][0][0]), int(zd['area'][0][1]))
                pt2 = (int(zd['area'][1][0]), int(zd['area'][1][1]))
                cv2.line(frame, pt1, pt2, zd['color'], 3)
            else:
                cv2.polylines(frame, [zd['area_np']], True, zd['color'], 3)
        
        # Draw count text for each zone (stacked vertically)
        y_offset = int(height * 0.05)
        for idx, zd in enumerate(zone_data):
            zone_id = zd['id']
            text_color = get_color_from_class_id(zd['class_ids'][0])  # Use first class for display color
            
            # Zone label with count
            zone_label = zd.get('label', f'Zone {idx + 1}')
            
            # Different display for line zones vs polygon zones
            if zd['is_line'] and zone_id in line_crossing_counts:
                lc = line_crossing_counts[zone_id]
                count_text = f"{zone_label}: IN {lc['in']} | OUT {lc['out']}"
            else:
                count = len(crossed_objects_per_zone.get(zone_id, {}))
                count_text = f"{zone_label}: {count}"
            
            text_position = (int(width * 0.02), y_offset + int(idx * height * 0.05))
            cv2.putText(frame, count_text, text_position, font, font_scale, text_color, font_thickness)
        
        # Only resize if necessary
        if frame.shape[1] != width or frame.shape[0] != height:
             frame = cv2.resize(frame, (width, height))
             
        out.write(frame)
        
        # Calculate progress percentage
        progress = int((frame_counter / total_frames) * 100) if total_frames > 0 else 0
        
        if success:
            # Convert heatmap grid to list for JSON serialization
            heatmap_data = heatmap_grid.tolist()
            yield frame, progress, detection_events, dwell_events, line_crossing_counts, heatmap_data
        else:
            break
        
    cap.release()
    out.release()
    end_time = time.time()
    process_time = end_time - start_time
    print("Processing time:", process_time, "seconds")
