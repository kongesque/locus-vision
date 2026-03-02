# LocusVision Hardware Monitoring Implementation Plan

Based on research of Frigate NVR and other systems, this plan outlines a phased approach to implement hardware usage monitoring and dashboards in LocusVision.

---

## 🎯 Goals

1. **Visibility**: Real-time insight into CPU, memory, storage, and AI inference performance
2. **Debugging**: Identify bottlenecks (slow detection, dropped frames, memory leaks)
3. **Optimization**: Capacity planning for camera additions and hardware upgrades
4. **Production Ready**: Prometheus metrics for external monitoring (optional)

---

## 📊 Metrics to Track

### System-Level Metrics
| Metric | Source | Purpose |
|--------|--------|---------|
| CPU usage % | `psutil` | Overall system load |
| Memory usage % | `psutil` | RAM consumption |
| Storage used/total | `shutil` / `psutil` | Disk space for recordings |
| GPU usage (if applicable) | `pynvml` / `onnxruntime` | Hardware acceleration efficiency |

### Application-Level Metrics
| Metric | Source | Purpose |
|--------|--------|---------|
| Detection FPS | `OnnxDetector` | Inference throughput |
| Inference latency (ms) | `OnnxDetector.detect()` | Model performance |
| Input FPS per camera | `CameraWorker` | Stream health |
| Processed FPS per camera | `AnalyticsEngine` | Processing throughput |
| Skipped/Dropped frames | `CameraWorker` | Bottleneck detection |
| Active streams count | `LivestreamManager` | Load indicator |
| Events generated/min | `AnalyticsEngine` | Detection activity |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      LocusVision Backend                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  SystemMonitor  │  │  MetricsStore   │  │ MetricsEndpoint │  │
│  │   (collector)   │──│   (in-memory)   │──│  (Prometheus)   │  │
│  └────────┬────────┘  └─────────────────┘  └─────────────────┘  │
│           │                                                     │
│  ┌────────▼────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  OnnxDetector   │  │  CameraWorker   │  │ AnalyticsEngine│  │
│  │  (instrumented) │  │  (instrumented) │  │ (instrumented) │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LocusVision Frontend                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              /system Route (SvelteKit)                   │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │   │
│  │  │   Overview  │ │   Cameras   │ │     Storage         │ │   │
│  │  │  Dashboard  │ │   Stats     │ │     Analytics       │ │   │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼ (Optional)
┌─────────────────────────────────────────────────────────────────┐
│              External Monitoring (Prometheus + Grafana)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 File Structure

```
backend/
├── services/
│   ├── metrics_collector.py    # System & app metrics collection
│   ├── metrics_store.py        # In-memory ring buffer for metrics
│   └── onnx_detector.py        # Already instrumented (add timing)
├── routers/
│   ├── system.py               # /api/system/* endpoints
│   └── metrics.py              # /api/metrics (Prometheus format)
└── main.py                     # Register routers + startup tasks

src/routes/(app)/
├── system/                     # NEW: System monitoring page
│   ├── +page.svelte           # Main dashboard
│   ├── +page.server.ts        # Load initial metrics
│   ├── CameraStats.svelte     # Per-camera metrics
│   ├── SystemOverview.svelte  # CPU/Memory charts
│   └── StoragePanel.svelte    # Disk usage
└── ...
```

---

## 🚀 Implementation Phases

### Phase 1: Backend Metrics Collection
**Effort**: Medium | **Priority**: High

