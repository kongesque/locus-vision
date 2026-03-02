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
from services.metrics_collector import metrics_collector


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
        
        # Frame timing metrics for FPS calculation
        self._frame_count = 0
        self._frame_times = []
        self._fps_calc_interval = 5  # Calculate FPS every 5 seconds
        self._last_fps_calc = time.time()

    def start(self):
        self._running = True
        # Register with metrics collector
        metrics_collector.register_camera(self.camera_id)
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        # Unregister from metrics collector
        metrics_collector.unregister_camera(self.camera_id)

    def _capture_loop(self):
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened() or not cap.read()[0]:
            print(f"[Livestream] Cannot open webcam 0. Falling back to dummy feed.")
            self._dummy_loop()
            return

        target_fps = 15
        frame_interval = 1.0 / target_fps
        
        # Track frame timing for FPS calculation
        frame_times = []
        last_frame_time = time.time()

        print(f"[Livestream] Started capture on {self.camera_id}")
        while self._running:
            loop_start = time.time()
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            # Calculate input FPS based on time between frames
            current_time = time.time()
            frame_times.append(current_time)
            # Keep only last 30 frames for FPS calc
            if len(frame_times) > 30:
                frame_times.pop(0)
            if len(frame_times) >= 2:
                input_fps = len(frame_times) / (frame_times[-1] - frame_times[0])
                metrics_collector.update_camera_input_fps(self.camera_id, input_fps)

            # Process AI with configured zones/classes
            result = self.engine.process_frame(frame)
            self.engine.draw_annotations(frame, result)
            
            # Track that a frame was processed
            self._frame_count += 1

            # Encode to JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if ret:
                frame_bytes = buffer.tobytes()
                for q in self.video_clients:
                    try:
                        q.put_nowait(frame_bytes)
                    except asyncio.QueueFull:
                        pass
                
                # Record successful frame processing
                metrics_collector.record_camera_frame(
                    self.camera_id, 
                    processed=True,
                    inference_ms=0  # Inference time is recorded by detector itself
                )
            else:
                # Frame encoding failed
                metrics_collector.record_camera_frame(
                    self.camera_id,
                    processed=False
                )

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
            elapsed = time.time() - loop_start
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
        
        # Track frame timing for FPS calculation
        frame_times = []
        
        while self._running:
            start_time = time.time()
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:] = (40, 40, 40)
            
            # Calculate input FPS
            current_time = time.time()
            frame_times.append(current_time)
            if len(frame_times) > 30:
                frame_times.pop(0)
            if len(frame_times) >= 2:
                input_fps = len(frame_times) / (frame_times[-1] - frame_times[0])
                metrics_collector.update_camera_input_fps(self.camera_id, input_fps)
            
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
                
                # Record frame processing for dummy feed
                metrics_collector.record_camera_frame(
                    self.camera_id,
                    processed=True
                )
                    
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
