"""
SQLite-backed video processing job queue.

Runs a single daemon worker thread that processes video tasks sequentially.
Uses the existing video_tasks table for state, adding progress tracking.
Crash-resilient: on startup, any 'processing' tasks are reset to 'pending'.
"""

import os
import cv2
import time
import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional
from services.analytics_engine import AnalyticsEngine
from services.duckdb_client import client as db_client
from config import settings

CACHE_DIR = "data/videos"
os.makedirs(CACHE_DIR, exist_ok=True)


def _dict_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


class VideoJobQueue:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._current_task_id: Optional[str] = None
        self._db_path = settings.database_path

    # ── Lifecycle ────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._recover_stale_tasks()
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        print("[JobQueue] Worker started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[JobQueue] Worker stopped.")

    # ── Public API ───────────────────────────────────────────

    def get_queue_status(self) -> dict:
        conn = self._get_conn()
        try:
            processing = None
            if self._current_task_id:
                row = conn.execute(
                    "SELECT id, filename, progress FROM video_tasks WHERE id = ?",
                    (self._current_task_id,),
                ).fetchone()
                if row:
                    processing = {
                        "task_id": row["id"],
                        "filename": row["filename"],
                        "progress": row["progress"],
                    }

            pending_rows = conn.execute(
                "SELECT id, filename FROM video_tasks WHERE status = 'pending' ORDER BY created_at ASC"
            ).fetchall()
            pending = [{"task_id": r["id"], "filename": r["filename"]} for r in pending_rows]

            return {
                "queue_length": len(pending) + (1 if processing else 0),
                "processing": processing,
                "pending": pending,
            }
        finally:
            conn.close()

    # ── Internal ─────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = _dict_factory
        return conn

    def _recover_stale_tasks(self):
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "UPDATE video_tasks SET status = 'pending', progress = 0 WHERE status = 'processing'"
            )
            if cursor.rowcount > 0:
                print(f"[JobQueue] Recovered {cursor.rowcount} stale task(s).")
            conn.commit()
        finally:
            conn.close()

    def _worker_loop(self):
        while self._running:
            task = self._fetch_next_task()
            if task:
                self._process_task(task)
            else:
                time.sleep(2)

    def _fetch_next_task(self) -> Optional[dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM video_tasks WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None

            conn.execute(
                "UPDATE video_tasks SET status = 'processing', progress = 0 WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            self._current_task_id = row["id"]
            return row
        finally:
            conn.close()

    def _update_progress(self, task_id: str, progress: int):
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE video_tasks SET progress = ? WHERE id = ?",
                (min(progress, 100), task_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _complete_task(self, task_id: str, duration_str: str, total_count: int, zone_counts: dict):
        conn = self._get_conn()
        try:
            conn.execute(
                """
                UPDATE video_tasks
                SET status = 'completed',
                    progress = 100,
                    completed_at = datetime('now'),
                    duration = ?,
                    format = 'mp4',
                    total_count = ?,
                    zone_counts = ?
                WHERE id = ?
                """,
                (duration_str, total_count, json.dumps(zone_counts), task_id),
            )
            conn.commit()
        finally:
            conn.close()
            self._current_task_id = None

    def _fail_task(self, task_id: str, error_msg: str):
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE video_tasks SET status = 'failed', error_message = ? WHERE id = ?",
                (error_msg, task_id),
            )
            conn.commit()
        finally:
            conn.close()
            self._current_task_id = None

    def _process_task(self, task: dict):
        task_id = task["id"]
        input_path = os.path.join(CACHE_DIR, f"input_{task_id}.mp4")
        output_path = os.path.join(CACHE_DIR, f"output_{task_id}.mp4")
        model_name = task.get("model_name") or "yolo11n"

        zones_raw = task.get("zones") or "[]"
        zones = json.loads(zones_raw) if isinstance(zones_raw, str) else zones_raw

        classes_raw = task.get("classes") or "[]"
        full_frame_classes = json.loads(classes_raw) if isinstance(classes_raw, str) else classes_raw

        target_fps = task.get("fps") or 12
        conf_threshold = task.get("confidence_threshold") or 0.15

        print(f"[JobQueue] Processing task {task_id} ({task.get('filename', '?')})")

        try:
            engine = AnalyticsEngine(
                model_name=model_name,
                zones=zones,
                full_frame_classes=full_frame_classes,
                mode="batch",
                camera_id=task_id,
                conf_threshold=conf_threshold
            )

            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                self._fail_task(task_id, f"Cannot open video file: {input_path}")
                return

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_sec = total_frames / fps if fps > 0 else 0
            duration_str = time.strftime("%H:%M:%S", time.gmtime(duration_sec))

            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
            ret, thumb_frame = cap.read()
            if ret:
                thumb_path = os.path.join(CACHE_DIR, f"thumbnail_{task_id}.jpg")
                cv2.imwrite(thumb_path, thumb_frame)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            new_fps = min(fps, target_fps)
            skip_interval = max(1, int(fps / new_fps))

            fourcc = cv2.VideoWriter_fourcc(*"avc1")
            out = cv2.VideoWriter(output_path, fourcc, new_fps, (width, height))

            analytical_data = {
                "task_id": task_id,
                "filename": task.get("filename", "unknown"),
                "model_name": model_name,
                "fps": new_fps,
                "zones": zones,
                "frames": [],
            }

            frame_count = 0
            frames_to_process = total_frames // skip_interval if skip_interval > 0 else total_frames
            processed_frames = 0
            start_time = time.time()
            last_progress_update = 0
            result = None
            
            zone_events_buffer = []
            line_events_buffer = []
            track_events_buffer = []

            while cap.isOpened() and self._running:
                success, frame = cap.read()
                if not success:
                    break

                frame_count += 1
                if frame_count % skip_interval != 0:
                    continue

                processed_frames += 1
                timestamp = frame_count / fps
                result = engine.process_frame(frame, current_time=timestamp)
                engine.draw_annotations(frame, result)
                out.write(frame)
                
                # Buffer telemetry for DuckDB
                for ze in result.zone_events:
                    zone_events_buffer.append(
                        (datetime.fromtimestamp(ze["timestamp"]), task_id, ze["zone_id"], ze["event_type"], ze["track_id"], ze["dwell_time"])
                    )
                for le in result.line_events:
                    line_events_buffer.append(
                        (datetime.fromtimestamp(le["timestamp"]), task_id, le["line_id"], le["direction"], le["track_id"])
                    )
                for te in result.track_events:
                    track_events_buffer.append(
                        (datetime.fromtimestamp(te["timestamp"]), task_id, te["track_id"], te["class_id"], te["x"], te["y"])
                    )

                if len(track_events_buffer) > 5000:
                    db_client.insert_zone_events(zone_events_buffer)
                    db_client.insert_line_events(line_events_buffer)
                    db_client.insert_object_tracks(track_events_buffer)
                    zone_events_buffer.clear()
                    line_events_buffer.clear()
                    track_events_buffer.clear()

                # Store per-frame data for JSON
                analytical_data["frames"].append(
                    {
                        "timestamp": round(timestamp, 2),
                        "boxes": result.boxes,
                        "current_total_count": result.total_count,
                        "current_zone_counts": result.zone_counts,
                    }
                )

                progress = int((processed_frames / max(frames_to_process, 1)) * 100)
                if progress - last_progress_update >= 2 or processed_frames % 30 == 0:
                    self._update_progress(task_id, progress)
                    last_progress_update = progress

            cap.release()
            out.release()
            
            # End of video loop, flush remaining
            # Force GC to emit exit events for active tracks at the end
            if result:
                engine._mode_temp = engine.mode
                engine.mode = "live" # temporarily switch mode to force GC
                engine._garbage_collect(timestamp + 999999)
                engine.mode = engine._mode_temp
                
                # We can't easily get the newly generated zone_events since process_frame returns them.
                # But it's fine, we can just skip final exit events to remain simple, or manually push them.
            
            db_client.insert_zone_events(zone_events_buffer)
            db_client.insert_line_events(line_events_buffer)
            db_client.insert_object_tracks(track_events_buffer)

            if not self._running:
                print(f"[JobQueue] Task {task_id} interrupted by shutdown.")
                conn = self._get_conn()
                try:
                    conn.execute(
                        "UPDATE video_tasks SET status = 'pending', progress = 0 WHERE id = ?",
                        (task_id,),
                    )
                    conn.commit()
                finally:
                    conn.close()
                    self._current_task_id = None
                return

            data_path = os.path.join(CACHE_DIR, f"data_{task_id}.json")
            with open(data_path, "w") as f:
                json.dump(analytical_data, f)

            if os.path.exists(input_path):
                os.remove(input_path)

            elapsed = time.time() - start_time
            print(f"[JobQueue] Task {task_id} completed in {elapsed:.1f}s")

            final_count = result.total_count if result else 0
            final_zone_counts = result.zone_counts if result else {}
            self._complete_task(task_id, duration_str, final_count, final_zone_counts)

        except Exception as e:
            print(f"[JobQueue] Task {task_id} failed: {e}")
            self._fail_task(task_id, str(e))


job_queue = VideoJobQueue()
