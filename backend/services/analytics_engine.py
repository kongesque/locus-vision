"""
Shared analytics engine for zone-based object counting and tracking.

Used by video processing (offline) and live streams.
Wraps the ONNX detector and adds stateful zone-aware counting logic.
"""

import cv2
import numpy as np
import supervision as sv
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from services.onnx_detector import get_detector, OnnxDetector
import time


@dataclass
class AnalyticsResult:
    """Result from a single frame analysis."""
    boxes: list          # List of box dicts {id, x, y, w, h, class, conf, label, in_zone}
    total_count: int     # Total unique objects that have entered any zone
    zone_counts: dict    # {zone_id: count}
    resolution: dict     # {w, h}
    # New event fields for DuckDB/WS integration
    zone_events: list = field(default_factory=list)
    line_events: list = field(default_factory=list)
    track_events: list = field(default_factory=list)
    alerts: list = field(default_factory=list)


@dataclass
class ParsedZone:
    """Pre-parsed zone polygon for efficient per-frame checking."""
    poly_rel: np.ndarray  # Relative points [0.0 - 1.0]
    color: tuple
    zone_id: str
    classes: list  # List of class IDs to filter (empty = all)
    zone_type: str = "polygon"  # 'polygon' or 'line'
    direction: str = "both"  # 'both', 'in', or 'out' (line zones only)
    capacity: int = 100 # Added for capacity alerts
    poly: Optional[np.ndarray] = None  # Absolute pixel coordinates calculated per frame


