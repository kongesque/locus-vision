# Hailo-8L AI HAT+ Integration Plan

Integrating the Raspberry Pi AI HAT+ (Hailo-8L, 13 TOPS) as an inference backend for LocusVision.

## Current Architecture

```
Camera/Video → AnalyticsEngine → OnnxDetector → ONNX Runtime (CPU)
                                     ↓
                              .onnx files in data/models/
                              FP32 / FP16 / INT8 (static)
                              YOLO output [1, 84, N] → manual NMS
```

## Target Architecture

```
Camera/Video → AnalyticsEngine → get_detector(model_name)
                                     ├── OnnxDetector  (.onnx → CPU)
                                     └── HailoDetector (.hef → Hailo-8L NPU)
                                            ↓
                                     HailoRT 4.23.0
                                     NHWC UINT8 input (no host-side normalization)
                                     NMS baked into HEF (model-specific output format)
```

## Benchmark Results

### CPU-only (ARM Cortex-A76, ONNX Runtime 1.24.4)

| Model | Precision | Size | FPS | Latency (median) |
|-------|-----------|------|-----|------------------|
| YOLO11n | FP32 | 10 MB | **5** | 188.9 ms |
| YOLO11n | INT8 (static) | 3 MB | **14** | 69.9 ms |

### Hailo-8L (PCIe, HailoRT 4.23.0, streaming mode)

| Model | Size | FPS | HW Latency |
|-------|------|-----|------------|
| YOLOv6n | 14 MB | **355** | 7.0 ms |
| YOLOv5n-seg | 7 MB | **65** | 14.2 ms |
| YOLOv5s-personface | 26 MB | **64** | 13.7 ms |
| YOLOv8s | 35 MB | **59** | 13.1 ms |
| YOLOX-s | 21 MB | **61** | 14.8 ms |
| YOLOv8s-pose | 23 MB | **51** | 18.9 ms |

> Streaming mode includes host-side DMA transfer. End-to-end app FPS will be lower due to host-side preprocessing (letterbox resize) and postprocessing (tracking, zone analytics).

### Key Takeaway

Hailo-8L is **4-25x faster** than CPU depending on model size. Even the "slowest" Hailo model (YOLOv8s-pose at 51 FPS) is still **3.6x faster** than the fastest CPU option (INT8 at 14 FPS).

## Known Issues

### HailoRT Python SDK Crashes

The Python SDK (`hailo_platform`) segfaults after loading a second model or on repeated VDevice creation/destruction. The `hailortcli` tool does not have this problem.

**Workaround**: Reload `hailo_pci` kernel module between benchmark runs:
```sh
sudo modprobe -r hailo_pci && sleep 2 && sudo modprobe hailo_pci && sleep 2
```

**Impact on integration**: May need subprocess-based inference (`hailortcli run`) instead of in-process Python API, or a long-lived VDevice singleton with careful lifecycle management.

### No YOLO11 HEF Models

Hailo's pre-built model zoo (`/usr/share/hailo-models/`) has YOLOv5, YOLOv6, YOLOv8, YOLOX — but no YOLO11. Compiling ONNX → HEF requires the Hailo Model Compiler (cloud tool, not available on-device).

### Postprocessing Varies Per Model

Unlike ONNX where all YOLO variants share the same `[1, 84, N]` output format, Hailo HEF models have NMS baked in with model-specific output shapes:

- `yolov8s_h8l`: output `(80, 5, 100)` — 80 classes × (4 bbox + 1 score) × 100 max detections
- `yolov5n_seg_h8l_mz`: segmentation output, different format
- `yolov8s_pose_h8l_pi`: pose keypoints + detections

Each model needs its own output parser.

---

## Implementation Phases

### Phase 1: Backend — Hailo Detector Service

Create the core inference abstraction.

#### New: `backend/services/hailo_detector.py`

`HailoDetector` class with the same public interface as `OnnxDetector`:

- `__init__(self, model_path: str, conf_threshold: float)`
  - Loads HEF via `VDevice.create_infer_model(path, '')`
  - Creates bindings, configures network group
  - Stores input shape from HEF metadata
- `get_detections(self, frame, classes=None) -> supervision.Detections`
  - Resize frame to model input size (NHWC, UINT8 — no float normalization)
  - Set input buffer, run inference, get output buffer
  - Parse NMS output format (model-specific) → `supervision.Detections(xyxy, confidence, class_id)`
- `detect(self, frame, classes=None) -> DetectionResult`
  - Wraps `get_detections()`, converts to custom `DetectionResult` format
- Singleton cache via `get_hailo_detector(model_name, conf_threshold)`

Key difference from ONNX: Hailo does normalization and NMS in hardware. No host-side letterbox padding, no NMS loop. Just resize → UINT8 → infer → parse structured output.

#### New: `backend/services/hailo_device.py`

Singleton managing the VDevice connection:

- Holds a single `VDevice` instance for the entire app lifetime
- `get_vdevice() -> VDevice` — lazy init, thread-safe
- `reload_driver()` — automated recovery when Hailo crashes
  - Detects `HAILO_OUT_OF_PHYSICAL_DEVICES` errors
  - Runs `sudo modprobe -r hailo_pci && sudo modprobe hailo_pci`
  - Re-creates VDevice
- Tracks active HEF network groups (Hailo-8L has limited concurrent slots)
- Health check: `is_available() -> bool`

#### Modify: `backend/services/onnx_detector.py`

