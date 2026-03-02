"""
System and application metrics collection service for LocusVision.

Collects CPU, memory, storage usage and application-level metrics
like detection FPS, inference latency, and camera stream health.
"""

import time
import asyncio
import psutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from collections import deque
from threading import Lock


@dataclass
class SystemMetrics:
    """System-level metrics snapshot."""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_used_gb: float
    disk_total_gb: float


@dataclass
class CameraMetrics:
    """Per-camera performance metrics."""
    camera_id: str
    timestamp: float
    input_fps: float = 0.0
    processed_fps: float = 0.0
    dropped_frames: int = 0
    total_frames: int = 0
    inference_ms: float = 0.0
    inference_count: int = 0
    is_active: bool = False


@dataclass
class DetectorMetrics:
    """ONNX detector performance metrics."""
    timestamp: float
    inference_ms: float
    num_detections: int
    model_name: str


class MetricsCollector:
    """
    Singleton metrics collector for LocusVision.
    
    Collects system metrics every second and aggregates application
    metrics from instrumented components.
    """
    _instance: Optional['MetricsCollector'] = None
    _lock: Lock = Lock()
    
    def __new__(cls) -> 'MetricsCollector':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, retention_seconds: int = 300):
        if self._initialized:
            return
            
        self.retention_seconds = retention_seconds
        
        # System metrics history (1 sample per second)
        self._system_history: deque[SystemMetrics] = deque(maxlen=retention_seconds)
        
        # Per-camera metrics (current snapshot)
        self._camera_metrics: Dict[str, CameraMetrics] = {}
        self._camera_lock = Lock()
        
        # Detector metrics (rolling window of recent inferences)
        self._detector_history: deque[DetectorMetrics] = deque(maxlen=1000)
        self._detector_lock = Lock()
        
        # Background task control
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        self._initialized = True
    
    async def start(self):
        """Start the background metrics collection loop."""
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._collection_loop())
        print("[MetricsCollector] Started")
    
    def stop(self):
        """Stop the background collection loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        print("[MetricsCollector] Stopped")
    
    async def _collection_loop(self):
        """Background loop that collects system metrics every second."""
        while self._running:
            try:
                self._collect_system_metrics()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[MetricsCollector] Error in collection loop: {e}")
                await asyncio.sleep(1)
    
    def _collect_system_metrics(self):
        """Collect current system resource usage."""
        try:
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics = SystemMetrics(
                timestamp=time.time(),
                cpu_percent=psutil.cpu_percent(interval=None),
                memory_percent=mem.percent,
                memory_used_mb=mem.used / 1024 / 1024,
                memory_total_mb=mem.total / 1024 / 1024,
                disk_used_gb=disk.used / 1024 / 1024 / 1024,
                disk_total_gb=disk.total / 1024 / 1024 / 1024,
            )
            self._system_history.append(metrics)
        except Exception as e:
            print(f"[MetricsCollector] Error collecting system metrics: {e}")
    
    # ── Camera Metrics API ─────────────────────────────────────────
    
    def register_camera(self, camera_id: str):
        """Register a new camera for metrics tracking."""
        with self._camera_lock:
            if camera_id not in self._camera_metrics:
                self._camera_metrics[camera_id] = CameraMetrics(
                    camera_id=camera_id,
                    timestamp=time.time(),
                    is_active=True
                )
    
    def unregister_camera(self, camera_id: str):
        """Mark a camera as inactive."""
        with self._camera_lock:
            if camera_id in self._camera_metrics:
                self._camera_metrics[camera_id].is_active = False
    
    def record_camera_frame(self, camera_id: str, processed: bool = True, 
                           inference_ms: float = 0):
        """
        Record a frame processed by a camera.
        
        Args:
            camera_id: Unique camera identifier
            processed: Whether the frame was successfully processed
            inference_ms: Time spent in AI detection (if applicable)
        """
        with self._camera_lock:
            if camera_id not in self._camera_metrics:
                self.register_camera(camera_id)
            
            cam = self._camera_metrics[camera_id]
            cam.timestamp = time.time()
            cam.total_frames += 1
            
            if processed:
                cam.processed_fps = self._calculate_rolling_fps(cam.processed_fps)
            else:
                cam.dropped_frames += 1
            
            if inference_ms > 0:
                # Rolling average of inference time
                if cam.inference_count == 0:
                    cam.inference_ms = inference_ms
                else:
                    cam.inference_ms = (cam.inference_ms * 0.9) + (inference_ms * 0.1)
                cam.inference_count += 1
    
    def update_camera_input_fps(self, camera_id: str, fps: float):
        """Update the input FPS for a camera (from stream metadata)."""
        with self._camera_lock:
            if camera_id in self._camera_metrics:
                self._camera_metrics[camera_id].input_fps = fps
    
    def _calculate_rolling_fps(self, current_fps: float, alpha: float = 0.9) -> float:
        """Calculate exponential moving average for FPS."""
        # This is a simplified calculation - in practice, you'd track
        # timestamps and calculate actual FPS over a window
        return current_fps * alpha + (1 / alpha) * 0.1
    
    # ── Detector Metrics API ────────────────────────────────────────
    
    def record_detection(self, inference_ms: float, num_detections: int, 
                        model_name: str):
        """
        Record an inference from the ONNX detector.
        
        Args:
            inference_ms: Time spent in model inference
            num_detections: Number of objects detected
            model_name: Name of the model used
        """
        with self._detector_lock:
            self._detector_history.append(DetectorMetrics(
                timestamp=time.time(),
                inference_ms=inference_ms,
                num_detections=num_detections,
                model_name=model_name
            ))
    
    # ── Query API ───────────────────────────────────────────────────
    
    def get_current_system_stats(self) -> Optional[SystemMetrics]:
        """Get the most recent system metrics."""
        if self._system_history:
            return self._system_history[-1]
        return None
    
    def get_system_history(self, seconds: int = 60) -> List[SystemMetrics]:
        """Get historical system metrics for the last N seconds."""
        return list(self._system_history)[-seconds:]
    
    def get_camera_stats(self) -> Dict[str, CameraMetrics]:
        """Get current metrics for all cameras."""
        with self._camera_lock:
            return dict(self._camera_metrics)
    
    def get_detector_stats(self, window_seconds: int = 60) -> dict:
        """Get aggregated detector statistics."""
        with self._detector_lock:
            cutoff = time.time() - window_seconds
            recent = [m for m in self._detector_history if m.timestamp > cutoff]
            
            if not recent:
                return {
                    "avg_inference_ms": 0,
                    "min_inference_ms": 0,
                    "max_inference_ms": 0,
                    "total_inferences": 0,
                    "avg_detections": 0,
                    "model_name": "unknown"
                }
            
            inferences = [m.inference_ms for m in recent]
            detections = [m.num_detections for m in recent]
            models = set(m.model_name for m in recent)
            
            return {
                "avg_inference_ms": sum(inferences) / len(inferences),
                "min_inference_ms": min(inferences),
                "max_inference_ms": max(inferences),
                "total_inferences": len(recent),
                "avg_detections": sum(detections) / len(detections) if detections else 0,
                "model_name": list(models)[0] if len(models) == 1 else "mixed"
            }
    
    def get_full_stats(self) -> dict:
        """Get complete metrics snapshot for API response."""
        system = self.get_current_system_stats()
        detector = self.get_detector_stats()
        cameras = self.get_camera_stats()
        
        return {
            "timestamp": time.time(),
            "system": {
                "cpu_percent": system.cpu_percent if system else 0,
                "memory_percent": system.memory_percent if system else 0,
                "memory_used_mb": round(system.memory_used_mb, 1) if system else 0,
                "memory_total_mb": round(system.memory_total_mb, 1) if system else 0,
                "disk_used_gb": round(system.disk_used_gb, 2) if system else 0,
                "disk_total_gb": round(system.disk_total_gb, 2) if system else 0,
            },
            "detector": detector,
            "cameras": [
                {
                    "id": cam.camera_id,
                    "is_active": cam.is_active,
                    "input_fps": round(cam.input_fps, 1),
                    "processed_fps": round(cam.processed_fps, 1),
                    "dropped_frames": cam.dropped_frames,
                    "total_frames": cam.total_frames,
                    "inference_ms": round(cam.inference_ms, 1),
                }
                for cam in cameras.values()
            ],
            "summary": {
                "active_cameras": sum(1 for c in cameras.values() if c.is_active),
                "total_cameras": len(cameras),
            }
        }


# Global singleton instance
metrics_collector = MetricsCollector()
