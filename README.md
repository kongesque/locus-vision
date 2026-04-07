![Locus Vision — self-hosted video analytics platform for edge devices](./banner.png)

<h1 align="center">Locus Vision — Open-Source Video Analytics</h1>

<p align="center">
  <strong>Self-hosted, real-time video analytics for edge devices and Raspberry Pi</strong><br/>
  Turn any camera into a smart sensor — people counting, object detection, line crossing, and zone analytics. No cloud. No subscriptions. Runs fully local.
</p>

<p align="center">
  <a href="https://github.com/kongesque/locus-vision/stargazers"><img src="https://img.shields.io/github/stars/kongesque/locus-vision?style=flat&color=f5a623" alt="GitHub stars" /></a>
  <a href="https://github.com/kongesque/locus-vision/blob/main/LICENSE"><img src="https://img.shields.io/github/license/kongesque/locus-vision?color=blue" alt="License" /></a>
  <a href="https://github.com/kongesque/locus-vision/issues"><img src="https://img.shields.io/github/issues/kongesque/locus-vision" alt="Open issues" /></a>
  <a href="https://github.com/kongesque/locus-vision/commits/main"><img src="https://img.shields.io/github/last-commit/kongesque/locus-vision" alt="Last commit" /></a>
  <img src="https://img.shields.io/badge/platform-edge%20devices-c51a4a" alt="Platform: edge devices" />
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen" alt="PRs welcome" />
</p>

---

Locus Vision is an **open-source, self-hosted video analytics platform** built for edge devices and Raspberry Pi. It performs real-time **people counting, object detection, and multi-object tracking** using YOLO + ONNX Runtime, with support for **INT8/FP16 quantized models** that cut model size by 70% while maintaining accuracy. Everything runs locally — no cloud, no subscriptions, no data leaving your network.

Whether you need a **computer vision dashboard** for retail foot traffic, a **local CCTV analytics** system for warehouses, or a **people counter** for any space, Locus Vision runs entirely on-device — including on a Raspberry Pi 5 with the Hailo-8L AI HAT.

https://github.com/user-attachments/assets/647da3b4-74e2-4da8-872c-6d9200b7c0af

## Features

### Real-Time Monitoring
- **Object Detection & Tracking** — YOLO models (v5–v11) via ONNX Runtime + ByteTrack multi-object tracking across concurrent camera streams
- **People Counting & Zone Analytics** — Polygon zones for occupancy counting, directional line crossing (A→B, B→A, or both), dwell time measurement, capacity alerts
- **Live Streams** — MJPEG video with overlaid detections, real-time spatial heatmaps, and SSE-based event feeds per camera

### Camera Configuration
- **Visual Zone Editor** — Draw polygon zones and directional lines directly on a live preview canvas
- **Per-Class Filtering** — Select which object classes to detect per camera (person, vehicle, etc.)
- **Granular Controls** — Per-camera confidence threshold, FPS cap, and model selection
- **Camera Flexibility** — RTSP streams, ONVIF auto-discovery, USB webcams, V4L2 hardware decoding

### Intelligence & Insights
- **Adaptive Models** — Auto-detects hardware (Hailo-8L, CUDA, CoreML, CPU ARM) and picks the optimal model format
- **Model Library UI** — Browse and download YOLO models with one click, or drag-and-drop your own models (.onnx, .tflite, .pt); hardware-appropriate precision auto-selected
- **Rich Analytics** — Peak hours analysis, hourly crowd aggregations, spatial heatmaps, CSV/JSON export for downstream BI tools
- **Batch Video Processing** — Upload recorded footage for offline analysis with a crash-resilient job queue, per-task progress, and result thumbnails

### Operations & Admin
- **Multi-User Access** — JWT + Argon2id auth with role-based access (admin/viewer), session management, and rate-limited login (5 attempts / 5 min)
- **User Management** — Admin controls for user creation, role assignment, and public signup toggle; users can update profile and change password
- **System Monitoring** — Per-camera FPS breakdown (input, process, detect, skipped), detector latency percentiles (p50/p90/p99), CPU/memory/storage with historical charts
- **Prometheus Metrics** — Scrape `/api/metrics` for system, camera, and detector telemetry
- **Data Archival** — Automatic downsampling of old metrics and cleanup of orphaned video files

## Use Cases

- **Retail Foot Traffic Analytics** — Count visitors entering/exiting zones, measure dwell time, identify peak hours across store areas
- **Warehouse & Logistics Monitoring** — Monitor loading docks, track forklift movement, detect restricted zone breaches
- **Parking Occupancy Detection** — Track parking space occupancy in real time, log vehicle entry/exit with directional line crossing
- **Crowd Analytics & People Counting** — Measure occupancy in public spaces, offices, or events without cloud dependency
- **Wildlife & Environmental Monitoring** — Observe animal activity patterns, generate spatial heatmaps from trail cameras

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | SvelteKit 5, Svelte 5, TypeScript |
| Styling | Tailwind CSS 4, shadcn-svelte |
| Backend | FastAPI, Python 3.11+ |
| Database | SQLite / aiosqlite (operational), DuckDB (analytics / Parquet) |
| AI / Vision | ONNX Runtime, TFLite Runtime, YOLO (v5–v11), ByteTrack, OpenCV, Hailo-8L |
| Auth | JWT (access + refresh tokens), Argon2id |

