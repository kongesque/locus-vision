"""
System monitoring API endpoints (Frigate-style).

Provides real-time hardware usage metrics and detailed application performance stats
including per-camera FPS breakdown (input/process/detect/skipped) and 
inference latency percentiles.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from services.metrics_collector import metrics_collector

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/stats")
async def get_system_stats():
    """
    Get current system metrics snapshot (Frigate-style).
    
    Returns:
    - CPU, memory usage with process breakdown
    - Storage breakdown (recordings, database)
    - Detector inference percentiles (p50, p90, p99)
    - Per-camera FPS metrics (input, process, detect, skipped)
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
    }


@router.get("/cameras")
async def get_camera_stats():
    """Get detailed metrics for all cameras (Frigate-style)."""
    cameras = metrics_collector.get_camera_stats()
    
    return {
        "cameras": [
            {
                "id": cam.camera_id,
                "name": cam.camera_name,
                "is_active": cam.is_active,
                "input_fps": round(cam.input_fps, 1),
                "process_fps": round(cam.process_fps, 1),
                "detect_fps": round(cam.detect_fps, 1),
                "skipped_fps": round(cam.skipped_fps, 1),
                "dropped_frames": cam.dropped_frames,
                "total_frames": cam.total_frames,
                "inference_ms": round(cam.inference_ms, 1),
            }
            for cam in cameras.values()
        ]
    }


@router.get("/detector")
async def get_detector_stats(window_seconds: int = 60):
    """
    Get detector performance statistics with percentiles.
    
    Args:
        window_seconds: Time window for aggregation (default: 60)
    
    Returns:
        p50, p90, p99 inference latencies and detection counts.
    """
    return metrics_collector.get_detector_stats(window_seconds)


@router.get("/storage")
async def get_storage_stats():
    """Get storage usage breakdown (Frigate-style)."""
    return metrics_collector.get_storage_stats()