#### 1.1 Create `services/metrics_collector.py`
```python
"""System and application metrics collection service."""
import psutil
import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import deque

@dataclass
class SystemMetrics:
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_used_gb: float
    disk_total_gb: float

@dataclass  
class CameraMetrics:
    camera_id: str
    timestamp: float
    input_fps: float
    processed_fps: float
    dropped_frames: int
    detection_fps: float
    inference_ms: float

@dataclass
class DetectorMetrics:
    timestamp: float
    inference_ms: float
    detections_per_frame: float
    model_name: str

class MetricsCollector:
    """
    Collects system and application metrics with configurable retention.
    """
    def __init__(self, retention_seconds: int = 300):
        self.retention = retention_seconds
        self.system_history: deque[SystemMetrics] = deque(maxlen=retention_seconds)
        self.camera_metrics: Dict[str, CameraMetrics] = {}
        self.detector_history: deque[DetectorMetrics] = deque(maxlen=1000)
        self._running = False
    
    async def start(self):
        """Start background collection loop."""
        self._running = True
        while self._running:
            self._collect_system_metrics()
            await asyncio.sleep(1)
    
    def _collect_system_metrics(self):
        """Collect current system metrics."""
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
        self.system_history.append(metrics)
    
    def record_camera_frame(self, camera_id: str, processed: bool, 
                           inference_ms: float = 0):
        """Record per-camera frame processing stats."""
        # Update rolling counters for FPS calculation
        pass
    
    def record_detection(self, inference_ms: float, 
                        num_detections: int, model_name: str):
        """Record detector inference metrics."""
        self.detector_history.append(DetectorMetrics(
            timestamp=time.time(),
            inference_ms=inference_ms,
            detections_per_frame=num_detections,
            model_name=model_name
        ))
    
    def get_current_stats(self) -> dict:
        """Get latest metrics snapshot for API."""
        # Return aggregated stats
        pass
```

#### 1.2 Instrument Existing Services

**`services/onnx_detector.py`** - Add timing:
```python
import time

class OnnxDetector:
    def detect(self, frame, classes=None):
        start = time.perf_counter()
        # ... existing detection code ...
        inference_ms = (time.perf_counter() - start) * 1000
        
        # Emit to metrics collector
        if hasattr(self, '_metrics_callback'):
            self._metrics_callback(inference_ms, len(boxes_xyxy))
        
        return DetectionResult(...)
```

**`services/camera_worker.py`** - Add FPS tracking:
```python
class CameraWorker:
    def __init__(self, ...):
        self.frame_count = 0
        self.processed_count = 0
        self.dropped_count = 0
        self.last_fps_calc = time.time()
        self.current_fps = 0
    
    def process_frame(self, frame):
        self.frame_count += 1
        # Process...
        self.processed_count += 1
```

#### 1.3 Create `routers/system.py`
```python
from fastapi import APIRouter, Depends
from typing import List

router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/stats")
async def get_system_stats():
    """Get current system metrics snapshot."""
    return {
        "cpu_percent": 23.5,
        "memory_percent": 45.2,
        "memory_used_mb": 2048,
        "memory_total_mb": 8192,
        "disk_used_gb": 45.2,
        "disk_total_gb": 128.0,
        "cameras": [
            {
                "id": "cam_01",
                "input_fps": 25.0,
                "processed_fps": 24.8,
                "dropped_frames": 2,
                "inference_ms": 15.2
            }
        ],
        "detector": {
            "model": "yolo11n",
            "avg_inference_ms": 14.5,
            "detections_per_sec": 12.3
        }
    }

@router.get("/history")
async def get_metrics_history(seconds: int = 300):
    """Get historical metrics for charts."""
    return {
        "timestamps": [...],
        "cpu": [...],
        "memory": [...]
    }
```

---

### Phase 2: Prometheus Metrics Endpoint
**Effort**: Low | **Priority**: Medium

#### 2.1 Create `routers/metrics.py`
```python
"""Prometheus-compatible metrics endpoint."""
from fastapi import APIRouter, Response

router = APIRouter(tags=["metrics"])

@router.get("/api/metrics")
async def prometheus_metrics():
    """Return metrics in Prometheus text format."""
    lines = []
    
    # System metrics
    lines.append("# HELP locus_cpu_usage_percent CPU usage percentage")
    lines.append("# TYPE locus_cpu_usage_percent gauge")
    lines.append(f"locus_cpu_usage_percent {get_current_cpu()}")
    
    # Camera metrics
    lines.append("# HELP locus_camera_input_fps Input FPS per camera")
    lines.append("# TYPE locus_camera_input_fps gauge")
    for cam in get_cameras():
        lines.append(f'locus_camera_input_fps{{camera="{cam.id}"}} {cam.input_fps}')
    
    # Detection metrics
    lines.append("# HELP locus_detector_inference_ms Detection inference time")
    lines.append("# TYPE locus_detector_inference_ms histogram")
    
    return Response(content="\n".join(lines), media_type="text/plain")
```

