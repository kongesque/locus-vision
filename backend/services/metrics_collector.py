"""
System and application metrics collection service for LocusVision.

Inspired by Frigate's metrics system - collects CPU, memory, storage usage 
and detailed application metrics like detection FPS, inference latency percentiles,
and per-camera stream health.
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
    processes: List[dict] = field(default_factory=list)


@dataclass
class CameraMetrics:
    """Per-camera performance metrics (Frigate-style)."""
    camera_id: str
    camera_name: str = ""
    timestamp: float = 0
    
    # FPS metrics (Frigate-style)
    input_fps: float = 0.0        # FPS from camera stream
    process_fps: float = 0.0      # FPS processed by detector
    detect_fps: float = 0.0       # FPS with detections
    skipped_fps: float = 0.0      # Frames skipped due to performance
    
    # Frame counters
    dropped_frames: int = 0
    total_frames: int = 0
    
    # Detection metrics
    inference_ms: float = 0.0
    inference_count: int = 0
    
    # Process stats
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    
    is_active: bool = False
    
    # Internal tracking for FPS calculation
    _frame_timestamps: deque = field(default_factory=lambda: deque(maxlen=60))
    _process_timestamps: deque = field(default_factory=lambda: deque(maxlen=60))
    _detect_timestamps: deque = field(default_factory=lambda: deque(maxlen=60))


@dataclass
class DetectorMetrics:
    """ONNX detector performance metrics with percentiles (Frigate-style)."""
    timestamp: float
    inference_ms: float
    num_detections: int
    model_name: str


class MetricsCollector:
    """
    Singleton metrics collector for LocusVision.
    
    Inspired by Frigate's metrics collection:
    - Collects system metrics every second
    - Tracks per-camera input/process/detect FPS separately
    - Calculates inference latency percentiles (p50, p90, p99)
    - Monitors process-level resource usage
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
        """Collect current system resource usage with process breakdown."""
        try:
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Collect process-level metrics (Frigate-style)
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                try:
                    name = proc.info['name']
                    # Track relevant processes
                    if any(x in name.lower() for x in ['python', 'ffmpeg', 'onnx']):
                        processes.append({
                            'name': name,
                            'cpu_percent': proc.info['cpu_percent'] or 0,
                            'memory_mb': (proc.info['memory_info'].rss / 1024 / 1024) if proc.info['memory_info'] else 0
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            metrics = SystemMetrics(
                timestamp=time.time(),
                cpu_percent=psutil.cpu_percent(interval=None),
                memory_percent=mem.percent,
                memory_used_mb=mem.used / 1024 / 1024,
                memory_total_mb=mem.total / 1024 / 1024,
                disk_used_gb=disk.used / 1024 / 1024 / 1024,
                disk_total_gb=disk.total / 1024 / 1024 / 1024,
                processes=processes
            )
            self._system_history.append(metrics)
        except Exception as e:
            print(f"[MetricsCollector] Error collecting system metrics: {e}")
    
    # ── Camera Metrics API (Frigate-style) ─────────────────────────
    
    def register_camera(self, camera_id: str, camera_name: str = ""):
        """Register a new camera for metrics tracking."""
        with self._camera_lock:
            if camera_id not in self._camera_metrics:
                self._camera_metrics[camera_id] = CameraMetrics(
                    camera_id=camera_id,
                    camera_name=camera_name or camera_id[:8],
                    timestamp=time.time(),
                    is_active=True
                )
    
    def unregister_camera(self, camera_id: str):
        """Mark a camera as inactive."""
        with self._camera_lock:
            if camera_id in self._camera_metrics:
                self._camera_metrics[camera_id].is_active = False
    
    def record_camera_frame(self, camera_id: str, processed: bool = True, 
                           had_detection: bool = False, inference_ms: float = 0):
        """
        Record a frame processed by a camera (Frigate-style).
        
        Args:
            camera_id: Unique camera identifier
            processed: Whether the frame went through detection
            had_detection: Whether the frame had objects detected
            inference_ms: Time spent in AI detection
        """
        with self._camera_lock:
            if camera_id not in self._camera_metrics:
                self.register_camera(camera_id)
            
            cam = self._camera_metrics[camera_id]
            now = time.time()
            cam.timestamp = now
            cam.total_frames += 1
            
            # Track frame timestamp for input FPS calculation
            cam._frame_timestamps.append(now)
            
            if processed:
                cam._process_timestamps.append(now)
                
                if had_detection:
                    cam._detect_timestamps.append(now)
                
                if inference_ms > 0:
                    # Rolling average of inference time
                    if cam.inference_count == 0:
                        cam.inference_ms = inference_ms
                    else:
                        cam.inference_ms = (cam.inference_ms * 0.9) + (inference_ms * 0.1)
                    cam.inference_count += 1
            else:
                cam.dropped_frames += 1
            
            # Recalculate FPS metrics
            self._calculate_camera_fps(cam)
    
    def _calculate_camera_fps(self, cam: CameraMetrics):
        """Calculate FPS metrics from timestamps (Frigate-style)."""
        now = time.time()
        window = 5.0  # 5-second window for FPS calculation
        
        # Input FPS: all frames received
        cutoff = now - window
        while cam._frame_timestamps and cam._frame_timestamps[0] < cutoff:
            cam._frame_timestamps.popleft()
        cam.input_fps = len(cam._frame_timestamps) / window if cam._frame_timestamps else 0
        
        # Process FPS: frames that went through detection
        while cam._process_timestamps and cam._process_timestamps[0] < cutoff:
            cam._process_timestamps.popleft()
        cam.process_fps = len(cam._process_timestamps) / window if cam._process_timestamps else 0
        
        # Detect FPS: frames with detections
        while cam._detect_timestamps and cam._detect_timestamps[0] < cutoff:
            cam._detect_timestamps.popleft()
        cam.detect_fps = len(cam._detect_timestamps) / window if cam._detect_timestamps else 0
        
        # Skipped FPS: difference between input and processed
        cam.skipped_fps = max(0, cam.input_fps - cam.process_fps)
    
    def update_camera_input_fps(self, camera_id: str, fps: float):
        """Update the input FPS from stream metadata."""
        with self._camera_lock:
            if camera_id in self._camera_metrics:
                self._camera_metrics[camera_id].input_fps = fps
    
    def update_camera_name(self, camera_id: str, name: str):
        """Update the display name for a camera."""
        with self._camera_lock:
            if camera_id in self._camera_metrics:
                self._camera_metrics[camera_id].camera_name = name
    
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
    
    # ── Query API (Frigate-style) ───────────────────────────────────
    
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
            # Recalculate FPS for all cameras before returning
            for cam in self._camera_metrics.values():
                self._calculate_camera_fps(cam)
            return dict(self._camera_metrics)
    
    def get_detector_stats(self, window_seconds: int = 60) -> dict:
        """
        Get detector statistics with percentiles (Frigate-style).
        
        Returns:
            Dict with p50, p90, p99 percentiles and other stats
        """
        with self._detector_lock:
            cutoff = time.time() - window_seconds
            recent = [m for m in self._detector_history if m.timestamp > cutoff]
            
            if not recent:
                return {
                    "model_name": "unknown",
                    "detector_type": "CPU",
                    "inference_speed": {
                        "p50": 0,
                        "p90": 0,
                        "p99": 0
                    },
                    "total_inferences": 0,
                    "avg_detections": 0
                }
            
            inferences = sorted([m.inference_ms for m in recent])
            detections = [m.num_detections for m in recent]
            models = set(m.model_name for m in recent)
            
            # Calculate percentiles
            def percentile(sorted_data, p):
                if not sorted_data:
                    return 0
                k = (len(sorted_data) - 1) * p / 100
                f = int(k)
                c = f + 1 if f + 1 < len(sorted_data) else f
                return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])
            
            return {
                "model_name": list(models)[0] if len(models) == 1 else "mixed",
                "detector_type": "CPU",  # Could be extended to detect GPU/Coral
                "inference_speed": {
                    "p50": percentile(inferences, 50),
                    "p90": percentile(inferences, 90),
                    "p99": percentile(inferences, 99)
                },
                "total_inferences": len(recent),
                "avg_detections": sum(detections) / len(detections) if detections else 0
            }
    
    def get_storage_stats(self) -> dict:
        """Get storage breakdown (Frigate-style)."""
        import os
        from pathlib import Path
        
        system = self.get_current_system_stats()
        
        # Calculate recordings directory
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
        
        # Database size
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
            }
        }
    
    def get_full_stats(self) -> dict:
        """Get complete metrics snapshot for API response (Frigate-style)."""
        system = self.get_current_system_stats()
        detector = self.get_detector_stats()
        cameras = self.get_camera_stats()
        storage = self.get_storage_stats()
        
        return {
            "timestamp": time.time(),
            "system": {
                "cpu_percent": system.cpu_percent if system else 0,
                "memory_percent": system.memory_percent if system else 0,
                "memory_used_mb": round(system.memory_used_mb, 1) if system else 0,
                "memory_total_mb": round(system.memory_total_mb, 1) if system else 0,
                "processes": system.processes if system else []
            },
            "storage": storage,
            "detector": detector,
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
                    "cpu_percent": round(cam.cpu_percent, 1),
                    "memory_mb": round(cam.memory_mb, 1)
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
