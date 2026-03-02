"""
Prometheus-compatible metrics endpoint.

Exposes system and application metrics in Prometheus text format
for external monitoring systems like Grafana.
"""

from fastapi import APIRouter, Response
from services.metrics_collector import metrics_collector

router = APIRouter(tags=["metrics"])


def _format_prometheus_name(name: str) -> str:
    """Convert metric name to Prometheus format."""
    return f"locusvision_{name}"


@router.get("/api/metrics")
async def prometheus_metrics():
    """
    Return metrics in Prometheus text format.
    
    Compatible with Prometheus scraping. Metrics include:
    - CPU, memory, disk usage
    - Per-camera FPS and frame counts
    - Detector inference latency
    """
    lines = []
    stats = metrics_collector.get_full_stats()
    
    # ── System Metrics ────────────────────────────────────────────
    
    lines.append("# HELP locusvision_cpu_usage_percent Current CPU usage percentage")
    lines.append("# TYPE locusvision_cpu_usage_percent gauge")
    lines.append(f"locusvision_cpu_usage_percent {stats['system']['cpu_percent']}")
    
    lines.append("# HELP locusvision_memory_usage_percent Current memory usage percentage")
    lines.append("# TYPE locusvision_memory_usage_percent gauge")
    lines.append(f"locusvision_memory_usage_percent {stats['system']['memory_percent']}")
    
    lines.append("# HELP locusvision_memory_used_bytes Current memory used in bytes")
    lines.append("# TYPE locusvision_memory_used_bytes gauge")
    lines.append(f"locusvision_memory_used_bytes {stats['system']['memory_used_mb'] * 1024 * 1024}")
    
    lines.append("# HELP locusvision_memory_total_bytes Total system memory in bytes")
    lines.append("# TYPE locusvision_memory_total_bytes gauge")
    lines.append(f"locusvision_memory_total_bytes {stats['system']['memory_total_mb'] * 1024 * 1024}")
    
    lines.append("# HELP locusvision_disk_usage_percent Current disk usage percentage")
    lines.append("# TYPE locusvision_disk_usage_percent gauge")
    lines.append(f"locusvision_disk_usage_percent {stats['system']['disk_used_gb'] / stats['system']['disk_total_gb'] * 100 if stats['system']['disk_total_gb'] > 0 else 0}")
    
    lines.append("# HELP locusvision_disk_used_bytes Current disk used in bytes")
    lines.append("# TYPE locusvision_disk_used_bytes gauge")
    lines.append(f"locusvision_disk_used_bytes {stats['system']['disk_used_gb'] * 1024 * 1024 * 1024}")
    
    # ── Camera Metrics ────────────────────────────────────────────
    
    lines.append("# HELP locusvision_camera_input_fps Input frames per second per camera")
    lines.append("# TYPE locusvision_camera_input_fps gauge")
    for cam in stats['cameras']:
        lines.append(f'locusvision_camera_input_fps{{camera="{cam["id"]}"}} {cam["input_fps"]}')
    
    lines.append("# HELP locusvision_camera_processed_fps Processed frames per second per camera")
    lines.append("# TYPE locusvision_camera_processed_fps gauge")
    for cam in stats['cameras']:
        lines.append(f'locusvision_camera_processed_fps{{camera="{cam["id"]}"}} {cam["processed_fps"]}')
    
    lines.append("# HELP locusvision_camera_dropped_frames Total dropped frames per camera")
    lines.append("# TYPE locusvision_camera_dropped_frames counter")
    for cam in stats['cameras']:
        lines.append(f'locusvision_camera_dropped_frames{{camera="{cam["id"]}"}} {cam["dropped_frames"]}')
    
    lines.append("# HELP locusvision_camera_active Whether the camera stream is active (1=active, 0=inactive)")
    lines.append("# TYPE locusvision_camera_active gauge")
    for cam in stats['cameras']:
        active = 1 if cam["is_active"] else 0
        lines.append(f'locusvision_camera_active{{camera="{cam["id"]}"}} {active}')
    
    # ── Detector Metrics ──────────────────────────────────────────
    
    detector = stats['detector']
    
    lines.append("# HELP locusvision_detector_inference_ms Average inference latency in milliseconds")
    lines.append("# TYPE locusvision_detector_inference_ms gauge")
    lines.append(f'locusvision_detector_inference_ms{{model="{detector["model_name"]}"}} {detector["avg_inference_ms"]}')
    
    lines.append("# HELP locusvision_detector_inferences_total Total number of inferences performed")
    lines.append("# TYPE locusvision_detector_inferences_total counter")
    lines.append(f'locusvision_detector_inferences_total {{model="{detector["model_name"]}"}} {detector["total_inferences"]}')
    
    lines.append("# HELP locusvision_detector_avg_detections Average detections per inference")
    lines.append("# TYPE locusvision_detector_avg_detections gauge")
    lines.append(f'locusvision_detector_avg_detections{{model="{detector["model_name"]}"}} {detector["avg_detections"]}')
    
    # ── Summary Metrics ───────────────────────────────────────────
    
    lines.append("# HELP locusvision_active_cameras Number of currently active camera streams")
    lines.append("# TYPE locusvision_active_cameras gauge")
    lines.append(f"locusvision_active_cameras {stats['summary']['active_cameras']}")
    
    lines.append("# HELP locusvision_total_cameras Total number of registered cameras")
    lines.append("# TYPE locusvision_total_cameras gauge")
    lines.append(f"locusvision_total_cameras {stats['summary']['total_cameras']}")
    
    return Response(content="\n".join(lines), media_type="text/plain")
