![Locus Vision Banner](./banner.png)

<h1 align="center">Locus Vision 👁️</h1>

<p align="center">
  <strong>Open-source, real-time video analytics engine optimized for edge devices</strong><br/>
  Turn any camera into a smart sensor — object detection, tracking, line crossing, and zone counting at the edge.
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

Locus Vision is a **self-hosted video analytics platform** built for edge devices. It performs real-time **object detection and tracking** using YOLO + ONNX Runtime, with support for **INT8/FP16 quantized models** that cut model size by 70% while maintaining accuracy. Everything stays local — no cloud, no subscriptions, no data leaving your network.

https://github.com/user-attachments/assets/647da3b4-74e2-4da8-872c-6d9200b7c0af

## Features

- 🎯 **Detection & Tracking** — YOLO via ONNX Runtime with ByteTrack multi-object tracking across concurrent camera streams
- 🔲 **Zones & Lines** — Polygon zone counting with dwell time and capacity alerts, directional line crossing with wrong-way detection
- 📹 **Live Streaming** — MJPEG video with real-time telemetry, live heatmaps, and activity feeds
- 🎞️ **Video Processing** — Upload videos for batch analysis with a crash-resilient background job queue
- 📊 **Analytics & Export** — Peak hours analysis, hourly aggregations, CSV/JSON export, Prometheus-compatible metrics
- 📷 **Camera Management** — ONVIF auto-discovery, RTSP streams, USB webcams, V4L2 hardware decoding
- 🧠 **Model Flexibility** — Hot-swap YOLO models from the UI, INT8/FP16 quantization, drag-and-drop `.onnx` import
- 🔒 **Auth & Security** — JWT with rate-limited login, role-based access, session management
- 📈 **System Monitor** — Per-camera FPS breakdown, CPU/memory/storage dashboard, Parquet archival of old data

## Use Cases

- **Retail & Foot Traffic** — Count visitors entering/exiting zones, measure dwell time across store areas
- **Warehouse & Logistics** — Monitor loading docks, track forklift movement, detect restricted zone breaches
- **Parking & Access Control** — Track occupancy in real time, log vehicle entry/exit with line crossing
- **Wildlife & Environmental** — Observe animal activity patterns, generate spatial heatmaps from trail cameras

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | SvelteKit 2, Svelte 5, TypeScript |
| Styling | Tailwind CSS 4, shadcn-svelte |
| Backend | FastAPI, Python 3.11+ |
| Database | SQLite (async), DuckDB (analytics) |
| AI / Vision | ONNX Runtime, YOLO11n, ByteTrack, OpenCV |
| Auth | JWT + Argon2id |

## Quick Start

```sh
# Clone & install
git clone https://github.com/kongesque/locus-vision.git
cd locusvision && pnpm install

# Setup backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cd ..

# Run
pnpm dev
```

Open [localhost:5173](http://localhost:5173) (app) or [localhost:8000/docs](http://localhost:8000/docs) (API docs).

**Optional** — generate an INT8 quantized model for edge deployment:

```sh
source backend/.venv/bin/activate
python backend/scripts/export_model.py yolo11n --int8
```

## Contributing

Contributions welcome — bug reports, feature requests, and pull requests all help. See [open issues](https://github.com/kongesque/locus-vision/issues) for where to start.

## License

[MIT License](LICENSE)

---

Made with ❤️ by <a href="https://github.com/kongesque">kongesque</a>

