"""
Livestream Manager: manages real-time video capture, AI processing, and event broadcasting.

Loads camera configuration (zones, classes, model) from the database when starting a stream.
Also buffers telemetry events and flushes them to DuckDB for analytics.
"""

import asyncio
import collections
import threading
import time
import json
import cv2
from datetime import datetime
from services.analytics_engine import AnalyticsEngine
from services.metrics_collector import metrics_collector
from services.duckdb_client import client as db_client
from services.video_capture import create_video_capture, get_capture_info


class LivestreamManager:
    def __init__(self):
        self.active_streams = {}  # camera_id -> StreamContext
        self.lock = threading.Lock()

    def get_or_create_stream(self, camera_id: str, zones=None, classes=None, model_name="yolo11n", fps=24, source=None, enable_hw_accel=True, conf_threshold=None):
        with self.lock:
            if camera_id not in self.active_streams:
                self.active_streams[camera_id] = StreamContext(
                    camera_id,
                    zones=zones,
                    classes=classes,
                    model_name=model_name,
                    fps=fps,
                    source=source,
                    enable_hw_accel=enable_hw_accel,
                    conf_threshold=conf_threshold,
                )
                self.active_streams[camera_id].start()
            return self.active_streams[camera_id]

    def stop_stream(self, camera_id: str):
        """Stop and remove a stream by camera ID."""
        with self.lock:
            stream = self.active_streams.pop(camera_id, None)
        if stream:
            stream.stop()

    def stop_all_streams(self):
        """Stop all active streams."""
        with self.lock:
            streams = list(self.active_streams.values())
            self.active_streams.clear()
        for stream in streams:
            stream.stop()

