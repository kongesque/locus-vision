"""
System monitoring API endpoints.

Provides real-time hardware usage metrics and application performance stats.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from services.metrics_collector import metrics_collector

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/stats")
async def get_system_stats():
    """
    Get current system metrics snapshot.
    
    Returns CPU, memory, disk usage, detector performance, and per-camera stats.
    """
    return metrics_collector.get_full_stats()


@router.get("/history")
async def get_metrics_history(seconds: int = 60):
    """
    Get historical system metrics for charting.
    
    Args:
        seconds: Number of seconds of history to return (default: 60, max: 300)
    
    Returns:
        Arrays of timestamps and metric values for plotting.
    """
    seconds = min(seconds, 300)  # Cap at 5 minutes
    
    history = metrics_collector.get_system_history(seconds)
    
    return {
        "timestamps": [m.timestamp for m in history],
        "cpu": [m.cpu_percent for m in history],
        "memory": [m.memory_percent for m in history],
        "memory_used_mb": [m.memory_used_mb for m in history],
        "disk_used_gb": [m.disk_used_gb for m in history],
    }


@router.get("/cameras")
async def get_camera_stats():
    """Get detailed metrics for all cameras."""
    cameras = metrics_collector.get_camera_stats()
    
    return {
        "cameras": [
            {
                "id": cam.camera_id,
                "is_active": cam.is_active,
                "input_fps": round(cam.input_fps, 1),
                "processed_fps": round(cam.processed_fps, 1),
                "dropped_frames": cam.dropped_frames,
                "total_frames": cam.total_frames,
                "inference_ms": round(cam.inference_ms, 1),
                "inference_count": cam.inference_count,
            }
            for cam in cameras.values()
        ]
    }


@router.get("/detector")
async def get_detector_stats(window_seconds: int = 60):
    """
    Get detector performance statistics.
    
    Args:
        window_seconds: Time window for aggregation (default: 60)
    
    Returns:
        Average, min, max inference times and detection counts.
    """
    return metrics_collector.get_detector_stats(window_seconds)


@router.get("/storage")
async def get_storage_stats():
    """Get storage usage breakdown."""
    import os
    import glob
    from pathlib import Path
    
    # Get base storage info
    system = metrics_collector.get_current_system_stats()
    
    # Calculate recordings directory size
    recordings_dir = Path("backend/data/recordings")
    recordings_size_gb = 0
    recordings_count = 0
    
    if recordings_dir.exists():
        try:
            for f in recordings_dir.rglob("*"):
                if f.is_file():
                    recordings_size_gb += f.stat().st_size
                    recordings_count += 1
            recordings_size_gb /= (1024 ** 3)
        except Exception:
            pass
    
    # Calculate database size
    db_size_mb = 0
    db_path = Path("backend/data/locusvision.db")
    if db_path.exists():
        try:
            db_size_mb = db_path.stat().st_size / (1024 ** 2)
        except Exception:
            pass
    
    return {
        "total": {
            "used_gb": round(system.disk_used_gb, 2) if system else 0,
            "total_gb": round(system.disk_total_gb, 2) if system else 0,
            "percent": round((system.disk_used_gb / system.disk_total_gb * 100), 1) if system and system.disk_total_gb > 0 else 0,
        },
        "recordings": {
            "size_gb": round(recordings_size_gb, 2),
            "file_count": recordings_count,
        },
        "database": {
            "size_mb": round(db_size_mb, 2),
        },
    }