- Extract shared interface: `detect()`, `get_detections()`, model loading
- Add `list_hailo_models()` — scans `/usr/share/hailo-models/` for `.hef` files
- Modify `get_detector(model_name, conf_threshold)`:
  - If `model_name` ends with `.hef` or matches a known HEF model → return `HailoDetector`
  - Otherwise → return `OnnxDetector` (existing behavior)
  - Both cached in the same `_detector_cache` dict

#### Modify: `backend/services/analytics_engine.py`

- No changes needed. Already takes `model_name` as a string. `get_detector()` handles routing.

### Phase 2: Backend — Model Management

Expose Hailo models through the API.

#### Modify: `backend/routers/models.py`

- `GET /api/models/registry` — return unified list:
  ```json
  [
    { "name": "yolo11n", "backend": "cpu", "size_mb": 10.2, "available": true },
    { "name": "yolo11n_int8", "backend": "cpu", "size_mb": 3.1, "available": true },
    { "name": "yolov8s_h8l", "backend": "hailo", "size_mb": 34.9, "available": true, "input_shape": [640, 640, 3] }
  ]
  ```
- `GET /api/models/hailo` — detailed HEF metadata (architecture, input/output shapes, NMS config)
  - Parses via `hailortcli parse-hef <path>` subprocess

#### Modify: `backend/services/model_manager.py`

- Hailo models are pre-installed (no download/export needed)
- `start_download()` should return immediately with "ready" status for HEF models
- Optionally: add ability to copy user-provided `.hef` files into `/usr/share/hailo-models/`

#### Modify: `backend/models.py`

- Add `backend: str = "cpu"` field to `CameraCreate`, `CameraUpdate`, `CameraResponse`
- Or auto-detect: if `model_name` contains `"h8l"` or `"h8"` → backend is `"hailo"`

### Phase 3: Frontend — Model Selection UI

#### Modify: `src/routes/(app)/create/[taskId]/+page.svelte`

- Extend model catalog to include both ONNX and Hailo models
- Fetch from unified `/api/models/registry` endpoint
- Group by backend in the UI

#### Modify: `src/lib/components/create/tools-panel.svelte`

- Show backend badge per model: "CPU" or "Hailo" with chip icon
- Conditional precision toggle:
  - ONNX models: show INT8 / FP16 / FP32 selector (existing)
  - Hailo models: hide precision selector (HEF is pre-compiled, no user choice)
- Hailo models always show "Ready" status (pre-installed)
- Add estimated FPS hint per model (from known benchmark data)

### Phase 4: Metrics & Telemetry

#### Modify: `backend/services/metrics_collector.py`

- Replace hardcoded `detector_type: "CPU"` (line 362) with actual backend from detector
- Read backend from `AnalyticsEngine` or detector instance
- Add Hailo-specific metrics if available:
  - Accelerator temperature (via `hailortcli fw-control identify` or sysfs)
  - NPU utilization
- Update system metrics to show `hailo_pci` in process breakdown

### Phase 5: Benchmark Script

#### New: `backend/scripts/benchmark_hailo.py`

- Wraps `hailortcli benchmark` for each HEF model
- Handles driver reload between models automatically
- Outputs markdown table (same format as `benchmark_inference.py`)
- Usage: `python3 scripts/benchmark_hailo.py --markdown`

---

## Files Changed

| File | Action | Phase | Description |
|------|--------|-------|-------------|
| `backend/services/hailo_detector.py` | NEW | 1 | Hailo inference service |
| `backend/services/hailo_device.py` | NEW | 1 | VDevice lifecycle + driver recovery |
| `backend/services/onnx_detector.py` | MODIFY | 1 | Routing logic, `list_hailo_models()`, shared interface |
| `backend/services/analytics_engine.py` | NONE | 1 | No change (routing is in `get_detector()`) |
| `backend/routers/models.py` | MODIFY | 2 | Unified ONNX + HEF registry endpoint |
| `backend/services/model_manager.py` | MODIFY | 2 | HEF model discovery |
| `backend/models.py` | MODIFY | 2 | Backend field on camera/task models |
| `backend/config.py` | MODIFY | 2 | Hailo config (models dir, device index) |
| `src/routes/(app)/create/[taskId]/+page.svelte` | MODIFY | 3 | Unified model catalog |
| `src/lib/components/create/tools-panel.svelte` | MODIFY | 3 | Backend-aware model selector |
| `backend/services/metrics_collector.py` | MODIFY | 4 | Dynamic detector type, Hailo metrics |
| `backend/scripts/benchmark_hailo.py` | NEW | 5 | Hailo benchmark script |

## Open Questions

1. **Python SDK vs subprocess**: HailoRT Python SDK segfaults on repeated model loads. Should we use `hailortcli run` as a subprocess instead? Adds latency per inference but is stable.

2. **Concurrent HEF loading**: Hailo-8L has limited network group slots. How many HEF models can be loaded simultaneously? Need to test with 2-3 cameras using different models.

3. **YOLO11 HEF compilation**: No pre-built YOLO11 HEF exists. Options:
   - Wait for Hailo to add YOLO11 to their model zoo
   - Use Hailo Model Compiler (cloud) to compile from ONNX → HEF
   - Stick with YOLOv8 on Hailo, YOLO11 on CPU

4. **NMS output parsing**: Each HEF model has different output structure. Need to either:
   - Ship model-specific parsers (maintainable for the 6 pre-built models)
   - Parse HEF metadata dynamically to determine output format
   - Use Hailo's postprocess library (`hailo_tappas`) if it handles this

5. **Camera model switching**: If a user changes a camera from CPU model to Hailo model (or vice versa), need to unload the old detector and load the new one. VDevice may need to be reconfigured.