---

### Phase 3: Frontend Dashboard
**Effort**: Medium | **Priority**: High

#### 3.1 Create `src/routes/(app)/system/+page.svelte`
```svelte
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import SystemOverview from './SystemOverview.svelte';
	import CameraStats from './CameraStats.svelte';
	import StoragePanel from './StoragePanel.svelte';
	
	let stats: SystemStats | null = $state(null);
	let refreshInterval: ReturnType<typeof setInterval>;
	
	async function fetchStats() {
		const res = await fetch('/api/system/stats');
		stats = await res.json();
	}
	
	onMount(() => {
		fetchStats();
		refreshInterval = setInterval(fetchStats, 2000);
	});
	
	onDestroy(() => {
		clearInterval(refreshInterval);
	});
</script>

<div class="container mx-auto p-6 space-y-6">
	<h1 class="text-3xl font-bold">System</h1>
	
	{#if stats}
		<SystemOverview {stats} />
		<CameraStats cameras={stats.cameras} />
		<StoragePanel storage={stats.storage} />
	{:else}
		<div class="animate-pulse">Loading...</div>
	{/if}
</div>
```

#### 3.2 Create `SystemOverview.svelte`
```svelte
<script lang="ts">
	import { Progress } from '$lib/components/ui/progress';
	
	interface Props {
		stats: SystemStats;
	}
	let { stats }: Props = $props();
</script>

<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
	<!-- CPU Card -->
	<div class="bg-card p-4 rounded-lg border">
		<div class="flex items-center justify-between">
			<h3 class="font-semibold">CPU</h3>
			<span class="text-2xl font-bold">{stats.cpu_percent.toFixed(1)}%</span>
		</div>
		<Progress value={stats.cpu_percent} class="mt-2" />
	</div>
	
	<!-- Memory Card -->
	<div class="bg-card p-4 rounded-lg border">
		<div class="flex items-center justify-between">
			<h3 class="font-semibold">Memory</h3>
			<span class="text-2xl font-bold">{stats.memory_percent.toFixed(1)}%</span>
		</div>
		<Progress value={stats.memory_percent} class="mt-2" />
		<p class="text-sm text-muted-foreground mt-1">
			{stats.memory_used_mb.toFixed(0)} / {stats.memory_total_mb.toFixed(0)} MB
		</p>
	</div>
	
	<!-- Detector Card -->
	<div class="bg-card p-4 rounded-lg border">
		<div class="flex items-center justify-between">
			<h3 class="font-semibold">Detector</h3>
			<span class="text-sm text-muted-foreground">{stats.detector.model}</span>
		</div>
		<p class="text-2xl font-bold mt-1">{stats.detector.avg_inference_ms.toFixed(1)}ms</p>
		<p class="text-sm text-muted-foreground">inference time</p>
	</div>
</div>
```

#### 3.3 Create `CameraStats.svelte` with Real-time FPS Charts
```svelte
<script lang="ts">
	// Show per-camera metrics in a table + mini sparklines
	// Using a simple SVG sparkline or lightweight chart library
</script>

<div class="bg-card rounded-lg border overflow-hidden">
	<table class="w-full">
		<thead class="bg-muted">
			<tr>
				<th class="p-3 text-left">Camera</th>
				<th class="p-3 text-right">Input FPS</th>
				<th class="p-3 text-right">Processed FPS</th>
				<th class="p-3 text-right">Dropped</th>
				<th class="p-3 text-right">Inference</th>
			</tr>
		</thead>
		<tbody>
			{#each cameras as cam}
				<tr class="border-t">
					<td class="p-3">{cam.name}</td>
					<td class="p-3 text-right">{cam.input_fps.toFixed(1)}</td>
					<td class="p-3 text-right">{cam.processed_fps.toFixed(1)}</td>
					<td class="p-3 text-right">
						{#if cam.dropped_frames > 0}
							<span class="text-destructive">{cam.dropped_frames}</span>
						{:else}
							<span class="text-muted-foreground">0</span>
						{/if}
					</td>
					<td class="p-3 text-right">{cam.inference_ms.toFixed(1)}ms</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
```

---

