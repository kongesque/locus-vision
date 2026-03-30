"""
Tests for livestream event SQLite persistence (PLAN_activity_feed.md — Priority 1).

Covers:
- livestream_events table created by init_db()
- _flush_sqlite_events writes buffered events to SQLite
- _preload_recent_events loads persisted events into the ring buffer on startup
- Archiver prunes events older than retention period
"""

import os
import sys
import time
import sqlite3
import tempfile
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite DB with the livestream_events table pre-created."""
    db_path = str(tmp_path / "test_locusvision.db")
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS livestream_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id  TEXT    NOT NULL,
            type       TEXT    NOT NULL,
            message    TEXT    NOT NULL,
            zone       TEXT    NULL,
            timestamp  REAL    NOT NULL,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_livestream_events_camera
            ON livestream_events(camera_id, timestamp DESC);
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def stream_ctx(tmp_db):
    """StreamContext with settings.database_path patched to the temp DB."""
    with patch("config.settings") as mock_settings:
        mock_settings.database_path = tmp_db
        from services.livestream_manager import StreamContext
        ctx = StreamContext(camera_id="cam_test", source=0)
    yield ctx, tmp_db
    ctx.stop()


# ─── Table schema ─────────────────────────────────────────────────────────────

class TestLivestreamEventsTable:
    def test_init_db_creates_table(self, tmp_path):
        """init_db() must create the livestream_events table."""
        import asyncio
        import database
        db_path = str(tmp_path / "locus.db")
        with patch.object(database, "settings") as mock_settings:
            mock_settings.database_path = db_path
            asyncio.run(database.init_db())

        conn = sqlite3.connect(db_path)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()

        assert "livestream_events" in tables

    def test_init_db_creates_index(self, tmp_path):
        """init_db() must create the camera+timestamp index."""
        import asyncio
        import database
        db_path = str(tmp_path / "locus.db")
        with patch.object(database, "settings") as mock_settings:
            mock_settings.database_path = db_path
            asyncio.run(database.init_db())

        conn = sqlite3.connect(db_path)
        indexes = [r[1] for r in conn.execute(
            "SELECT * FROM sqlite_master WHERE type='index'"
        ).fetchall()]
        conn.close()

        assert "idx_livestream_events_camera" in indexes

    def test_table_columns(self, tmp_path):
        """livestream_events must have the expected columns."""
        import asyncio
        import database
        db_path = str(tmp_path / "locus.db")
        with patch.object(database, "settings") as mock_settings:
            mock_settings.database_path = db_path
            asyncio.run(database.init_db())

        conn = sqlite3.connect(db_path)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(livestream_events)").fetchall()]
        conn.close()

        assert set(cols) == {"id", "camera_id", "type", "message", "zone", "timestamp", "created_at"}


# ─── Flush ────────────────────────────────────────────────────────────────────

class TestFlushSqliteEvents:
    def test_flush_writes_events_to_db(self, tmp_db):
        """_flush_sqlite_events must INSERT buffered events into SQLite."""
        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx = StreamContext(camera_id="cam1", source=0)

        ctx._event_write_buffer = [
            {"type": "person", "message": "Person entered Zone A", "zone": "Zone A", "timestamp": 1700000000.0},
            {"type": "vehicle", "message": "Vehicle detected", "zone": None, "timestamp": 1700000005.0},
        ]

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            ctx._flush_sqlite_events()

        conn = sqlite3.connect(tmp_db)
        rows = conn.execute(
            "SELECT type, message, zone, timestamp FROM livestream_events WHERE camera_id = 'cam1' ORDER BY timestamp"
        ).fetchall()
        conn.close()
        ctx.stop()

        assert len(rows) == 2
        assert rows[0] == ("person", "Person entered Zone A", "Zone A", 1700000000.0)
        assert rows[1] == ("vehicle", "Vehicle detected", None, 1700000005.0)

    def test_flush_clears_write_buffer(self, tmp_db):
        """After flush, _event_write_buffer must be empty."""
        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx = StreamContext(camera_id="cam_clear", source=0)

        ctx._event_write_buffer = [
            {"type": "person", "message": "test", "zone": None, "timestamp": time.time()},
        ]

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            ctx._flush_sqlite_events()

        assert ctx._event_write_buffer == []
        ctx.stop()

    def test_flush_noop_when_buffer_empty(self, tmp_db):
        """_flush_sqlite_events must do nothing when the buffer is empty."""
        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx = StreamContext(camera_id="cam_noop", source=0)

        ctx._event_write_buffer = []

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            ctx._flush_sqlite_events()

        conn = sqlite3.connect(tmp_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM livestream_events WHERE camera_id = 'cam_noop'"
        ).fetchone()[0]
        conn.close()
        ctx.stop()

        assert count == 0

    def test_flush_isolates_by_camera(self, tmp_db):
        """Flushed events must be stored under the correct camera_id."""
        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx_a = StreamContext(camera_id="cam_A", source=0)
            ctx_b = StreamContext(camera_id="cam_B", source=0)

        ctx_a._event_write_buffer = [
            {"type": "person", "message": "A event", "zone": None, "timestamp": time.time()},
        ]
        ctx_b._event_write_buffer = [
            {"type": "vehicle", "message": "B event", "zone": None, "timestamp": time.time()},
        ]

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            ctx_a._flush_sqlite_events()
            ctx_b._flush_sqlite_events()

        conn = sqlite3.connect(tmp_db)
        count_a = conn.execute(
            "SELECT COUNT(*) FROM livestream_events WHERE camera_id = 'cam_A'"
        ).fetchone()[0]
        count_b = conn.execute(
            "SELECT COUNT(*) FROM livestream_events WHERE camera_id = 'cam_B'"
        ).fetchone()[0]
        conn.close()
        ctx_a.stop()
        ctx_b.stop()

        assert count_a == 1
        assert count_b == 1


# ─── Preload ──────────────────────────────────────────────────────────────────

class TestPreloadRecentEvents:
    def _seed_events(self, db_path, camera_id, events):
        conn = sqlite3.connect(db_path)
        conn.executemany(
            "INSERT INTO livestream_events (camera_id, type, message, zone, timestamp) VALUES (?,?,?,?,?)",
            [(camera_id, e["type"], e["message"], e.get("zone"), e["timestamp"]) for e in events]
        )
        conn.commit()
        conn.close()

    def test_preload_fills_ring_buffer(self, tmp_db):
        """_preload_recent_events must populate recent_events from SQLite."""
        self._seed_events(tmp_db, "cam_pre", [
            {"type": "person", "message": "Person seen", "zone": "Entrance", "timestamp": 1700000001.0},
            {"type": "zone", "message": "Zone crossed", "zone": "Exit", "timestamp": 1700000002.0},
        ])

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx = StreamContext(camera_id="cam_pre", source=0)

        assert len(ctx.recent_events) == 2
        types = [e["type"] for e in ctx.recent_events]
        assert "person" in types
        assert "zone" in types
        ctx.stop()

    def test_preload_preserves_oldest_first_order(self, tmp_db):
        """Ring buffer must be ordered oldest→newest (newest at right end of deque)."""
        ts_base = 1700000000.0
        events = [
            {"type": "person", "message": f"Event {i}", "zone": None, "timestamp": ts_base + i}
            for i in range(5)
        ]
        self._seed_events(tmp_db, "cam_order", events)

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx = StreamContext(camera_id="cam_order", source=0)

        timestamps = [e["timestamp"] for e in ctx.recent_events]
        assert timestamps == sorted(timestamps)
        ctx.stop()

    def test_preload_respects_200_limit(self, tmp_db):
        """Preload must not exceed 200 events (deque maxlen)."""
        events = [
            {"type": "person", "message": f"Event {i}", "zone": None, "timestamp": 1700000000.0 + i}
            for i in range(250)
        ]
        self._seed_events(tmp_db, "cam_limit", events)

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx = StreamContext(camera_id="cam_limit", source=0)

        assert len(ctx.recent_events) == 200
        ctx.stop()

    def test_preload_empty_when_no_prior_events(self, tmp_db):
        """Ring buffer must start empty for a brand-new camera with no DB rows."""
        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx = StreamContext(camera_id="cam_new", source=0)

        assert len(ctx.recent_events) == 0
        ctx.stop()

    def test_preload_isolates_by_camera(self, tmp_db):
        """Preload must only load events for the correct camera_id."""
        self._seed_events(tmp_db, "cam_X", [
            {"type": "person", "message": "X event", "zone": None, "timestamp": 1700000001.0},
        ])
        self._seed_events(tmp_db, "cam_Y", [
            {"type": "vehicle", "message": "Y event", "zone": None, "timestamp": 1700000002.0},
            {"type": "alert", "message": "Y alert", "zone": None, "timestamp": 1700000003.0},
        ])

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx = StreamContext(camera_id="cam_X", source=0)

        assert len(ctx.recent_events) == 1
        assert list(ctx.recent_events)[0]["type"] == "person"
        ctx.stop()


# ─── Round-trip ───────────────────────────────────────────────────────────────

class TestPersistenceRoundTrip:
    def test_flush_then_preload_survives_restart(self, tmp_db):
        """Events flushed by one StreamContext must be visible to a new one (simulates restart)."""
        events = [
            {"type": "person", "message": "Seen before restart", "zone": "Lobby", "timestamp": 1700000010.0},
            {"type": "alert", "message": "Alert before restart", "zone": "Gate", "timestamp": 1700000020.0},
        ]

        # Simulate first run — flush events
        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext
            ctx1 = StreamContext(camera_id="cam_restart", source=0)

        ctx1._event_write_buffer = events[:]
        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            ctx1._flush_sqlite_events()
        ctx1.stop()

        # Simulate restart — new StreamContext should preload those events
        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.livestream_manager import StreamContext as StreamContext2
            ctx2 = StreamContext2(camera_id="cam_restart", source=0)

        loaded = list(ctx2.recent_events)
        assert len(loaded) == 2
        assert loaded[0]["message"] == "Seen before restart"
        assert loaded[1]["message"] == "Alert before restart"
        ctx2.stop()


# ─── Archiver pruning ─────────────────────────────────────────────────────────

class TestArchiverPruning:
    def _seed_events(self, db_path, camera_id, events):
        conn = sqlite3.connect(db_path)
        conn.executemany(
            "INSERT INTO livestream_events (camera_id, type, message, zone, timestamp) VALUES (?,?,?,?,?)",
            [(camera_id, e["type"], e["message"], e.get("zone"), e["timestamp"]) for e in events]
        )
        conn.commit()
        conn.close()

    def test_archiver_deletes_old_events(self, tmp_db):
        """Archiver must delete livestream_events older than retention_days."""
        now = time.time()
        retention_days = 7
        old_ts = now - (retention_days + 1) * 86400  # 1 day beyond cutoff
        new_ts = now - 3600  # 1 hour ago — within retention

        self._seed_events(tmp_db, "cam_archive", [
            {"type": "person", "message": "Old event", "zone": None, "timestamp": old_ts},
            {"type": "person", "message": "Recent event", "zone": None, "timestamp": new_ts},
        ])

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.archiver import Archiver
            archiver = Archiver(retention_days=retention_days)
            archiver.run_archival()

        conn = sqlite3.connect(tmp_db)
        rows = conn.execute(
            "SELECT message FROM livestream_events WHERE camera_id = 'cam_archive'"
        ).fetchall()
        conn.close()

        messages = [r[0] for r in rows]
        assert "Old event" not in messages
        assert "Recent event" in messages

    def test_archiver_keeps_events_within_retention(self, tmp_db):
        """Archiver must not delete events that are within the retention window."""
        now = time.time()
        retention_days = 30

        recent_events = [
            {"type": "person", "message": f"Event {i}", "zone": None, "timestamp": now - i * 3600}
            for i in range(5)
        ]
        self._seed_events(tmp_db, "cam_keep", recent_events)

        with patch("config.settings") as mock_settings:
            mock_settings.database_path = tmp_db
            from services.archiver import Archiver
            archiver = Archiver(retention_days=retention_days)
            archiver.run_archival()

        conn = sqlite3.connect(tmp_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM livestream_events WHERE camera_id = 'cam_keep'"
        ).fetchone()[0]
        conn.close()

        assert count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
