"""
Shared analytics engine for zone-based object counting and tracking.

Used by both video processing (offline) and livestream (real-time WebSocket).
Wraps the ONNX detector and adds stateful zone-aware counting logic.
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from services.onnx_detector import get_detector, OnnxDetector


@dataclass
class AnalyticsResult:
    """Result from a single frame analysis."""
    boxes: list          # List of box dicts {id, x, y, w, h, class, conf, label, in_zone}
    total_count: int     # Total unique objects that have entered any zone
    resolution: dict     # {w, h}


@dataclass
class ParsedZone:
    """Pre-parsed zone polygon for efficient per-frame checking."""
    poly: np.ndarray
    color: tuple
    zone_id: str
    classes: list  # List of class IDs to filter (empty = all)


class AnalyticsEngine:
    """
    Stateful per-session analytics engine.

    Maintains tracking state across frames:
    - Track history (last 30 positions per object)
    - Crossed objects (unique IDs that entered any zone)
    - Per-zone class filtering
    """

    def __init__(self, model_name: str = "yolo11n", zones: list = None, full_frame_classes: list = None):
        self.detector: OnnxDetector = get_detector(model_name)
        self.track_history: dict[int, list] = {}
        self.crossed_objects: dict[int, bool] = {}
        self.parsed_zones: list[ParsedZone] = []
        self.full_frame_class_ids: list[int] = []

        if zones:
            self.set_zones(zones)
        if full_frame_classes:
            self.full_frame_class_ids = self._get_class_ids(full_frame_classes)

    def set_zones(self, zones: list):
        """Parse zone definitions into efficient polygon structures."""
        self.parsed_zones = []
        for zone in zones:
            points = zone.get("points", [])
            if len(points) < 3:
                continue
            pts = np.array([[p['x'], p['y']] for p in points], np.int32)
            self.parsed_zones.append(ParsedZone(
                poly=pts,
                color=self._parse_color(zone.get("color", "#00ff00")),
                zone_id=zone.get("id", ""),
                classes=self._get_class_ids(zone.get("classes", []))
            ))

    def reset(self):
        """Reset all tracking state (call between different sources)."""
        self.track_history.clear()
        self.crossed_objects.clear()
        self.detector.reset_tracker()

    def process_frame(self, frame: np.ndarray) -> AnalyticsResult:
        """
        Run detection + tracking + zone counting on a single frame.
        Returns an AnalyticsResult with boxes, counts, and resolution.
        """
        h, w = frame.shape[:2]

        # Determine which classes to track
        classes_arg = self._compute_required_classes()

        # Run ONNX detection + ByteTrack tracking
        result = self.detector.track(frame, classes=classes_arg)

        boxes_data = []

        if result.has_detections and result.track_ids:
            for box, track_id, cls_idx, conf in zip(
                result.boxes_xywh, result.track_ids, result.class_ids, result.scores
            ):
                cls_idx = int(cls_idx)
                cx, cy, bw, bh = box
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
                        dist = cv2.pointPolygonTest(zone.poly, center, False)
                        if dist >= 0:
                            in_zone = True
                            if track_id not in self.crossed_objects:
                                self.crossed_objects[track_id] = True
                            break
                else:
                    # No zones defined — count everything matching full-frame filter
                    if not self.full_frame_class_ids or cls_idx in self.full_frame_class_ids:
                        if track_id not in self.crossed_objects:
                            self.crossed_objects[track_id] = True

                boxes_data.append({
                    "id": int(track_id),
                    "x": float(cx - bw / 2),
                    "y": float(cy - bh / 2),
                    "w": float(bw),
                    "h": float(bh),
                    "class": cls_idx,
                    "conf": round(float(conf), 2),
                    "label": self.detector.names.get(cls_idx, f"class_{cls_idx}"),
                    "in_zone": in_zone,
                })

        return AnalyticsResult(
            boxes=boxes_data,
            total_count=len(self.crossed_objects),
            resolution={"w": w, "h": h},
        )

    def draw_annotations(self, frame: np.ndarray, result: AnalyticsResult):
        """
        Draw bounding boxes, zones, and count overlay on a frame.
        Used by the video processing pipeline (not livestream — that draws on canvas).
        """
        # Draw zones
        for zone in self.parsed_zones:
            cv2.polylines(frame, [zone.poly], True, zone.color, 3)

        # Draw boxes
        for box in result.boxes:
            center = (int(box["x"] + box["w"] / 2), int(box["y"] + box["h"] / 2))
            track_id = box["id"]

            if box["in_zone"]:
                cv2.circle(frame, center, 9, (244, 133, 66), -1)   # Orange = in zone
            elif track_id in self.crossed_objects:
                cv2.circle(frame, center, 9, (83, 168, 51), -1)    # Green = already counted
            else:
                cv2.circle(frame, center, 9, (54, 67, 234), -1)    # Red = not counted

        # Draw count
        count_text = f"Count: {result.total_count}"
        cv2.putText(frame, count_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

    # ── Private helpers ──────────────────────────────────────────

    def _get_class_ids(self, class_names: list[str]) -> list[int]:
        """Convert class names to IDs using the detector's names map."""
        if not class_names:
            return []
        name_to_id = {v: k for k, v in self.detector.names.items()}
        return [name_to_id[n] for n in class_names if n in name_to_id]

    def _compute_required_classes(self) -> list[int] | None:
        """Collect all class IDs needed across zones + full-frame filter."""
        required = set(self.full_frame_class_ids)
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