### Phase 4: Optional Grafana Integration
**Effort**: Low | **Priority**: Low

When users want external monitoring, they can:

1. **Prometheus config**:
```yaml
scrape_configs:
  - job_name: 'locusvision'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /api/metrics
```

2. **Import pre-built Grafana dashboard** (provide JSON)

---

### Phase 5: Alerts & Thresholds
**Effort**: Medium | **Priority**: Low

Add alert rules to backend:
```python
# In metrics_collector.py
ALERT_THRESHOLDS = {
    'cpu_percent': 85,
    'memory_percent': 90,
    'disk_percent': 80,
    'inference_ms': 100,  # Alert if detection takes >100ms
}

async def check_alerts(self):
    """Check thresholds and emit alerts."""
    if stats.cpu_percent > ALERT_THRESHOLDS['cpu_percent']:
        await self._emit_alert('high_cpu', f'CPU at {stats.cpu_percent}%')
```

Frontend shows alerts in a toast/notification area.

---

## 📦 Dependencies

### Backend
```txt
# Add to requirements.txt
psutil>=5.9.0
prometheus-client>=0.17.0  # Optional, for /metrics endpoint
```

### Frontend
```bash
# Optional: For historical charts
npm install chart.js
# Or use simple SVG sparklines for lighter footprint
```

---

## 🧪 Testing

1. **Unit tests** for metrics collection
2. **Integration tests** for `/api/system/*` endpoints
3. **Load testing** - verify metrics don't impact performance
4. **UI tests** - dashboard renders correctly with mock data

---

## 📋 Implementation Checklist

### Phase 1
- [ ] Create `metrics_collector.py` service
- [ ] Add instrumentation to `OnnxDetector`
- [ ] Add instrumentation to `CameraWorker`/`AnalyticsEngine`
- [ ] Create `system.py` router with endpoints
- [ ] Register collector in `main.py` startup

### Phase 2  
- [ ] Create `/api/metrics` Prometheus endpoint
- [ ] Add `prometheus-client` dependency
- [ ] Test with `curl localhost:8000/api/metrics`

### Phase 3
- [ ] Create `/system` route
- [ ] Build `SystemOverview` component
- [ ] Build `CameraStats` component  
- [ ] Build `StoragePanel` component
- [ ] Add sidebar navigation link
- [ ] Add auto-refresh (2s interval)

### Phase 4 (Optional)
- [ ] Create Grafana dashboard JSON
- [ ] Document Prometheus setup

### Phase 5 (Optional)
- [ ] Add threshold configuration
- [ ] Implement alert system
- [ ] Add UI notifications

---

## 🎨 UI Mockup

```
┌─────────────────────────────────────────────────────────────┐
│ System                                      [Auto-refresh ▼] │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ CPU         │ │ Memory      │ │ Detector    │           │
│  │ 23.5%       │ │ 45.2%       │ │ yolo11n     │           │
│  │ ████░░░░░░  │ │ █████░░░░░  │ │ 14.5ms      │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────┤
│ Cameras                                                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Camera      Input  Processed  Dropped  Inference       │ │
│ │ ─────────────────────────────────────────────────────  │ │
│ │ Front Door   25.0     24.8        2      15.2ms       │ │
│ │ Backyard     25.0     25.0        0      14.8ms       │ │
│ │ Garage       15.0     15.0        0      15.1ms       │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Storage                                                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Recordings: 45.2 GB / 128 GB (35%)                     │ │
│ │ ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │ │
│ │ Database: 234 MB                                        │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔮 Future Enhancements

1. **Historical data** - Store metrics in SQLite for long-term trends
2. **Export** - Download metrics as CSV/JSON
3. **Mobile app** - Push notifications for alerts
4. **Multi-node** - Aggregate metrics from multiple LocusVision instances
5. **AI-powered alerts** - Detect anomalies in patterns

---

## 📚 References

- Frigate Metrics Docs: https://docs.frigate.video/configuration/metrics
- Frigate Grafana Dashboard: https://grafana.com/grafana/dashboards/24165-frigate-monitoring-dashboard/
- Prometheus Metrics Format: https://prometheus.io/docs/instrumenting/exposition_formats/
- psutil Documentation: https://psutil.readthedocs.io/
