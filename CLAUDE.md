# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
- `pnpm dev` - Start fullstack dev server (frontend + backend concurrently)
- `pnpm dev:frontend` - Start frontend only (Vite dev server on port 5173)
- `pnpm dev:backend` - Start backend only (FastAPI/uvicorn on port 8000 with reload)
- `pnpm build` - Production build (outputs to `dist/`)
- `pnpm preview` - Preview production build

**Docker alternative:** `docker compose up --build` — runs app on port 3000, API on port 8000.

**Backend venv:** `source backend/.venv/bin/activate` — required before all `cd backend && ...` commands.

**Python version:** 3.11 or 3.12 only (TFLite Runtime and ML packages have strict version requirements).

### Testing
- `pnpm test` - Run all frontend unit tests (Vitest with --run)
- `pnpm test:unit` - Run Vitest in watch mode
- `pnpm test -- src/path/to/file.test.ts` - Run a single frontend test file
- `cd backend && pytest` - Run all backend tests
- `cd backend && pytest tests/test_specific.py` - Run a single backend test file
- `cd backend && pytest tests/test_specific.py::test_function -v` - Run a single backend test

### Code Quality
- `pnpm lint` - ESLint + Prettier check
- `pnpm format` - Format all files with Prettier
- `pnpm check` - Type-check Svelte files with svelte-check
- `pnpm check:watch` - Type-check in watch mode

### Model & Benchmarking
- `python backend/scripts/export_model.py yolo11n --int8` - Export quantized model to `data/models/` (requires `ultralytics`)
- `python backend/scripts/benchmark_inference.py` - Benchmark ONNX inference on current hardware

## Code Style

Prettier enforces: **tabs** for indentation, **single quotes**, **no trailing commas**, **100 char printWidth**. Svelte files use the `svelte` parser. Tailwind class sorting is automatic via `prettier-plugin-tailwindcss`.

ESLint uses flat config format (ESLint 9). `no-undef` is off (TypeScript handles it).

## High-Level Architecture

LocusVision is a self-hosted video analytics platform targeting **Raspberry Pi 5 (8GB)**. All processing is local — no cloud dependencies.

### Frontend-Backend Communication

There is **no Vite proxy** — the frontend calls the backend directly. Both servers run independently on different ports (5173 for frontend, 8000 for backend). CORS is configured in `backend/config.py` for these origins.

`src/lib/api.ts` exports `API_URL` which resolves dynamically to `${window.location.hostname}:8000` on the client (so Docker deployments on non-localhost hosts work) and falls back to `http://127.0.0.1:8000` on the server. Always import `API_URL` from `$lib/api` rather than hardcoding the backend URL.

API calls from the frontend use native `fetch` (no axios or wrapper library). Server-side calls in `hooks.server.ts` and `+page.ts` load functions hit the backend directly. Client-side calls in components use the same pattern.

Interactive API docs are at `http://localhost:8000/api/docs`.

### Frontend (SvelteKit 5 + TypeScript)

**Authentication Flow**
- Authentication is handled in `src/hooks.server.ts` via JWT access/refresh tokens stored in HttpOnly cookies
- All routes except `/login`, `/signup`, `/get-started`, `/logout` require authentication
- The hook validates tokens against the FastAPI backend (`/api/auth/me`) and auto-refreshes expired access tokens
- User data is attached to `event.locals.user` and available in all route loaders
- User type defined in `src/app.d.ts`: `{ id: number; email: string; name: string; role: 'admin' | 'viewer' } | null`
- First-time setup: navigate to `/get-started` to create the initial admin account

**Route Structure**
- `src/routes/(app)/` - Authenticated application routes (livestream, video-analytics, analytics, settings, system)
  - `livestream/` - Camera grid view
  - `livestream/[taskId]/` - Single-camera fullscreen view
  - `video-analytics/` - Video job list and upload
  - `video-analytics/[taskId]/` - Video job detail and results
  - `create/[taskId]/` - Zone/line drawing canvas for configuring analytics on a video or stream before processing. Uses `$lib/stores/video.svelte.ts` (global store) to carry the video URL/type across the navigation from the upload step.
  - `analytics/` - DuckDB-backed event analytics dashboard
  - `settings/` - User profile, appearance, models, admin
  - `system/` - System health and storage
- `src/routes/(auth)/` - Public authentication routes (login, signup, get-started)
- `src/routes/+layout.svelte` - Root layout with global styles

**Component Architecture**
- UI components use shadcn-svelte (installed in `src/lib/components/ui/`) with bits-ui primitives
- Add new shadcn components with: `npx shadcn-svelte@latest add <component>`
- Custom components are organized by feature: `livestream/`, `video-analytics/`, `create/`
- Svelte 5 runes (`$state`, `$derived`, `$props`) are used throughout — avoid legacy `$:` reactive statements
- Styling uses Tailwind CSS 4 with CSS variables for theming (defined in `src/routes/layout.css`)
- Component aliases: `$lib/components`, `$lib/components/ui`, `$lib/hooks`

