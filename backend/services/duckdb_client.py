"""DuckDB client for high-performance analytics."""

import duckdb
from pathlib import Path
import logging
from datetime import datetime
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class DuckDBClient:
    def __init__(self, db_path: str = "data/locus_active.duckdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Initialize connection
        self.conn = duckdb.connect(str(self.db_path))
        self.init_schema()

    def init_schema(self):
        """Initialize telemetry tables."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS zone_events (
                timestamp TIMESTAMP,
                camera_id VARCHAR,
                zone_id VARCHAR,
                event_type VARCHAR,
                track_id INTEGER,
                dwell_time FLOAT
            );
            
            CREATE TABLE IF NOT EXISTS line_events (
                timestamp TIMESTAMP,
                camera_id VARCHAR,
                line_id VARCHAR,
                direction VARCHAR,
                track_id INTEGER
            );
            
            CREATE TABLE IF NOT EXISTS object_tracks (
                timestamp TIMESTAMP,
                camera_id VARCHAR,
                track_id INTEGER,
                class_id INTEGER,
                x FLOAT,
                y FLOAT
            );
        """)

    def insert_zone_events(self, events: List[Tuple[datetime, str, str, str, int, float]]):
        """
        Insert multiple zone events.
        events: [(timestamp, camera_id, zone_id, event_type, track_id, dwell_time), ...]
        """
        if not events:
            return
        self.conn.executemany(
            "INSERT INTO zone_events VALUES (?, ?, ?, ?, ?, ?)",
            events
        )

    def insert_line_events(self, events: List[Tuple[datetime, str, str, str, int]]):
        """
        Insert multiple line events.
        events: [(timestamp, camera_id, line_id, direction, track_id), ...]
        """
        if not events:
            return
        self.conn.executemany(
            "INSERT INTO line_events VALUES (?, ?, ?, ?, ?)",
            events
        )

    def insert_object_tracks(self, events: List[Tuple[datetime, str, int, int, float, float]]):
        """
        Insert multiple object tracks.
        events: [(timestamp, camera_id, track_id, class_id, x, y), ...]
        """
        if not events:
            return
        self.conn.executemany(
            "INSERT INTO object_tracks VALUES (?, ?, ?, ?, ?, ?)",
            events
        )

    def close(self):
        self.conn.close()

# Provide a global instance for simple imports and usage
client = DuckDBClient()
