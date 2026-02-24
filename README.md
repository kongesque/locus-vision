# Locus Vision

Locus is an open-source, high-performance video analytics engine designed specifically for the Raspberry Pi 5 (8GB). Locus parses reality in real-time—turning video feeds into structured data, searchable events, and actionable insights.

It is built to be local-first, privacy-centric, and highly optimized for edge deployment. Lightweight, fast, minimal resource usage.

## Tech Stack

| Category | Technology |
|----------|------------|
| Frontend | SvelteKit 2, TypeScript |
| Styling | Tailwind CSS 4 |
| UI Components | shadcn-svelte, mode-watcher (Themes) |
| Backend | FastAPI, Python |
| Database | SQLite (async via aiosqlite) |
| AI / Vision | ONNX Runtime (YOLO11n), ByteTrack (supervision), OpenCV |
| Auth | JWT (access + refresh tokens), Argon2id |
| Build | Vite |
| Testing | Vitest |
| Linting | ESLint + Prettier |

## Features

- **Edge-Optimized AI** — Lightweight ONNX Runtime inference (~15MB engine) replaces heavy PyTorch dependencies, halving the backend footprint for Raspberry Pi 5 deployment.
- **Unified Analytics Engine** — Shared stateful object tracking (ByteTrack) and zone-based ROI counting logic serving both real-time streams and recorded video tasks.
- **Directional Line Crossing** — A/B region virtual lines with mathematically accurate vector cross-product trajectory detection (A↔B, A→B, B→A).
- **Live Stream** — Real-time RTSP/Webcam feeds with HLS proxying and ultra-low-latency WebSocket bounding box overlays drawn seamlessly on the frontend canvas.
- **Video Analytics** — Process offline video files with custom polygonal and line zones, class filtering, and downloadable hard-annotated MP4 results perfectly matching the livestream UI.
- **Authentication** — JWT-based auth with HttpOnly cookies, auto-refresh
- **Role-Based Access** — admin and viewer roles
- **User Management** — admin panel for user CRUD, role assignment, activation
- **Session Management** — view and revoke active sessions
- **Signup Control** — admin toggle for public registration (disabled by default)
- **Settings** — account management, password change, security controls, theme mode selection, system storage statistics, and media deletion

## Current Status & Recent Progress

Locus is under active development. Recent milestones include:

- **Advanced Analytics & UI**: Unified annotation drawing across the frontend and backend. Added support for dashed zone borders, semi-transparent zone fills, colored bounding boxes with class labels, and on-screen count overlays.
- **Directional Crossing Filters**: Enhanced line zones with intersection detection and precise crossing direction selection in both the UI and analytics engine.
- **System & Media Management**: Introduced system storage statistics display, media deletion capabilities, theme mode selection, and complete user account deletion functionalities.
- **Benchmarking Tools**: Optimizations to the benchmark script to accurately profile AI inference performance and deployment readiness on the Raspberry Pi 5.

## Quick Start

```sh
# Install frontend dependencies
pnpm install

# Setup backend environment
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# Start fullstack dev server (SvelteKit + FastAPI)
pnpm dev
```

## Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start fullstack dev server |
| `pnpm build` | Production build |
| `pnpm preview` | Preview build |
| `pnpm test` | Run tests |
| `pnpm lint` | Lint code |
| `pnpm format` | Format code |
| `pnpm benchmark` | Run build size & performance benchmark |
