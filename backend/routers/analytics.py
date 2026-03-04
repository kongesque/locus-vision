from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
import io
import csv
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel
from services.duckdb_client import client as db_client
import json

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/export")
def export_analytics(
    camera_id: Optional[str] = None,
    zone_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    format: str = Query("json", description="json or csv")
):
    """
    Export zone telemetry data (counts, dwell times) aggregated by hour/day, or raw events.
    """
    if not start_time:
        start_time = datetime.now() - timedelta(days=7)
    if not end_time:
        end_time = datetime.now()
        
    query = """
    SELECT 
        time_bucket(INTERVAL 1 HOUR, timestamp) AS bucket,
        camera_id,
        zone_id,
        event_type,
        COUNT(DISTINCT track_id) as unique_objects,
        AVG(dwell_time) as avg_dwell_time
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
        
    query += " GROUP BY bucket, camera_id, zone_id, event_type ORDER BY bucket DESC"
    
    try:
        results = db_client.conn.execute(query, params).fetchall()
        columns = ["bucket", "camera_id", "zone_id", "event_type", "unique_objects", "avg_dwell_time"]
        
        data = []
        for row in results:
            data.append(dict(zip(columns, row)))
            
        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data)
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]), 
                media_type="text/csv", 
                headers={"Content-Disposition": "attachment; filename=analytics_export.csv"}
            )
            
        return {"data": data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/peak-hours")
def get_peak_hours(
    camera_id: Optional[str] = None,
    zone_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
):
    """
    Aggregate zone events by hour-of-day (0–23) to identify peak traffic hours.
    Returns per-hour counts and the single busiest hour.
    """
    if not start_time:
        start_time = datetime.now() - timedelta(days=7)
    if not end_time:
        end_time = datetime.now()

    query = """
    SELECT
        EXTRACT(HOUR FROM timestamp)::INTEGER AS hour,
        COUNT(DISTINCT track_id)              AS count,
        COALESCE(AVG(dwell_time), 0)          AS avg_dwell
    FROM zone_events
    WHERE timestamp >= ? AND timestamp <= ?
    """
    params: list = [start_time, end_time]

    if camera_id:
        query += " AND camera_id = ?"
        params.append(camera_id)
    if zone_id:
        query += " AND zone_id = ?"
        params.append(zone_id)

    query += " GROUP BY hour ORDER BY hour"

    try:
        results = db_client.conn.execute(query, params).fetchall()

        # Build a full 0–23 map so the frontend always gets every hour
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap")
def get_heatmap_data(
    camera_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 10000
):
    """
    Returns array of {x, y, weight} coordinates for frontend canvas heatmap rendering.
    """
    if not start_time:
        start_time = datetime.now() - timedelta(hours=24)
    if not end_time:
        end_time = datetime.now()
        
    query = """
    SELECT x, y
    FROM object_tracks
    WHERE camera_id = ? AND timestamp >= ? AND timestamp <= ?
    USING SAMPLE ?
    """
    
    try:
        # We sample the tracks to avoid sending millions of points to the frontend
        results = db_client.conn.execute(query, [camera_id, start_time, end_time, limit]).fetchall()
        
        points = [{"x": row[0], "y": row[1], "value": 1} for row in results]
        return {"points": points}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
