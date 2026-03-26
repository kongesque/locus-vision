"""
Locus Jobs API Routes - CRUD operations for video processing jobs
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import os
import csv
import io

from app.models import ProcessRequest, UpdateZonesRequest, RenameRequest
from app.services.db import get_job, update_job, get_all_jobs, delete_job, clear_all_jobs
from app.services.file_handler import handle_upload_file, safe_remove_file
from app.services.processor import run_processing_pipeline

router = APIRouter()


@router.post("")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file and create a new job."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    task_id = handle_upload_file(file, "uploads/videos")
    return {"taskId": task_id, "success": True}


@router.get("")
async def list_jobs(status: str | None = None):
    """Get all jobs, optionally filtered by status."""
    jobs = get_all_jobs(status=status)
    return jobs


@router.delete("/all")
async def clear_all_jobs_endpoint():
    """Delete all jobs and all associated files."""
    # Get all jobs first to clean up files
    jobs = get_all_jobs()
    
    for job in jobs:
        # Clean up associated files
        safe_remove_file(job.get("video_path"))
        safe_remove_file(job.get("frame_path"))
        task_id = job.get("id")
        if task_id:
            output_path = os.path.join("uploads/outputs", f"output_{task_id}.mp4")
            safe_remove_file(output_path)
    
    # Clear database
    clear_all_jobs()
    return {"success": True, "deleted_count": len(jobs)}


@router.get("/{task_id}")
async def get_job_details(task_id: str):
    """Get details of a specific job."""
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job["id"],
        "name": job.get("name"),
        "filename": job.get("filename"),
        "videoPath": job.get("video_path"),
        "framePath": job.get("frame_path"),
        "frameWidth": job.get("frame_width"),
        "frameHeight": job.get("frame_height"),
        "status": job.get("status", "pending"),
        "progress": job.get("progress", 0),
        "zones": job.get("zones", []),
        "confidence": job.get("confidence", 35),
        "model": job.get("model", "yolo11n.pt"),
        "trackerConfig": job.get("tracker_config"),
        "detectionData": job.get("detection_data", []),
        "dwellData": job.get("dwell_data", []),
        "lineCrossingData": job.get("line_crossing_data", {}),
        "heatmapData": job.get("heatmap_data"),
        "processTime": job.get("process_time", 0),
        "sourceType": job.get("source_type", "file"),
        "streamUrl": job.get("stream_url"),
        "createdAt": job.get("created_at"),
    }


@router.patch("/{task_id}")
async def update_job_details(task_id: str, request: RenameRequest):
    """Rename a job."""
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    update_job(task_id, name=request.name)
    return {"success": True}


@router.delete("/{task_id}")
async def remove_job(task_id: str):
    """Delete a job and all associated files."""
    job = get_job(task_id)
    if job:
        safe_remove_file(job.get("video_path"))
        safe_remove_file(job.get("frame_path"))
        output_path = os.path.join("uploads/outputs", f"output_{task_id}.mp4")
        safe_remove_file(output_path)
    
    delete_job(task_id)
    return {"success": True}


@router.get("/{task_id}/zones")
async def get_zones(task_id: str):
    """Get zones for a job."""
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"zones": job.get("zones", [])}


@router.put("/{task_id}/zones")
async def update_zones(task_id: str, request: UpdateZonesRequest):
    """Update zones for a job."""
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    zones_data = [zone.model_dump() for zone in request.zones]
    update_job(task_id, zones=zones_data)
    return {"success": True}


@router.post("/{task_id}/process")
async def process_job(task_id: str, request: ProcessRequest, background_tasks: BackgroundTasks):
    """Start processing a job."""
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    zones_data = [zone.model_dump() for zone in request.zones]
    tracker_config = request.trackerConfig.model_dump() if request.trackerConfig else None
    
    update_job(
        task_id,
        zones=zones_data,
        confidence=request.confidence,
        model=request.model,
        tracker_config=tracker_config,
        status="processing"
    )
    
    if job.get("source_type") in ("rtsp", "webcam"):
        return {"success": True, "redirect": f"/live/{task_id}"}
    
    background_tasks.add_task(
        run_processing_pipeline,
        task_id,
        job,
        zones_data,
        request.confidence,
        request.model,
        tracker_config
    )
    
    return {"success": True, "redirect": f"/result/{task_id}"}


@router.get("/{task_id}/progress")
async def get_progress(task_id: str):
    """Get processing progress for a job."""
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "progress": job.get("progress", 0),
        "status": job.get("status", "pending")
    }


@router.get("/{task_id}/export")
async def export_data(task_id: str, format: str = "json"):
    """Export detection data as CSV or JSON."""
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    detection_data = job.get("detection_data", [])
    zones = job.get("zones", [])
    process_time = job.get("process_time", 0)
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 1. Identify all zones
        # Use zones from job definition to ensure we have labels, plus any seen in data
        job_zones = job.get("zones", [])
        zone_ids = [z["id"] for z in job_zones]
        zone_labels = {z["id"]: z.get("label", z["id"]) for z in job_zones}
        
        # Also include any zone_ids found in data but not in config (just in case)
        data_zone_ids = set(e.get("zone_id") for e in detection_data if e.get("zone_id"))
        for zid in data_zone_ids:
            if zid not in zone_ids:
                zone_ids.append(zid)
                zone_labels[zid] = zid
        
        # Header: Timestamp, then each Zone's Label
        header = ["Timestamp (s)"] + [zone_labels[zid] for zid in zone_ids]
        writer.writerow(header)
        
        # 2. Aggregate data by time
        # Struct: time_data[seconds][zone_id] = count
        time_data = {}
        max_time = 0
        
        for event in detection_data:
            t = int(event.get("time", 0))
            z = event.get("zone_id")
            c = event.get("count", 0)
            
            if t > max_time:
                max_time = t
                
            if t not in time_data:
                time_data[t] = {}
            
            # Assuming 'count' in event is the total count at that time
            # If multiple events for same zone same time, take the latest (or max?)
            # Usually detection_data is a sequence of updates.
            time_data[t][z] = c

        # 3. Write rows for every second
        # If process_time is available, use it as duration, else max_time seen
        duration = int(job.get("process_time", 0)) or max_time
        
        for t in range(duration + 1):
            row = [t]
            for zid in zone_ids:
                # Get count for this zone at this time
                # If no data for this specific second, carry forward previous value?
                # Or is '0' correct? 
                # For "Activity", 0 is correct if no detection.
                # But if "count" is cumulative unique visitors, we should probably carry forward.
                # However, previous existing logic seemed to just dump raw events.
                # Let's write the count if present, else 0 (assuming rate/activity)
                # OR if it's cumulative, we need to know the semantics.
                # Looking at frontend ActivityTimeline, it counts events per bucket.
                # Let's output raw counts per second found in data.
                val = time_data.get(t, {}).get(zid, 0)
                row.append(val)
            writer.writerow(row)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=locus_data_{task_id}.csv"}
        )
    
    # JSON export with statistics
    zone_stats = {}
    for event in detection_data:
        zone_id = event.get("zone_id", "default")
        count = event.get("count", 0)
        time = event.get("time", 0)
        
        if zone_id not in zone_stats:
            zone_stats[zone_id] = {"total": 0, "peak": 0, "peak_time": 0, "events": []}
        
        zone_stats[zone_id]["total"] = count
        if count > zone_stats[zone_id]["peak"]:
            zone_stats[zone_id]["peak"] = count
            zone_stats[zone_id]["peak_time"] = time
        zone_stats[zone_id]["events"].append({"time": time, "count": count})
    
    for zone_id, stats in zone_stats.items():
        if process_time > 0:
            stats["avg_per_minute"] = round(stats["total"] / (process_time / 60), 1)
        else:
            stats["avg_per_minute"] = 0
    
    return {
        "task_id": task_id,
        "process_time": process_time,
        "frame_width": job.get("frame_width"),
        "frame_height": job.get("frame_height"),
        "zones": zones,
        "detection_data": detection_data,
        "statistics": zone_stats
    }
