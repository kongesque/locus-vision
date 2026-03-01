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
- **Unified Analytics Engine** — Shared stateful object tracking (ByteTrack) and zone-based ROI counting logic.
- **Directional Line Crossing** — A/B region virtual lines with mathematically accurate vector cross-product trajectory detection (A↔B, A→B, B→A).
- **Video Analytics Job Queue** — Robust background job queue system for batch video uploads, sequential processing via a dedicated multiprocessing worker, and real-time progress tracking.
- **Optimized Background Processing** — OS-level multiprocessing architecture bypassing the Python GIL, coupled with a motion detection pipeline to pre-filter static frames and optimize CPU usage.
- **Live Stream** — Real-time backend video streaming (MJPEG) and synchronized Server-Sent Events (SSE) telemetry for dynamic object filtering and event feeds.
- **Dynamic Activity Feeds** — Actionable UI that automatically maps detected object classes (from backend analytics) into interactive visual filters.
- **Database Tracking** — Audited backend schema with async SQLite connection management.
- // TODO: Consider integrating support for secondary RTSP camera streams besides the primary webcam.
- **Authentication** — JWT-based auth with HttpOnly cookies, auto-refresh
- **Role-Based Access** — admin and viewer roles
- **User Management** — admin panel for user CRUD, role assignment, activation
- **Session Management** — view and revoke active sessions
- **Signup Control** — admin toggle for public registration (disabled by default)
- **Settings** — account management, password change, security controls, theme mode selection, system storage statistics, and media deletion

## Repository Structure

```text
locusvision/
├── backend/               # FastAPI backend & analytics engine
│   ├── routers/           # API endpoints (auth, video processing, settings, etc.)
│   ├── services/          # Core analytics, vision, and background job queue services
│   ├── main.py            # FastAPI application entry point
│   └── database.py        # SQLite async database configuration
├── src/                   # SvelteKit frontend application
│   ├── lib/               # Shared UI components and utilities
│   └── routes/            # Application pages (livestream, analytics, settings, etc.)
├── scripts/               # Benchmarking and utility scripts
└── static/                # Static assets (images, data)
```

## Current Status & Recent Progress

Locus is under active development. Recent milestones include:

- **Multiprocessing & Job Queue Architecture**: Completely refactored the background processing to use true multiprocessing (bypassing the GIL) with shared memory and queues, resulting in a highly scalable and fault-tolerant video analytics pipeline.
- **Motion Detection Optimization**: Introduced a pre-filtering motion detection pipeline to drop static frames before running expensive AI object detection, drastically reducing CPU usage.
- **Advanced Analytics & UI**: Unified annotation drawing across the frontend and backend. Added support for dashed zone borders, semi-transparent zone fills, colored bounding boxes with class labels, and on-screen count overlays.
- **Directional Crossing Filters**: Enhanced line zones with intersection detection and precise crossing direction selection in both the UI and analytics engine.
- **Live Video & Telemetry Overhaul**: Redesigned `/video-analytics` and `/livestream` pages, fixed video player CSS scaling rules, integrated SSE for telemetry dashboards, and supported dynamic filtering.
- **Backend Infrastructure Audit**: Validated schema relationships, async db execution flows, and REST endpoints for maximum code quality.
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