class StreamContext:
    def __init__(self, camera_id: str, zones=None, classes=None, model_name="yolo11n", fps=24, source=None, enable_hw_accel=True, conf_threshold=None):
        self.camera_id = camera_id
        self.source = source if source is not None else 0  # Default to webcam 0
        self.enable_hw_accel = enable_hw_accel
        self.target_fps = fps
        self.video_clients = []
        self.event_clients = []
        
        self.engine = AnalyticsEngine(
            model_name=model_name,
            zones=zones,
            full_frame_classes=classes,
            mode="live",
            camera_id=camera_id,
            conf_threshold=conf_threshold
        )
        
        self._running = False
        self._thread = None
        self._frame_count = 0
        
        # Stream uptime tracking (NVR-style — survives page refreshes)
        self.started_at = time.time()

        # Server-side event ring buffer (NVR-style — recent events survive page refreshes)
        self.recent_events = collections.deque(maxlen=200)
        self._event_write_buffer = []

        # Telemetry Buffers for DuckDB
        self.zone_events_buffer = []
        self.line_events_buffer = []
        self.track_events_buffer = []
        self._last_db_flush = time.time()

        # SSE Event Throttling — only emit meaningful state changes
        self._known_tracks = set()           # track IDs we've announced
        self._track_last_event = {}          # track_id -> last SSE emit time
        self._track_zones = {}               # track_id -> last known zone
        self._sse_cooldown = 5.0             # seconds between dwell updates per track
        self._preload_recent_events()

    def start(self):
        self._running = True
        metrics_collector.register_camera(self.camera_id)
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        metrics_collector.remove_camera(self.camera_id)
        # Final flush
        self._flush_duckdb()

    def _flush_duckdb(self):
        try:
            db_client.insert_zone_events(self.zone_events_buffer)
            db_client.insert_line_events(self.line_events_buffer)
            db_client.insert_object_tracks(self.track_events_buffer)
        except Exception as e:
            print(f"[Livestream] DuckDB flush failed: {e}")
        finally:
            self.zone_events_buffer.clear()
            self.line_events_buffer.clear()
            self.track_events_buffer.clear()
        self._flush_sqlite_events()

    def _flush_sqlite_events(self):
        if not self._event_write_buffer:
            return
        events = self._event_write_buffer[:]
        self._event_write_buffer.clear()
        try:
            import sqlite3
            from config import settings
            conn = sqlite3.connect(settings.database_path)
            conn.executemany(
                "INSERT INTO livestream_events (camera_id, type, message, zone, timestamp) VALUES (?,?,?,?,?)",
                [(self.camera_id, e["type"], e["message"], e.get("zone"), e["timestamp"]) for e in events]
            )
            conn.commit()
            conn.close()
        except Exception as ex:
            print(f"[Livestream] SQLite event flush failed: {ex}")

    def _preload_recent_events(self):
        try:
            import sqlite3
            from config import settings
            conn = sqlite3.connect(settings.database_path)
            rows = conn.execute(
                "SELECT type, message, zone, timestamp FROM livestream_events "
                "WHERE camera_id = ? ORDER BY timestamp DESC LIMIT 200",
                (self.camera_id,)
            ).fetchall()
            conn.close()
            for row in reversed(rows):
                self.recent_events.append({
                    "type": row[0], "message": row[1],
                    "zone": row[2], "timestamp": row[3]
                })
        except Exception as ex:
            print(f"[Livestream] Event preload failed: {ex}")

    def _capture_loop(self):
        # Use hardware-accelerated video capture
        cap = create_video_capture(self.source, enable_hw_accel=self.enable_hw_accel)
        
        if not cap.isOpened() or not cap.read()[0]:
            print(f"[Livestream] Cannot open source {self.source}. Falling back to dummy feed.")
            cap.release()
            self._dummy_loop()
            return
        
        # Log capture info for debugging
        info = get_capture_info(cap)
        print(f"[Livestream] Camera {self.camera_id} info: {info}")

        target_fps = self.target_fps
        frame_interval = 1.0 / target_fps
        frame_times = []

        print(f"[Livestream] Started capture on {self.camera_id}")
        while self._running:
            loop_start = time.time()
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            current_time = time.time()
            frame_times.append(current_time)
            if len(frame_times) > 30:
                frame_times.pop(0)
            if len(frame_times) >= 2:
                input_fps = len(frame_times) / (frame_times[-1] - frame_times[0])
                metrics_collector.update_camera_input_fps(self.camera_id, input_fps)

            # Process AI
            result = self.engine.process_frame(frame, current_time=current_time)
            self.engine.draw_annotations(frame, result)
            self._frame_count += 1

            # Buffer telemetry for DuckDB
            for ze in result.zone_events:
                self.zone_events_buffer.append(
                    (datetime.fromtimestamp(ze["timestamp"]), ze["camera_id"], ze["zone_id"], ze["event_type"], ze["track_id"], ze["dwell_time"])
                )
            for le in result.line_events:
                self.line_events_buffer.append(
                    (datetime.fromtimestamp(le["timestamp"]), le["camera_id"], le["line_id"], le["direction"], le["track_id"])
                )
            for te in result.track_events:
                self.track_events_buffer.append(
                    (datetime.fromtimestamp(te["timestamp"]), te["camera_id"], te["track_id"], te["class_id"], te["x"], te["y"])
                )

            # Flush every 5 seconds
            if current_time - self._last_db_flush > 5.0:
                self._flush_duckdb()
                self._last_db_flush = current_time

            # Encode to JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if ret:
                frame_bytes = buffer.tobytes()
                for q in self.video_clients:
                    try: q.put_nowait(frame_bytes)
                    except asyncio.QueueFull: pass
                
                metrics_collector.record_camera_frame(
                    self.camera_id, 
                    processed=True,
                    had_detection=len(result.boxes) > 0
                )
            else:
                metrics_collector.record_camera_frame(self.camera_id, processed=False)

            # Generate real-time events for SSE (throttled, NVR-style)
            ws_events = []
            
            # Intelligent per-track event emission
            for box in result.boxes:
                track_id = box.get("id")
                label = box["label"]
                # in_zone is a boolean — derive a readable zone name from zone_events or fallback
                zone_name = "Camera View"
                if box.get("in_zone"):
                    # Find which zone this track is in from the current zone_events
                    for ze in result.zone_events:
                        if ze.get("track_id") == track_id and ze.get("event_type") == "enter":
                            zone_name = ze.get("zone_id", "Zone")
                            break
                    else:
                        zone_name = "Zone"
                dwell_time = box.get("dwell_time", 0.0)
                point = {"x": box["x"] + box["w"] / 2, "y": box["y"] + box["h"]}
                
                # Always send heatmap points (lightweight, no log entry)
                # but only emit activity log events on state changes
                
                if track_id is not None:
                    # 1) New track — object just appeared
                    if track_id not in self._known_tracks:
                        self._known_tracks.add(track_id)
                        self._track_last_event[track_id] = current_time
                        self._track_zones[track_id] = zone_name
                        ws_events.append({
                            "type": label.lower(),
                            "message": f"{label} entered {zone_name}",
                            "zone": zone_name,
                            "timestamp": current_time,
                            "point": point,
                        })
                        continue
                    
                    # 2) Zone transition — object moved between zones
                    prev_zone = self._track_zones.get(track_id)
                    if prev_zone and prev_zone != zone_name:
                        self._track_zones[track_id] = zone_name
                        self._track_last_event[track_id] = current_time
                        ws_events.append({
                            "type": "zone",
                            "message": f"{label} moved from {prev_zone} to {zone_name}",
                            "zone": zone_name,
                            "timestamp": current_time,
                            "point": point,
                        })
                        continue
                    
                    # 3) Dwell heartbeat — update every N seconds
                    last_emit = self._track_last_event.get(track_id, 0)
                    if current_time - last_emit >= self._sse_cooldown and dwell_time > 0:
                        self._track_last_event[track_id] = current_time
                        ws_events.append({
                            "type": label.lower(),
                            "message": f"{label} in {zone_name} · {dwell_time:.0f}s",
                            "zone": zone_name,
                            "timestamp": current_time,
                            "point": point,
                        })
                else:
                    # No track_id (untracked detection) — throttle globally by label
                    throttle_key = f"__untracked_{label.lower()}"
                    last_emit = self._track_last_event.get(throttle_key, 0)
                    if current_time - last_emit >= self._sse_cooldown:
                        self._track_last_event[throttle_key] = current_time
                        ws_events.append({
                            "type": label.lower(),
                            "message": f"{label} detected in {zone_name}",
                            "zone": zone_name,
                            "timestamp": current_time,
                            "point": point,
                        })

            # Analytics alerts — always emit immediately (high priority)
            for alert in result.alerts:
                ws_events.append(alert)

            # Zone exit events — surface dwell time (spatial analytics)
            box_labels = {box["id"]: box["label"] for box in result.boxes}
            for ze in result.zone_events:
                if ze["event_type"] == "exit" and ze["dwell_time"] >= 1.0:
                    label = box_labels.get(ze["track_id"], "Object")
                    dwell = ze["dwell_time"]
                    dwell_str = f"{dwell:.0f}s" if dwell < 60 else f"{dwell / 60:.1f}m"
                    ws_events.append({
                        "type": "zone_exit",
                        "message": f"{label} left {ze['zone_id']} · {dwell_str} dwell",
                        "zone": ze["zone_id"],
                        "timestamp": ze["timestamp"],
                    })

            # Line crossing events — surface direction
            for le in result.line_events:
                label = box_labels.get(le["track_id"], "Object")
                direction = le["direction"]
                dir_label = "→ in" if direction == "in" else "← out" if direction == "out" else "crossing"
                ws_events.append({
                    "type": "line_cross",
                    "message": f"{label} crossed {le['line_id']} · {dir_label}",
                    "zone": le["line_id"],
                    "timestamp": le["timestamp"],
                    "direction": direction,
                })

            # Zone counts update — always emit total_count so frontend stays in sync
            if result.zone_counts or result.total_count > 0:
                ws_events.append({
                    "type": "zone_update",
                    "zone_counts": result.zone_counts,
                    "total_count": result.total_count,
                    "timestamp": current_time,
                })

            # Garbage-collect stale tracks from throttle state (every 30s)
            if self._frame_count % 450 == 0:  # ~30s at 15fps
                stale_cutoff = current_time - 30.0
                stale_ids = [k for k, v in self._track_last_event.items() if v < stale_cutoff]
                for k in stale_ids:
                    self._track_last_event.pop(k, None)
                    self._known_tracks.discard(k)
                    self._track_zones.pop(k, None)
                
            for ev in ws_events:
                # Buffer event server-side for replay on page refresh (NVR-style)
                if ev.get("type") != "zone_update":
                    self.recent_events.append(ev)
                    self._event_write_buffer.append(ev)
                for q in self.event_clients:
                    try: q.put_nowait(json.dumps(ev))
                    except asyncio.QueueFull: pass

            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()

    def _dummy_loop(self):
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
                    
            if x % 30 == 0:
                ev = {"type": "alert", "message": "Dummy motion detected", "zone": "Fallback", "timestamp": time.time()}
                for q in self.event_clients:
                    try: q.put_nowait(json.dumps(ev))
                    except: pass

            elapsed = time.time() - start_time
            if (frame_interval - elapsed) > 0:
                time.sleep(frame_interval - elapsed)


livestream_manager = LivestreamManager()
