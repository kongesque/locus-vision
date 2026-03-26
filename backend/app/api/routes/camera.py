"""
Camera/Live Stream API Routes
"""
from fastapi import APIRouter, HTTPException
import cv2

from app.models import CameraRequest, TestConnectionRequest
from app.services.db import get_job
from app.services.file_handler import handle_rtsp_source
from app.core.live_detector import stop_live_stream, get_stream_counts, get_stream_analytics, is_stream_running

router = APIRouter()


@router.post("/camera")
async def create_camera_stream(request: CameraRequest):
    """Create a live stream job from RTSP URL or webcam."""
    try:
        task_id = handle_rtsp_source(request.stream_url, request.source_type)
        return {"taskId": task_id, "success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@router.post("/camera/test")
async def test_camera_connection(request: TestConnectionRequest):
    """Test connection to an RTSP stream."""
    try:
        cap = cv2.VideoCapture(request.stream_url)
        success = False
        for _ in range(30):
            success, frame = cap.read()
            if success:
                break
        
        if success:
            height, width = frame.shape[:2]
            cap.release()
            return {"success": True, "width": width, "height": height}
        else:
            cap.release()
            return {"success": False, "error": "Could not read frame from stream"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/live/{task_id}/stop")
async def stop_stream(task_id: str):
    """Stop a live stream."""
    stop_live_stream(task_id)
    return {"success": True}


@router.get("/live/{task_id}/counts")
async def live_counts(task_id: str):
    """Get current counts for a running stream."""
    counts = get_stream_counts(task_id)
    return {"counts": counts, "running": is_stream_running(task_id)}


@router.get("/live/{task_id}/analytics")
async def live_analytics(task_id: str):
    """Get comprehensive analytics data for a running stream."""
    analytics = get_stream_analytics(task_id)
    if analytics is None:
        raise HTTPException(status_code=404, detail="Stream not found")
    return analytics
