"""
Livestream Manager: manages real-time video capture, AI processing, and event broadcasting.

Loads camera configuration (zones, classes, model) from the database when starting a stream.
"""

import asyncio
import threading
import time
import json
import cv2
from services.analytics_engine import AnalyticsEngine


class LivestreamManager:
    def __init__(self):
        self.active_streams = {}  # camera_id -> StreamContext
        self.lock = threading.Lock()

    def get_or_create_stream(self, camera_id: str, zones=None, classes=None, model_name="yolo11n"):
        with self.lock:
            if camera_id not in self.active_streams:
                self.active_streams[camera_id] = StreamContext(
                    camera_id,
                    zones=zones,
                    classes=classes,
                    model_name=model_name,
                )
                self.active_streams[camera_id].start()
            return self.active_streams[camera_id]

class StreamContext:
    def __init__(self, camera_id: str, zones=None, classes=None, model_name="yolo11n"):
        self.camera_id = camera_id
        self.video_clients = []
        self.event_clients = []
        
        # Initialize AnalyticsEngine with camera-specific config
        self.engine = AnalyticsEngine(
            model_name=model_name,
            zones=zones,
            full_frame_classes=classes,
        )
        
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _capture_loop(self):
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened() or not cap.read()[0]:
            print(f"[Livestream] Cannot open webcam 0. Falling back to dummy feed.")
            self._dummy_loop()
            return

        target_fps = 15
        frame_interval = 1.0 / target_fps

        print(f"[Livestream] Started capture on {self.camera_id}")
        while self._running:
            start_time = time.time()
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # Process AI with configured zones/classes
            result = self.engine.process_frame(frame)
            self.engine.draw_annotations(frame, result)

            # Encode to JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if ret:
                frame_bytes = buffer.tobytes()
                for q in self.video_clients:
                    try:
                        q.put_nowait(frame_bytes)
                    except asyncio.QueueFull:
                        pass

            # Generate zone-aware events
            if result.boxes:
                events = []
                for box in result.boxes:
                    zone_name = box.get("in_zone", "Camera View") or "Camera View"
                    events.append({
                        "type": box["label"].lower(),
                        "message": f"{box['label']} detected (Confidence: {box['conf']})",
                        "zone": zone_name,
                        "timestamp": time.time(),
                    })
                
                # Also emit zone count updates
                if result.zone_counts:
                    events.append({
                        "type": "zone_update",
                        "zone_counts": result.zone_counts,
                        "total_count": result.total_count,
                        "timestamp": time.time(),
                    })
                
                for ev in events:
                    for q in self.event_clients:
                        try:
                            q.put_nowait(json.dumps(ev))
                        except asyncio.QueueFull:
                            pass

            # Sleep to maintain fps
            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()

    def _dummy_loop(self):
        """Fallback loop that generates a bouncing color box if no video source is available."""
        import numpy as np
        target_fps = 10
        frame_interval = 1.0 / target_fps
        x, y = 100, 100
        dx, dy = 15, 15
        
        while self._running:
            start_time = time.time()
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:] = (40, 40, 40)
            
            x += dx
            y += dy
            if x <= 0 or x >= 640 - 50: dx *= -1
            if y <= 0 or y >= 480 - 50: dy *= -1
            
            cv2.rectangle(frame, (x, y), (x+50, y+50), (0, 0, 255), -1)
            cv2.putText(frame, "NO CAMERA FEED AVAILABLE", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
            
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if ret:
                frame_bytes = buffer.tobytes()
                for q in self.video_clients:
                    try: q.put_nowait(frame_bytes)
                    except Exception: pass
                    
            # Dummy event
            if x % 30 == 0:
                ev = {"type": "alert", "message": "Dummy motion detected", "zone": "Fallback", "timestamp": time.time()}
                for q in self.event_clients:
                    try: q.put_nowait(json.dumps(ev))
                    except: pass

            elapsed = time.time() - start_time
            if (frame_interval - elapsed) > 0:
                time.sleep(frame_interval - elapsed)


livestream_manager = LivestreamManager()
