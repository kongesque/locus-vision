"""
WebSocket Routes for Live Video Streaming
"""
import asyncio
import base64
import threading
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.db import get_job
from app.core.live_detector import live_detection, stop_live_stream

router = APIRouter()


@router.websocket("/ws/live/{task_id}")
async def live_stream_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for live video streaming.
    Streams processed frames from RTSP/webcam source with detection overlays.
    """
    await websocket.accept()
    
    # Get job data
    job = get_job(task_id)
    if not job:
        await websocket.send_json({"error": "Job not found"})
        await websocket.close()
        return
    
    # Validate source type
    source_type = job.get("source_type")
    if source_type not in ("rtsp", "webcam"):
        await websocket.send_json({"error": "Not a live stream job"})
        await websocket.close()
        return
    
    stream_url = job.get("stream_url")
    zones = job.get("zones", [])
    frame_size = (job.get("frame_width", 640), job.get("frame_height", 480))
    confidence = job.get("confidence", 35)
    model = job.get("model", "yolo11n.pt")
    tracker_config = job.get("tracker_config")
    
    # Queue for passing frames from thread to async handler
    frame_queue = asyncio.Queue(maxsize=2)
    stop_event = threading.Event()
    
    def detection_thread():
        """Run blocking detection in separate thread."""
        try:
            for jpeg_bytes, counts in live_detection(
                stream_url=stream_url,
                zones=zones,
                frame_size=frame_size,
                task_id=task_id,
                conf=confidence,
                model_name=model,
                tracker_config=tracker_config,
                source_type=source_type
            ):
                if stop_event.is_set():
                    break
                # Put frame in queue (drop old frames if full)
                try:
                    frame_queue.put_nowait((jpeg_bytes, counts))
                except asyncio.QueueFull:
                    # Drop oldest frame and add new one
                    try:
                        frame_queue.get_nowait()
                        frame_queue.put_nowait((jpeg_bytes, counts))
                    except:
                        pass
        except Exception as e:
            print(f"Detection thread error: {e}")
        finally:
            stop_live_stream(task_id)
    
    # Start detection in thread
    thread = threading.Thread(target=detection_thread, daemon=True)
    thread.start()
    
    try:
        while True:
            try:
                # Wait for frame with timeout
                jpeg_bytes, counts = await asyncio.wait_for(
                    frame_queue.get(), 
                    timeout=5.0
                )
                
                # Convert and send
                frame_base64 = base64.b64encode(jpeg_bytes).decode("utf-8")
                await websocket.send_json({
                    "type": "frame",
                    "frame": frame_base64,
                    "counts": counts
                })
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        stop_live_stream(task_id)