**State Management**
- Svelte 5 runes-based stores in `src/lib/stores/` (e.g., `video.svelte.ts`) using factory functions with `$state` runes
- Prefer local component state with props over global stores when possible

### Backend (FastAPI + Python)

**Application Structure**
- `main.py` - FastAPI app factory with lifespan management (starts/stops background workers)
- `config.py` - Pydantic-settings configuration (env vars prefixed with `LOCUS_`, reads `.env` from `backend/`)
- `database.py` - Async SQLite (aiosqlite) database initialization and connection management
- `auth.py` - JWT token utilities and Argon2id password hashing
- `models.py` - Pydantic request/response models

**Router Organization**
- `routers/auth.py` - Login, signup, token refresh, user management
- `routers/cameras.py` - Camera CRUD and configuration
- `routers/livestream.py` - MJPEG streaming and SSE telemetry endpoints
- `routers/video_processing.py` - Video upload and job queue management
- `routers/analytics.py` - Analytics queries and event retrieval
- `routers/metrics.py` - System metrics collection endpoint
- `routers/system.py` - Storage management and system health
- `routers/settings.py` - User settings and admin configuration
- `routers/models.py` - ML model discovery and management

All routers use `APIRouter(prefix="/api/...", tags=[...])` and are mounted in `main.py`.

**Background Services**
All services are singletons started/stopped in `main.py` lifespan:

- `services/job_queue.py` - SQLite-backed video processing queue with single worker thread. Processes videos sequentially using `AnalyticsEngine`, updates progress in DB. Crash-resilient (resets stale tasks on startup).
- `services/analytics_engine.py` - Stateful per-session engine wrapping ONNX detector with ByteTracker. Handles zone-based counting, line crossing detection (vector cross-product), and event generation. Used by both live streams and video processing.
- `services/livestream_manager.py` - Manages per-camera inference loops (multiprocessing), MJPEG streaming, and SSE telemetry. Each camera runs in isolated process with its own `AnalyticsEngine` instance.
- `services/onnx_detector.py` - ONNX Runtime YOLO inference with NMS. Supports FP16/INT8 quantized models and TFLite. Auto-detects hardware execution provider (Hailo → CUDA → CoreML → CPU). Dynamic model loading from `data/models/`.
- `services/metrics_collector.py` - Background metrics aggregation (CPU, memory, FPS, detection counts) written to SQLite for time-series queries.
- `services/downsampler.py` - Archives old high-frequency metrics data.
- `services/archiver.py` - Cleans up old processed videos and orphaned files.
- `services/duckdb_client.py` - DuckDB connection manager for analytics queries (Parquet output).
- `services/model_manager.py` - Discovers and validates ONNX/TFLite models in `data/models/` directory. Reads `backend/model_catalog.json` for the downloadable model registry (YOLO11n/s/m/l/x and YOLOv8 variants with Hailo `.hef` formats).
- `services/discovery_service.py` - Discovers local cameras (V4L2 on Linux, OpenCV index probing with macOS `system_profiler` names) and ONVIF network cameras via WS-Discovery multicast.
- `services/video_capture.py` - `FFmpegCapture` (Frigate-style ffmpeg subprocess for RTSP with a background reader thread keeping only the latest frame) vs. `cv2.VideoCapture` for local devices and files. RTSP sources always use FFmpegCapture; local/file sources use OpenCV.

**Database Architecture**
- SQLite (aiosqlite) for primary data: users, cameras, video tasks, events, sessions, metrics
- DuckDB for analytics: queries against event data with Parquet export capability
- Database file location: `backend/data/locusvision.db`
- SQLite uses WAL mode and foreign keys (`PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`)
- Migrations are inline in `database.py` `init_db()` — new columns go in both the CREATE TABLE statement and the migrations dict for existing databases (no Alembic)

**AI/Vision Pipeline**
1. **Detection**: ONNX Runtime with YOLO models (supports FP16/INT8 quantization) and TFLite; hardware auto-selected (Hailo-8L → CUDA → CoreML → CPU ARM)
2. **Tracking**: ByteTrack (via supervision library) per-camera instances prevent ID collision
3. **Analytics**: Zone-based counting with polygon containment, directional line crossing (A→B, B→A, both)
4. **Events**: Zone entries/exits, line crossings, track lifecycle events written to DuckDB for analytics
5. **Model Export**: `python backend/scripts/export_model.py yolo11n --int8` to generate quantized models into `data/models/`

**Key Conventions**
- All database operations are async (aiosqlite)
- FastAPI dependency injection for common patterns (get_current_user, get_db)
- Background workers use threading (job queue) or multiprocessing (livestream inference)
- Environment variables use `LOCUS_` prefix (see `config.py`)
- Argon2id parameters are tuned for Raspberry Pi 5 constrained memory