## Quick Start

### Docker (recommended)

```sh
git clone https://github.com/kongesque/locus-vision.git
cd locusvision
docker compose up --build
```

Open [localhost:3000](http://localhost:3000) (app) or [localhost:8000/api/docs](http://localhost:8000/api/docs) (API docs).

### Manual

> **Requires Python 3.11–3.12** (for TFLite Runtime and full ML package compatibility).

```sh
# Clone & install
git clone https://github.com/kongesque/locus-vision.git
cd locusvision && pnpm install

# Setup backend (Python 3.11 or 3.12)
cd backend && python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cd ..

# Run
pnpm dev
```

Open [localhost:5173](http://localhost:5173) (app) or [localhost:8000/api/docs](http://localhost:8000/api/docs) (API docs).

### First-Time Setup

On first launch, navigate to `/get-started` to create the initial admin account. After that, additional users can be invited by an admin or (optionally) self-register if public signup is enabled in **Settings > Admin**.

## Model Management

Models are managed from **Settings > Models** in the UI. The system auto-detects your hardware (Hailo, CUDA, CoreML, or CPU) and shows which formats are compatible for each model.

**Downloading models:**
- Click "Download" next to any model to fetch it from GitHub Releases
- The best precision for your hardware is automatically selected (INT8 on Pi, FP32 on Mac/desktop)
- No additional dependencies required on your machine

**Uploading custom models:**
- Drag and drop model files directly into the **Upload Model** area in Settings > Models
- Supported formats:
  - **`.onnx`** — ONNX models, ready to use immediately
  - **`.tflite`** — TensorFlow Lite models, optimized for ARM/edge devices
  - **`.pt`** — PyTorch models, auto-converted to ONNX on upload (requires `ultralytics`)
- All uploads are validated before saving — invalid models are rejected with a clear error
- Non-COCO models (custom classes) are accepted with a warning about label mapping

**Current models:** YOLO11 (n/s/m/l/x), YOLOv8 (n/s), YOLOv6n, YOLOv5 variants, YOLOX. See `MODELS.md` for the full list and available formats per model.

**For developers:** To add new models to the release, export them with the CLI tool (requires `ultralytics` on your dev machine only):

```sh
source backend/.venv/bin/activate
pip install ultralytics
python backend/scripts/export_model.py yolo11n --int8
# Then upload to the GitHub release and update model_catalog.json with the download URL
```

## Performance

All numbers are **inference-only** (ONNX Runtime, 640×640 input, 15s timed run after 3s warmup). End-to-end stream FPS is lower due to video decode, tracking, and analytics overhead.

### High-compute reference — Apple M5 (16 GB)

| Model | Size | FPS | Latency (median) | Latency (p99) |
|-------|------|-----|------------------|---------------|
| YOLO11n | 10 MB | **200** | 5.0 ms | 6.6 ms |
| YOLO11s | 36 MB | **118** | 8.5 ms | 9.9 ms |
| YOLO11m | 77 MB | **62** | 16.1 ms | 19.4 ms |

> FP32, CoreML (Apple Neural Engine), ONNX Runtime 1.24.2. 15s timed run after 3s warmup, 2s cooldown between models. FPS derived from median latency.

### Edge reference — Raspberry Pi 5 (8 GB)

#### CPU-only (ARM Cortex-A76)

| Model | Precision | Size | FPS | Latency (median) | Latency (p99) |
|-------|-----------|------|-----|------------------|---------------|
| YOLO11n | FP32 | 10 MB | **5** | 188.9 ms | 275.5 ms |
| YOLO11n | INT8 | 3 MB | **14** | 69.9 ms | 93.7 ms |

> ONNX Runtime 1.24.4. Static INT8 quantization with QDQ nodes. 15s timed run after 3s warmup, 2s cooldown between models. FPS derived from median latency.

#### Hailo-8L AI HAT+ (PCIe, 13 TOPS)

| Model | Size | FPS | HW Latency |
|-------|------|-----|------------|
| YOLOv6n | 14 MB | **355** | 7.0 ms |
| YOLOv5n-seg | 7 MB | **65** | 14.2 ms |
| YOLOv8s | 35 MB | **59** | 13.1 ms |
| YOLOv5s-personface | 26 MB | **64** | 13.7 ms |
| YOLOX-s | 21 MB | **61** | 14.8 ms |
| YOLOv8s-pose | 23 MB | **51** | 18.9 ms |

> HailoRT 4.23.0, HEF format. `hailortcli benchmark`, streaming mode (includes host-side DMA transfer). 15s per model. End-to-end app FPS will be lower due to host-side preprocessing (letterbox resize, normalization) and postprocessing (NMS, tracking, zone analytics). YOLO11 HEF models not yet available — compiled from pre-built Hailo model zoo.

To reproduce:

```sh
# CPU benchmark
cd backend && source .venv/bin/activate
python scripts/benchmark_inference.py

# Hailo benchmark
hailortcli benchmark /usr/share/hailo-models/<model>.hef
```

## Contributing

Contributions welcome — bug reports, feature requests, and pull requests all help. See [open issues](https://github.com/kongesque/locus-vision/issues) for where to start.

## License

[MIT License](LICENSE)

---

Made with ❤️ by <a href="https://github.com/kongesque">kongesque</a>