class AnalyticsEngine:
    """
    Stateful per-session analytics engine.
    """

    @staticmethod
    def _ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

    @staticmethod
    def _segments_intersect(A, B, C, D) -> bool:
        return AnalyticsEngine._ccw(A, C, D) != AnalyticsEngine._ccw(B, C, D) and \
               AnalyticsEngine._ccw(A, B, C) != AnalyticsEngine._ccw(A, B, D)

    @staticmethod
    def _cross_sign(A, B, C, D) -> int:
        ldx = D[0] - C[0]
        ldy = D[1] - C[1]
        mid = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
        cross = ldx * (mid[1] - C[1]) - ldy * (mid[0] - C[0])
        if cross > 0: return 1   # "in"
        elif cross < 0: return -1  # "out"
        return 0

    def __init__(self, model_name: str = "yolo11n", zones: list = None, full_frame_classes: list = None, mode: str = "live", camera_id: str = "default", conf_threshold: float | None = None):
        self.detector: OnnxDetector = get_detector(model_name, conf_threshold=conf_threshold)
        self.mode = mode
        self.camera_id = camera_id
        
        self.tracker = sv.ByteTrack(
            track_activation_threshold=self.detector.conf_threshold,
            minimum_matching_threshold=0.8,
            frame_rate=30,
        )
        
        self.track_history: dict[int, list] = {}
        self.crossed_objects: dict[int, bool] = {}
        self.zone_crossed_objects: dict[str, set[int]] = {}
        self.parsed_zones: list[ParsedZone] = []
        self.full_frame_class_ids: list[int] = []
        
        # New timestamp tracking
        self.last_seen: dict[int, float] = {}
        self.zone_entry_times: dict[int, dict[str, float]] = {}  # track_id -> {zone_id: timestamp}
        self.object_classes: dict[int, int] = {} # track_id -> class_id

        if zones:
            self.set_zones(zones)
        if full_frame_classes:
            self.full_frame_class_ids = self._get_class_ids(full_frame_classes)
            
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        self.motion_threshold_pixels = 500
        self.last_result: Optional[AnalyticsResult] = None

    def set_zones(self, zones: list):
        self.parsed_zones = []
        for zone in zones:
            points = zone.get("points", [])
            if len(points) < 2: continue
            
            pts_rel = np.array([[p['x'], p['y']] for p in points], dtype=np.float32)
            z_type = zone.get("type", "polygon")
            if z_type == "polygon" and len(pts_rel) < 3: continue
                
            self.parsed_zones.append(ParsedZone(
                poly_rel=pts_rel,
                color=self._parse_color(zone.get("color", "#00ff00")),
                zone_id=zone.get("id", ""),
                classes=self._get_class_ids(zone.get("classes", [])),
                zone_type=z_type,
                direction=zone.get("direction", "both"),
                capacity=zone.get("capacity", 100)
            ))
            self.zone_crossed_objects[zone.get("id", "")] = set()

    def reset(self):
        self.track_history.clear()
        self.crossed_objects.clear()
        self.last_seen.clear()
        self.zone_entry_times.clear()
        self.object_classes.clear()
        for v in self.zone_crossed_objects.values():
            v.clear()
        self.tracker = sv.ByteTrack(
            track_activation_threshold=self.detector.conf_threshold,
            minimum_matching_threshold=0.8,
            frame_rate=30,
        )
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        self.last_result = None

    def _garbage_collect(self, current_time: float):
        """Purge state for objects not seen recently to prevent memory leaks in live mode."""
        if self.mode != "live":
            return
            
        timeout = 10.0 # seconds
        expired_tracks = [tid for tid, ts in self.last_seen.items() if current_time - ts > timeout]
        
        for tid in expired_tracks:
            # Emit zone exit events before deleting if they were inside
            if tid in self.zone_entry_times:
                for z_id, entry_ts in self.zone_entry_times[tid].items():
                    dwell = current_time - entry_ts
                    # Handled by caller to emit exit event if we want, but for GC we just clean up
            
            self.track_history.pop(tid, None)
            self.crossed_objects.pop(tid, None)
            self.last_seen.pop(tid, None)
            self.zone_entry_times.pop(tid, None)
            self.object_classes.pop(tid, None)
            for z_id in self.zone_crossed_objects:
                self.zone_crossed_objects[z_id].discard(tid)

    def process_frame(self, frame: np.ndarray, scale: float = 1.0, current_time: Optional[float] = None) -> AnalyticsResult:
        if current_time is None:
            current_time = time.time()
            
        self._garbage_collect(current_time)

        h, w = frame.shape[:2]
        for z in self.parsed_zones:
            z.poly = (z.poly_rel * [w, h]).astype(np.int32)

        small_frame = cv2.resize(frame, (640, int(640 * (h / w))))
        fg_mask = self.bg_subtractor.apply(small_frame)
        fg_mask = cv2.erode(fg_mask, None, iterations=1)
        fg_mask = cv2.dilate(fg_mask, None, iterations=2)
        motion_pixels = cv2.countNonZero(fg_mask)
        
        if motion_pixels < self.motion_threshold_pixels and self.last_result is not None:
            # Update dwell times even without motion
            for box in self.last_result.boxes:
                tid = box["id"]
                if tid in self.zone_entry_times:
                    for z_id, entry_ts in self.zone_entry_times[tid].items():
                        box["dwell_time"] = current_time - entry_ts
            return self.last_result

        classes_arg = self._compute_required_classes()
        detections = self.detector.get_detections(frame, classes=classes_arg)
        tracked = self.tracker.update_with_detections(detections)

        boxes_data = []
        zone_events = []
        line_events = []
        track_events = []
        alerts = []
        
        # Track current frame's capacity per zone to emit alerts
        current_zone_occupancy = {z.zone_id: 0 for z in self.parsed_zones if z.zone_type == "polygon"}

        if len(tracked) > 0 and tracked.tracker_id is not None:
            boxes_xyxy = tracked.xyxy
            track_ids = tracked.tracker_id
            class_ids = tracked.class_id
            scores = tracked.confidence

            for box_xyxy, track_id, cls_idx, conf in zip(
                boxes_xyxy, track_ids, class_ids, scores
            ):
                cls_idx = int(cls_idx)
                track_id = int(track_id)
                self.last_seen[track_id] = current_time
                self.object_classes[track_id] = cls_idx

                if self.full_frame_class_ids and cls_idx not in self.full_frame_class_ids:
                    continue
                
                inv_scale = 1.0 / scale
                bw = float(box_xyxy[2] - box_xyxy[0]) * inv_scale
                bh = float(box_xyxy[3] - box_xyxy[1]) * inv_scale
                cx = float((box_xyxy[0] + box_xyxy[2]) / 2) * inv_scale
                cy = float((box_xyxy[1] + box_xyxy[3]) / 2) * inv_scale
                center = (int(cx), int(cy))

                track = self.track_history.setdefault(track_id, [])
                track.append(center)
                if len(track) > 30:
                    track.pop(0)
                    
                # Track event for spaghetti map (batch mode) or just raw location (live mode)
                track_events.append({
                    "timestamp": current_time,
                    "camera_id": self.camera_id,
                    "track_id": track_id,
                    "class_id": cls_idx,
                    "x": float(cx),
                    "y": float(cy)
                })

                in_zone = False
                in_zones = [] # Keep track of which zones we are currently inside
                max_dwell = 0.0

                if self.parsed_zones:
                    for zone in self.parsed_zones:
                        if zone.classes and cls_idx not in zone.classes:
                            continue
                        
                        if zone.zone_type == "polygon":
                            dist = cv2.pointPolygonTest(zone.poly, center, False)
                            if dist >= 0:
                                in_zone = True
                                in_zones.append(zone.zone_id)
                                current_zone_occupancy[zone.zone_id] += 1
                                
                                # Zone Entry Logic
                                if track_id not in self.zone_entry_times:
                                    self.zone_entry_times[track_id] = {}
                                    
                                if zone.zone_id not in self.zone_entry_times[track_id]:
                                    self.zone_entry_times[track_id][zone.zone_id] = current_time
                                    zone_events.append({
                                        "timestamp": current_time,
                                        "camera_id": self.camera_id,
                                        "zone_id": zone.zone_id,
                                        "event_type": "enter",
                                        "track_id": track_id,
                                        "dwell_time": 0.0
                                    })
                                
                                dwell = current_time - self.zone_entry_times[track_id][zone.zone_id]
                                max_dwell = max(max_dwell, dwell)

                                if track_id not in self.crossed_objects:
                                    self.crossed_objects[track_id] = True
                                self.zone_crossed_objects[zone.zone_id].add(track_id)
                                
                        elif zone.zone_type == "line":
                            if len(zone.poly) >= 2 and len(track) >= 2:
                                p1 = track[-2]
                                p2 = track[-1]
                                line_start = tuple(zone.poly[0])
                                line_end = tuple(zone.poly[-1])
                                if AnalyticsEngine._segments_intersect(p1, p2, line_start, line_end):
                                    sign = AnalyticsEngine._cross_sign(p1, p2, line_start, line_end)
                                    crossed_dir = "in" if sign > 0 else "out" if sign < 0 else "unknown"
                                    
                                    # Directional anomaly check
                                    if zone.direction != "both" and crossed_dir != "unknown" and crossed_dir != zone.direction:
                                        alerts.append({
                                            "type": "wrong_way",
                                            "message": f"Wrong way traversal detected on line {zone.zone_id}",
                                            "zone_id": zone.zone_id,
                                            "timestamp": current_time
                                        })
                                        
                                    line_events.append({
                                        "timestamp": current_time,
                                        "camera_id": self.camera_id,
                                        "line_id": zone.zone_id,
                                        "direction": crossed_dir,
                                        "track_id": track_id
                                    })
                                    
                                    in_zone = True
                                    if track_id not in self.crossed_objects:
                                        self.crossed_objects[track_id] = True
                                    self.zone_crossed_objects[zone.zone_id].add(track_id)
                                    
                # Zone Exit Logic
                if track_id in self.zone_entry_times:
                    exited_zones = [z for z in self.zone_entry_times[track_id] if z not in in_zones]
                    for z_id in exited_zones:
                        entry_time = self.zone_entry_times[track_id].pop(z_id)
                        dwell = current_time - entry_time
                        zone_events.append({
                            "timestamp": current_time,
                            "camera_id": self.camera_id,
                            "zone_id": z_id,
                            "event_type": "exit",
                            "track_id": track_id,
                            "dwell_time": dwell
                        })

                if not self.parsed_zones:
                    if track_id not in self.crossed_objects:
                        self.crossed_objects[track_id] = True

                boxes_data.append({
                    "id": track_id,
                    "x": float((cx - bw / 2) * scale),
                    "y": float((cy - bh / 2) * scale),
                    "w": float(bw * scale),
                    "h": float(bh * scale),
                    "class": cls_idx,
                    "conf": round(float(conf), 2),
                    "label": self.detector.names.get(cls_idx, f"class_{cls_idx}"),
                    "in_zone": in_zone,
                    "is_counted": track_id in self.crossed_objects,
                    "dwell_time": max_dwell
                })
                
        # Handle objects that completely disappeared (missed by YOLO for a bit)
        if len(tracked) == 0 or tracked.tracker_id is None:
            # We don't GC them immediately unless they timeout, but we could mark exit if they are missing
            pass
            
        # Capacity Alerts
        for zone in self.parsed_zones:
            if zone.zone_type == "polygon":
                occ = current_zone_occupancy[zone.zone_id]
                cap = zone.capacity
                if occ > cap * 0.8:
                    alerts.append({
                        "type": "capacity_warning",
                        "message": f"Zone {zone.zone_id} is at {occ}/{cap} capacity",
                        "zone_id": zone.zone_id,
                        "timestamp": current_time
                    })

        final_result = AnalyticsResult(
            boxes=boxes_data,
            total_count=len(self.crossed_objects),
            zone_counts={z_id: len(objs) for z_id, objs in self.zone_crossed_objects.items()},
            resolution={"w": w, "h": h},
            zone_events=zone_events,
            line_events=line_events,
            track_events=track_events,
            alerts=alerts
        )
        
        self.last_result = final_result
        return final_result

    def draw_annotations(self, frame: np.ndarray, result: AnalyticsResult):
        for zone in self.parsed_zones:
            if zone.zone_type == "polygon":
                overlay = frame.copy()
                cv2.fillPoly(overlay, [zone.poly], zone.color)
                cv2.addWeighted(overlay, 0.1, frame, 0.9, 0, frame)

            dash_length = 10
            gap_length = 5
            pts = zone.poly
            num_pts = len(pts)
            
            segments = num_pts if zone.zone_type == "polygon" else num_pts - 1
            
            for i in range(segments):
                pt1 = tuple(pts[i])
                pt2 = tuple(pts[(i + 1) % num_pts])
                dx = pt2[0] - pt1[0]
                dy = pt2[1] - pt1[1]
                dist = np.sqrt(dx**2 + dy**2)
                
                if dist == 0: continue
                    
                dx_norm = dx / dist
                dy_norm = dy / dist
                
                curr_dist = 0
                while curr_dist < dist:
                    start_x = int(pt1[0] + dx_norm * curr_dist)
                    start_y = int(pt1[1] + dy_norm * curr_dist)
                    
                    curr_dist = min(curr_dist + dash_length, dist)
                    end_x = int(pt1[0] + dx_norm * curr_dist)
                    end_y = int(pt1[1] + dy_norm * curr_dist)
                    
                    cv2.line(frame, (start_x, start_y), (end_x, end_y), zone.color, 2)
                    curr_dist += gap_length

        for box in result.boxes:
            x1, y1 = int(box["x"]), int(box["y"])
            x2, y2 = int(box["x"] + box["w"]), int(box["y"] + box["h"])
            track_id = box["id"]

            if box["in_zone"]: color = (0, 140, 255)
            elif track_id in self.crossed_objects: color = (0, 200, 0)
            else: color = (0, 0, 255)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            dwell = box.get("dwell_time", 0.0)
            dwell_str = f" {dwell:.1f}s" if dwell > 0 else ""
            label = f"{box['label']} #{track_id}{dwell_str}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 8, y1), color, -1)
            cv2.putText(frame, label, (x1 + 4, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        y_offset = 40
        if not self.parsed_zones:
            count_text = f"Count: {result.total_count}"
            cv2.putText(frame, count_text, (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(frame, count_text, (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            for zone in self.parsed_zones:
                zone_count = result.zone_counts.get(zone.zone_id, 0)
                label_text = f"Zone {zone.zone_id[:8]}: {zone_count}" if len(zone.zone_id) > 8 else f"{zone.zone_id}: {zone_count}"
                
                cv2.putText(frame, label_text, (20, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(frame, label_text, (20, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, zone.color, 2, cv2.LINE_AA)
                
                y_offset += 40

    def _get_class_ids(self, class_names: list[str]) -> list[int]:
        if not class_names: return []
        name_to_id = {v: k for k, v in self.detector.names.items()}
        return [name_to_id[n] for n in class_names if n in name_to_id]

    def _compute_required_classes(self) -> list[int] | None:
        if self.full_frame_class_ids:
            return self.full_frame_class_ids
            
        required = set()
        for zone in self.parsed_zones:
            if not zone.classes: return None
            required.update(zone.classes)
        return list(required) if required else None

    @staticmethod
    def _parse_color(hex_color: str) -> tuple:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return (b, g, r)
        return (0, 255, 0)
