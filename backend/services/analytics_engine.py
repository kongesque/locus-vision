"""
Shared analytics engine for zone-based object counting and tracking.

Used by video processing (offline).
Wraps the ONNX detector and adds stateful zone-aware counting logic.
"""

import cv2
import numpy as np
import supervision as sv
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from services.onnx_detector import get_detector, OnnxDetector


@dataclass
class AnalyticsResult:
    """Result from a single frame analysis."""
    boxes: list          # List of box dicts {id, x, y, w, h, class, conf, label, in_zone}
    total_count: int     # Total unique objects that have entered any zone
    zone_counts: dict    # {zone_id: count}
    resolution: dict     # {w, h}


@dataclass
class ParsedZone:
    """Pre-parsed zone polygon for efficient per-frame checking."""
    poly_rel: np.ndarray  # Relative points [0.0 - 1.0]
    color: tuple
    zone_id: str
    classes: list  # List of class IDs to filter (empty = all)
    zone_type: str = "polygon"  # 'polygon' or 'line'
    direction: str = "both"  # 'both', 'in', or 'out' (line zones only)
    poly: Optional[np.ndarray] = None  # Absolute pixel coordinates calculated per frame


class AnalyticsEngine:
    """
    Stateful per-session analytics engine.

    Maintains tracking state across frames:
    - Track history (last 30 positions per object)
    - Crossed objects (unique IDs that entered any zone)
    - Per-zone class filtering
    """

    @staticmethod
    def _ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

    @staticmethod
    def _segments_intersect(A, B, C, D) -> bool:
        """Return True if line segment AB intersects CD."""
        return AnalyticsEngine._ccw(A, C, D) != AnalyticsEngine._ccw(B, C, D) and \
               AnalyticsEngine._ccw(A, B, C) != AnalyticsEngine._ccw(A, B, D)

    @staticmethod
    def _cross_sign(A, B, C, D) -> int:
        """
        Return the sign of the cross product of line CD with movement AB.
        Positive = crossing from left to right ("in"), Negative = right to left ("out").
        """
        # Line direction vector
        ldx = D[0] - C[0]
        ldy = D[1] - C[1]
        # Movement midpoint relative to line start
        mid = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
        # Cross product: line_dir × (midpoint - line_start)
        cross = ldx * (mid[1] - C[1]) - ldy * (mid[0] - C[0])
        if cross > 0:
            return 1   # "in"
        elif cross < 0:
            return -1  # "out"
        return 0

    def __init__(self, model_name: str = "yolo11n", zones: list = None, full_frame_classes: list = None):
        self.detector: OnnxDetector = get_detector(model_name)
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

        if zones:
            self.set_zones(zones)
        if full_frame_classes:
            self.full_frame_class_ids = self._get_class_ids(full_frame_classes)
            
        # Motion detection optimization
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        self.motion_threshold_pixels = 500  # Minimum moving pixels to trigger YOLO
        self.last_result: Optional[AnalyticsResult] = None  # Cache previous valid result if no motion

    def set_zones(self, zones: list):
        """Parse zone definitions into efficient polygon structures."""
        self.parsed_zones = []
        for zone in zones:
            points = zone.get("points", [])
            if len(points) < 2:
                continue
            
            # Points are now expected to be relative [0.0 - 1.0] from frontend
            pts_rel = np.array([[p['x'], p['y']] for p in points], dtype=np.float32)
            
            # Require at least 3 points for a polygon, 2 for a line
            z_type = zone.get("type", "polygon")
            if z_type == "polygon" and len(pts_rel) < 3:
                continue
                
            self.parsed_zones.append(ParsedZone(
                poly_rel=pts_rel,
                color=self._parse_color(zone.get("color", "#00ff00")),
                zone_id=zone.get("id", ""),
                classes=self._get_class_ids(zone.get("classes", [])),
                zone_type=z_type,
                direction=zone.get("direction", "both")
            ))
            self.zone_crossed_objects[zone.get("id", "")] = set()

    def reset(self):
        """Reset all tracking state (call between different sources)."""
        self.track_history.clear()
        self.crossed_objects.clear()
        for v in self.zone_crossed_objects.values():
            v.clear()
        self.tracker = sv.ByteTrack(
            track_activation_threshold=self.detector.conf_threshold,
            minimum_matching_threshold=0.8,
            frame_rate=30,
        )
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        self.last_result = None

    def process_frame(self, frame: np.ndarray, scale: float = 1.0) -> AnalyticsResult:
        """
        Run detection + tracking + zone counting on a single frame.
        `scale` indicates how much the frame was resized before passing in.
        Returns an AnalyticsResult with boxes, counts, and resolution.
        """
        h, w = frame.shape[:2]

        # Ensure absolute polygons are scaled to current frame size
        for z in self.parsed_zones:
            z.poly = (z.poly_rel * [w, h]).astype(np.int32)

        # 1. Motion Detection Stage
        # Resize frame for faster motion detection (MOG2 is CPU bound)
        small_frame = cv2.resize(frame, (640, int(640 * (h / w))))
        fg_mask = self.bg_subtractor.apply(small_frame)
        
        # Clean up noise
        fg_mask = cv2.erode(fg_mask, None, iterations=1)
        fg_mask = cv2.dilate(fg_mask, None, iterations=2)
        
        motion_pixels = cv2.countNonZero(fg_mask)
        
        # If no significant motion is detected and we have a previous result, return it
        if motion_pixels < self.motion_threshold_pixels and self.last_result is not None:
            # We don't want to count a stationary object multiple times or advance its track history
            # Just return the visual boxes so the UI doesn't stutter/flicker
            return self.last_result

        # 2. Object Detection Stage (Only runs if motion is detected)
        # Determine which classes to track
        classes_arg = self._compute_required_classes()

        # Run ONNX detection + ByteTrack tracking
        detections = self.detector.get_detections(frame, classes=classes_arg)
        tracked = self.tracker.update_with_detections(detections)

        boxes_data = []

        if len(tracked) > 0 and tracked.tracker_id is not None:
            boxes_xyxy = tracked.xyxy
            track_ids = tracked.tracker_id
            class_ids = tracked.class_id
            scores = tracked.confidence

            for box_xyxy, track_id, cls_idx, conf in zip(
                boxes_xyxy, track_ids, class_ids, scores
            ):
                cls_idx = int(cls_idx)
                
                # Master Global Filter: If the user explicitly restricted the overarching camera classes, 
                # ignore any detection that doesn't match, regardless of zone configurations.
                if self.full_frame_class_ids and cls_idx not in self.full_frame_class_ids:
                    continue
                
                # Scale the YOLO boxes back up to the original high-res camera dimensions
                # before testing against `zone.poly` (which was drawn on the high-res frame).
                inv_scale = 1.0 / scale
                bw = float(box_xyxy[2] - box_xyxy[0]) * inv_scale
                bh = float(box_xyxy[3] - box_xyxy[1]) * inv_scale
                cx = float((box_xyxy[0] + box_xyxy[2]) / 2) * inv_scale
                cy = float((box_xyxy[1] + box_xyxy[3]) / 2) * inv_scale
                center = (int(cx), int(cy))

                # Update track history
                track = self.track_history.setdefault(track_id, [])
                track.append(center)
                if len(track) > 30:
                    track.pop(0)

                # Check zone membership
                in_zone = False
                if self.parsed_zones:
                    for zone in self.parsed_zones:
                        # Class filter: if zone specifies classes, skip non-matching
                        if zone.classes and cls_idx not in zone.classes:
                            continue
                        
                        if zone.zone_type == "polygon":
                            dist = cv2.pointPolygonTest(zone.poly, center, False)
                            if dist >= 0:
                                in_zone = True
                                if track_id not in self.crossed_objects:
                                    self.crossed_objects[track_id] = True
                                self.zone_crossed_objects[zone.zone_id].add(int(track_id))
                                break
                        elif zone.zone_type == "line":
                            if len(zone.poly) >= 2 and len(track) >= 2:
                                p1 = track[-2]
                                p2 = track[-1]
                                line_start = tuple(zone.poly[0])
                                line_end = tuple(zone.poly[-1])
                                if AnalyticsEngine._segments_intersect(p1, p2, line_start, line_end):
                                    # Check crossing direction
                                    if zone.direction == "both":
                                        direction_ok = True
                                    else:
                                        sign = AnalyticsEngine._cross_sign(p1, p2, line_start, line_end)
                                        direction_ok = (
                                            (zone.direction == "in" and sign > 0) or
                                            (zone.direction == "out" and sign < 0)
                                        )
                                    if direction_ok:
                                        in_zone = True
                                        if track_id not in self.crossed_objects:
                                            self.crossed_objects[track_id] = True
                                        self.zone_crossed_objects[zone.zone_id].add(int(track_id))
                                        break
                else:
                    # No zones defined — count everything
                    if track_id not in self.crossed_objects:
                        self.crossed_objects[track_id] = True

                boxes_data.append({
                    "id": int(track_id),
                    "x": float((cx - bw / 2) * scale),
                    "y": float((cy - bh / 2) * scale),
                    "w": float(bw * scale),
                    "h": float(bh * scale),
                    "class": cls_idx,
                    "conf": round(float(conf), 2),
                    "label": self.detector.names.get(cls_idx, f"class_{cls_idx}"),
                    "in_zone": in_zone,
                    "is_counted": track_id in self.crossed_objects,
                })

            final_result = AnalyticsResult(
                boxes=boxes_data,
                total_count=len(self.crossed_objects),
                zone_counts={z_id: len(objs) for z_id, objs in self.zone_crossed_objects.items()},
                resolution={"w": w, "h": h},
            )
        else:
            # No detections - return empty result
            final_result = AnalyticsResult(
                boxes=[],
                total_count=len(self.crossed_objects),
                zone_counts={z_id: len(objs) for z_id, objs in self.zone_crossed_objects.items()},
                resolution={"w": w, "h": h},
            )
        
        self.last_result = final_result
        return final_result

    def draw_annotations(self, frame: np.ndarray, result: AnalyticsResult):
        """
        Draw bounding boxes, labels, zones, and count overlay on a frame.
        Matches the frontend visual style.
        """
        # Draw zone polygons and lines (dashed-style)
        for zone in self.parsed_zones:
            if zone.zone_type == "polygon":
                # Semi-transparent fill
                overlay = frame.copy()
                cv2.fillPoly(overlay, [zone.poly], zone.color)
                cv2.addWeighted(overlay, 0.1, frame, 0.9, 0, frame)

            # Draw dashed borders
            dash_length = 10
            gap_length = 5
            pts = zone.poly
            num_pts = len(pts)
            
            # Polygons close the shape (num_pts), lines do not (num_pts - 1)
            segments = num_pts if zone.zone_type == "polygon" else num_pts - 1
            
            for i in range(segments):
                pt1 = tuple(pts[i])
                pt2 = tuple(pts[(i + 1) % num_pts])
                
                # Calculate vector and distance
                dx = pt2[0] - pt1[0]
                dy = pt2[1] - pt1[1]
                dist = np.sqrt(dx**2 + dy**2)
                
                if dist == 0:
                    continue
                    
                dx_norm = dx / dist
                dy_norm = dy / dist
                
                # Draw dashes along the segment
                curr_dist = 0
                while curr_dist < dist:
                    start_x = int(pt1[0] + dx_norm * curr_dist)
                    start_y = int(pt1[1] + dy_norm * curr_dist)
                    
                    curr_dist = min(curr_dist + dash_length, dist)
                    end_x = int(pt1[0] + dx_norm * curr_dist)
                    end_y = int(pt1[1] + dy_norm * curr_dist)
                    
                    cv2.line(frame, (start_x, start_y), (end_x, end_y), zone.color, 2)
                    curr_dist += gap_length

        # Draw bounding boxes with labels
        for box in result.boxes:
            x1 = int(box["x"])
            y1 = int(box["y"])
            x2 = int(box["x"] + box["w"])
            y2 = int(box["y"] + box["h"])
            track_id = box["id"]

            # Color: orange if currently in zone, green if already counted, red otherwise
            if box["in_zone"]:
                color = (0, 140, 255)    # Orange (BGR)
            elif track_id in self.crossed_objects:
                color = (0, 200, 0)      # Green
            else:
                color = (0, 0, 255)      # Red

            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Label background + text
            label = f"{box['label']} #{track_id}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 8, y1), color, -1)
            cv2.putText(frame, label, (x1 + 4, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        # Count overlay (top-left)
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
                # Parse zone name from zone_id if possible or just use zone_id
                # Often zone_id is a UUID or simply string. If we want a nice name, we check if there's a name.
                # Since ParsedZone doesn't store name right now, let's just display "Zone ...: X"
                # Wait, does the zone have a name property? Checking ParsedZone...
                # It doesn't, but let's just show standard text.
                # We can draw it with the zone's color to make it clear.
                label_text = f"Zone {zone.zone_id[:8]}: {zone_count}" if len(zone.zone_id) > 8 else f"{zone.zone_id}: {zone_count}"
                
                # Dark outline
                cv2.putText(frame, label_text, (20, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
                # Colored text matching zone color
                cv2.putText(frame, label_text, (20, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, zone.color, 2, cv2.LINE_AA)
                
                y_offset += 40


    # ── Private helpers ──────────────────────────────────────────

    def _get_class_ids(self, class_names: list[str]) -> list[int]:
        """Convert class names to IDs using the detector's names map."""
        if not class_names:
            return []
        name_to_id = {v: k for k, v in self.detector.names.items()}
        return [name_to_id[n] for n in class_names if n in name_to_id]

    def _compute_required_classes(self) -> list[int] | None:
        """Collect all class IDs needed across zones + full-frame filter."""
        # If a master global filter is set, it restricts YOLO to ONLY tracking those classes
        if self.full_frame_class_ids:
            return self.full_frame_class_ids
            
        required = set()
        for zone in self.parsed_zones:
            if not zone.classes:
                return None  # Empty zone classes = track everything
            required.update(zone.classes)
        return list(required) if required else None

    @staticmethod
    def _parse_color(hex_color: str) -> tuple:
        """Convert hex color string to BGR tuple."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return (b, g, r)  # BGR for OpenCV
        return (0, 255, 0)
