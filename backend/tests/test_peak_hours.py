"""Tests for the /api/analytics/peak-hours endpoint logic."""

import pytest
import os
from datetime import datetime, timedelta

from services.duckdb_client import DuckDBClient

TEST_DB_PATH = "data/test_peak_hours.duckdb"


@pytest.fixture
def db_client():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    client = DuckDBClient(db_path=TEST_DB_PATH)
    yield client
    client.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def _run_peak_hours_query(conn, start_time, end_time, camera_id=None, zone_id=None):
    """
    Reproduce the same SQL logic used by the /api/analytics/peak-hours endpoint
    so we can test it without spinning up the full FastAPI app.
    """
    query = """
    SELECT
        EXTRACT(HOUR FROM timestamp)::INTEGER AS hour,
        COUNT(DISTINCT track_id)              AS count,
        COALESCE(AVG(dwell_time), 0)          AS avg_dwell
    FROM zone_events
    WHERE timestamp >= ? AND timestamp <= ?
    """
    params = [start_time, end_time]

    if camera_id:
        query += " AND camera_id = ?"
        params.append(camera_id)
    if zone_id:
        query += " AND zone_id = ?"
        params.append(zone_id)

    query += " GROUP BY hour ORDER BY hour"

    results = conn.execute(query, params).fetchall()

    hour_map = {h: {"hour": h, "count": 0, "avg_dwell": 0.0} for h in range(24)}
    total_events = 0
    for row in results:
        h, cnt, dwell = int(row[0]), int(row[1]), float(row[2])
        hour_map[h] = {"hour": h, "count": cnt, "avg_dwell": round(dwell, 2)}
        total_events += cnt

    hours = list(hour_map.values())
    peak = max(hours, key=lambda x: x["count"])

    return {
        "hours": hours,
        "peak_hour": peak["hour"],
        "peak_count": peak["count"],
        "total_events": total_events,
    }


def test_peak_hours_identifies_busiest_hour(db_client):
    """Insert events concentrated at hour 14 and verify it is identified as peak."""
    base = datetime(2026, 3, 1, 0, 0, 0)
    events = []

    # Heavy traffic at 14:00 — 50 unique tracks
    for i in range(50):
        events.append((base.replace(hour=14, minute=i % 60), "cam1", "zone1", "enter", i, 5.0))

    # Moderate traffic at 09:00 — 20 unique tracks
    for i in range(20):
        events.append((base.replace(hour=9, minute=i % 60), "cam1", "zone1", "enter", 100 + i, 3.0))

    # Light traffic at 03:00 — 3 unique tracks
    for i in range(3):
        events.append((base.replace(hour=3, minute=i), "cam1", "zone1", "enter", 200 + i, 1.0))

    db_client.insert_zone_events(events)

    result = _run_peak_hours_query(
        db_client.conn,
        start_time=base - timedelta(hours=1),
        end_time=base + timedelta(hours=24),
    )

    assert result["peak_hour"] == 14
    assert result["peak_count"] == 50
    assert result["total_events"] == 73  # 50 + 20 + 3
    assert len(result["hours"]) == 24


def test_peak_hours_all_hours_present(db_client):
    """Even with no data, the response should contain all 24 hours with count 0."""
    result = _run_peak_hours_query(
        db_client.conn,
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 2),
    )
    assert len(result["hours"]) == 24
    assert result["total_events"] == 0
    assert all(h["count"] == 0 for h in result["hours"])


def test_peak_hours_camera_filter(db_client):
    """Filtering by camera_id should only return events for that camera."""
    base = datetime(2026, 3, 1, 10, 0, 0)
    events = [
        (base, "cam1", "zone1", "enter", 1, 2.0),
        (base, "cam1", "zone1", "enter", 2, 2.0),
        (base, "cam2", "zone1", "enter", 3, 2.0),
    ]
    db_client.insert_zone_events(events)

    result = _run_peak_hours_query(
        db_client.conn,
        start_time=base - timedelta(hours=1),
        end_time=base + timedelta(hours=1),
        camera_id="cam1",
    )

    assert result["peak_hour"] == 10
    assert result["peak_count"] == 2  # only cam1's tracks
    assert result["total_events"] == 2


def test_peak_hours_avg_dwell(db_client):
    """Average dwell time should be computed correctly for the peak hour."""
    base = datetime(2026, 3, 1, 15, 0, 0)
    events = [
        (base, "cam1", "zone1", "enter", 1, 10.0),
        (base, "cam1", "zone1", "exit", 1, 20.0),
    ]
    db_client.insert_zone_events(events)

    result = _run_peak_hours_query(
        db_client.conn,
        start_time=base - timedelta(hours=1),
        end_time=base + timedelta(hours=1),
    )

    hour_15 = next(h for h in result["hours"] if h["hour"] == 15)
    assert hour_15["avg_dwell"] == 15.0  # (10 + 20) / 2
