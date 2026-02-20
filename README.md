# Locus Vision

Locus is an open-source, high-performance video analytics engine designed specifically for edge deployment (e.g., Raspberry Pi 5). Locus parses reality in real-time—turning video feeds into structured data, searchable events, and actionable insights.

It is built to be local-first, privacy-centric, and highly optimized for minimal resource usage.

## Tech Stack

| Category | Technology |
|----------|------------|
| Frontend | SvelteKit 2, TypeScript |
| Styling | Tailwind CSS 4, shadcn-svelte |
| Stream Decoding | hls.js (Hardware-accelerated native playback) |
| Backend | FastAPI, Python |
| Database | SQLite (async via aiosqlite) |
| AI / Vision | Ultralytics YOLO (Object Detection, Tracking) |
| Matrix/Math | OpenCV, NumPy |

## Core Architecture

Locus Vision uses a **Dual-Mode Analytics Pipeline** to handle both physical webcams and network streams interchangeably:

- **Webcam Mode**: Video is captured natively via the browser's `getUserMedia()`. Visible frames are rasterized to an offscreen canvas and shipped via WebSocket to the backend for inference.
- **RTSP / HLS Mode**: Instead of a laggy backend MJPEG proxy, the UI utilizes native browser playback. For `.m3u8` HLS streams (e.g., YouTube Live), Locus uses `hls.js` pointing to a backend CORS proxy (`/api/cameras/hls-proxy`). The proxy uses chunked streaming (`StreamingResponse`) to bypass origin restrictions and deliver full-FPS, hardware-decoded video. The frontend captures these playing frames and sends them over WebSocket to ensure perfectly synchronized YOLO bounding boxes.

## Features

- **Live Stream Analytics** — Real-time RTSP/HLS/Webcam feeds overlaid with YOLO object detection.
- **Custom Zones** — Draw polygon detection zones on the live feed to filter tracking to specific areas.
- **Video Processing** — Upload pre-recorded `.mp4` videos for batch YOLO processing.
- **Theme Switching** — Built-in support for auto, dark, and light modes.
- **Authentication** — JWT-based auth with HttpOnly cookies, auto-refresh, and role-based access.

## Quick Start

```sh
# 1. Install frontend dependencies
pnpm install

# 2. Setup backend Python environment using uv (recommended for speed)
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
# Alternatively, install httpx explicitly if missing: uv pip install httpx
cd ..

# 3. Start fullstack dev server (Vite + Uvicorn)
pnpm dev
```

## Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start fullstack dev server |
| `pnpm build` | Production build |
| `pnpm benchmark` | Run build size & performance benchmark script for edge profiling |
