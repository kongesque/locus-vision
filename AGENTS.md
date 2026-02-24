# LocusVision — Agent Guide

This document provides essential context for AI coding agents working on the LocusVision codebase.

## Project Overview

**LocusVision** is an open-source, high-performance video analytics engine designed specifically for the Raspberry Pi 5 (8GB). It parses reality in real-time—turning video feeds into structured data, searchable events, and actionable insights.

Key characteristics:
- **Local-first, privacy-centric** — all processing happens on-device
- **Edge-optimized** — minimal resource usage, runs on constrained devices
- **Full-stack application** — SvelteKit frontend + FastAPI backend
- **AI-powered** — YOLO11n object detection with ByteTrack tracking

## Technology Stack

| Category | Technology |
|----------|------------|
| Frontend | SvelteKit 2, TypeScript, Svelte 5 (runes) |
| Styling | Tailwind CSS 4, CSS variables for theming |
| UI Components | shadcn-svelte (bits-ui), mode-watcher (dark/light mode) |
| Backend | FastAPI, Python 3.14 |
| Database | SQLite (async via aiosqlite), WAL mode enabled |
| AI / Vision | ONNX Runtime (YOLO11n), ByteTrack (supervision), OpenCV |
| Auth | JWT (access + refresh tokens), Argon2id password hashing |
| Build | Vite, adapter-auto |
| Testing | Vitest (frontend), pytest (backend) |
| Linting | ESLint + Prettier |
| Package Manager | pnpm |

## Project Structure

```
locusvision/
├── backend/                    # FastAPI backend & analytics engine
│   ├── routers/               # API endpoints
│   │   ├── auth.py           # Authentication (login, signup, refresh)
│   │   ├── cameras.py        # Livestream camera management
│   │   ├── settings.py       # User management, app settings
│   │   └── video_processing.py # Video upload, processing, results
│   ├── services/              # Core business logic
│   │   ├── analytics_engine.py # Zone-based counting, line crossing detection
│   │   ├── camera_worker.py   # RTSP/Webcam streaming, HLS generation
│   │   └── onnx_detector.py   # ONNX YOLO inference with ByteTrack
│   ├── tests/                 # pytest test suite
│   ├── main.py                # FastAPI application entry point
│   ├── database.py            # SQLite async DB configuration
│   ├── models.py              # Pydantic request/response models
│   ├── config.py              # pydantic-settings configuration
│   ├── auth.py                # JWT token utilities, password hashing
│   └── requirements.txt       # Python dependencies
├── src/                        # SvelteKit frontend
│   ├── lib/
│   │   ├── components/        # Svelte components
│   │   │   ├── ui/           # shadcn-svelte components (button, card, dialog, etc.)
│   │   │   ├── create/       # Zone/line drawing canvas components
│   │   │   ├── livestream/   # Live camera feed components
│   │   │   └── video-analytics/ # Video upload/list components
│   │   ├── hooks/            # Custom Svelte 5 hooks (is-mobile)
│   │   ├── stores/           # Svelte 5 runes-based stores
│   │   └── utils.ts          # cn() utility for Tailwind class merging
│   ├── routes/
│   │   ├── (app)/            # Protected app routes (with sidebar layout)
│   │   │   ├── +page.svelte  # Dashboard
│   │   │   ├── livestream/   # Camera management & live view
│   │   │   ├── video-analytics/ # Video upload & results
│   │   │   ├── create/[taskId]/ # Zone/line annotation editor
│   │   │   └── settings/     # Account & system settings
│   │   └── (auth)/           # Auth routes (no sidebar)
│   │       ├── login/
│   │       ├── signup/
│   │       ├── get-started/  # Initial setup wizard
│   │       └── logout/
│   ├── hooks.server.ts       # Server-side auth middleware (JWT validation)
│   ├── app.d.ts              # App-wide TypeScript types
│   └── routes/layout.css     # Tailwind 4 entry point + CSS variables
├── static/                     # Static assets
├── scripts/                    # Benchmarking tools
│   ├── benchmark.sh          # Full-stack performance benchmark
│   └── bench_inference.py    # AI inference benchmark
├── components.json            # shadcn-svelte configuration
├── svelte.config.js           # SvelteKit configuration
├── vite.config.ts             # Vite + Vitest configuration
├── tsconfig.json              # TypeScript configuration
├── eslint.config.js           # ESLint flat config
├── .prettierrc                # Prettier configuration
└── package.json               # Node.js dependencies
```

## Build and Development Commands

All commands run from project root:

```bash
# Development (starts both frontend and backend)
pnpm dev

# Individual development servers
pnpm dev:frontend    # Vite dev server (port 5173)
pnpm dev:backend     # FastAPI with uvicorn reload (port 8000)

# Production build
pnpm build           # Vite production build

# Testing
pnpm test            # Run Vitest tests
pnpm test:unit       # Run Vitest in watch mode

# Backend tests
cd backend && source .venv/bin/activate && pytest tests/ -v

# Code quality
pnpm lint            # ESLint + Prettier check
pnpm format          # Prettier write
pnpm check           # svelte-check TypeScript validation

# Benchmarking
pnpm benchmark       # Run edge performance benchmark
```

## Code Style Guidelines

### Frontend (TypeScript / Svelte 5)

- **Tabs for indentation** (not spaces)
- **Single quotes** for strings
- **No trailing commas**
- **Print width**: 100 characters
- **Svelte 5 runes**: Use `$state`, `$derived`, `$props` — avoid legacy `$:` reactive statements
- **TypeScript**: Strict mode enabled, explicit types on exports
- **Tailwind**: Use `cn()` utility for conditional class merging
- **Imports**: Use `$lib/` alias for project imports

Example component structure:
```svelte
<script lang="ts">
	import { cn } from '$lib/utils';
	
	interface Props {
		class?: string;
		children?: import('svelte').Snippet;
	}
	
	let { class: className = '', children }: Props = $props();
</script>

<div class={cn('base-classes', className)}>
	{@render children?.()}
</div>
```

### Backend (Python)

- **PEP 8** style with 4-space indentation
- **Type hints** on function signatures
- **Docstrings** for modules, classes, and public functions
- **Async/await** for all I/O operations (database, HTTP)
- **Pydantic models** for request/response validation
- **Router-based organization** — endpoints grouped by domain

Example endpoint pattern:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

class CameraCreate(BaseModel):
    name: str
    url: str | None = None

@router.post("", response_model=CameraResponse)
async def create_camera(data: CameraCreate):
    """Create a new camera configuration."""
    # Implementation
```

## Key Architecture Patterns

### Authentication Flow

1. **JWT-based** with short-lived access tokens (15 min) and long-lived refresh tokens (7 days)
2. **HttpOnly cookies** for token storage (XSS protection)
3. **Server-side auth guard** in `hooks.server.ts` — validates tokens on every request
4. **Auto-refresh** — when access token expires, automatically refreshes using refresh token
5. **Role-based access** — `admin` and `viewer` roles

### Database Pattern

- **SQLite** with async `aiosqlite` driver
- **WAL mode** enabled for concurrent read/write
- **Connection per request** — no connection pooling needed for SQLite
- **Row factory** returns `aiosqlite.Row` for dict-like access

### AI/Analytics Engine

- **ONNX Runtime** for inference (~15MB model vs 200MB+ PyTorch)
- **ByteTrack** for multi-object tracking
- **Zone-based analytics** — polygon zones for counting, line zones for directional crossing
- **Shared engine** — same `AnalyticsEngine` class used for both live streams and video files
- **Vector cross-product** for mathematically accurate line crossing detection

### Frontend State Management

- **Svelte 5 runes** (`$state`, `$derived`) for local component state
- **Stores** in `src/lib/stores/` for cross-component shared state
- **Server data** — use `+page.server.ts` for initial data loading
- **API calls** — direct `fetch()` to backend in `hooks.server.ts` or load functions

## Testing Strategy

### Frontend (Vitest)

- Tests located alongside source files: `*.test.ts` or `*.spec.ts`
- Configuration in `vite.config.ts`
- Run with `pnpm test`

### Backend (pytest)

- Tests in `backend/tests/`
- Fixtures for common setup (database, detector)
- Run with: `cd backend && source .venv/bin/activate && pytest tests/ -v`

### Current Test Coverage

- `backend/tests/test_onnx_detector.py` — Comprehensive tests for ONNX detector including:
  - Model loading and initialization
  - NMS (Non-Maximum Suppression)
  - Preprocessing (letterboxing, normalization)
  - Detection and tracking
  - Class filtering

## Security Considerations

### Authentication & Authorization

- **Argon2id** for password hashing (OWASP 2025 minimum: t=2, m=19 MiB, p=1)
- **Rate limiting** on login (5 attempts, 5-minute lockout)
- **JWT secrets** — configure via `LOCUS_JWT_SECRET` env var in production
- **CORS** — restricted to known origins in production

### Data Protection

- **HttpOnly cookies** prevent JavaScript access to tokens
- **SameSite=Lax** cookie attribute
- **Input validation** via Pydantic models on all endpoints
- **SQL injection prevention** — parameterized queries throughout

### Deployment Security

```bash
# Required environment variables for production
export LOCUS_JWT_SECRET="your-256-bit-secret-here"  # openssl rand -hex 32
export LOCUS_ACCESS_TOKEN_EXPIRE_MINUTES=15
export LOCUS_REFRESH_TOKEN_EXPIRE_DAYS=7
```

## Configuration

### Frontend Environment

No special env vars needed — all API calls go through SvelteKit server hooks or are proxied.

### Backend Environment

Configuration via `backend/config.py` using pydantic-settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCUS_JWT_SECRET` | (dev default) | JWT signing key |
| `LOCUS_JWT_ALGORITHM` | HS256 | JWT algorithm |
| `LOCUS_ACCESS_TOKEN_EXPIRE_MINUTES` | 15 | Access token lifetime |
| `LOCUS_REFRESH_TOKEN_EXPIRE_DAYS` | 7 | Refresh token lifetime |
| `LOCUS_DATABASE_PATH` | `backend/data/locusvision.db` | SQLite database path |
| `LOCUS_APP_NAME` | LocusVision | Application name |
| `LOCUS_CORS_ORIGINS` | localhost ports | Allowed CORS origins |
| `LOCUS_LOGIN_MAX_ATTEMPTS` | 5 | Login rate limit |
| `LOCUS_LOGIN_LOCKOUT_SECONDS` | 300 | Lockout duration |

## Common Development Tasks

### Adding a New API Endpoint

1. Add Pydantic models to `backend/models.py`
2. Add endpoint to appropriate router in `backend/routers/`
3. Register router in `backend/main.py` if new

### Adding a New Page

1. Create route directory in `src/routes/(app)/` (protected) or `src/routes/(auth)/` (public)
2. Add `+page.svelte` — component rendered for the route
3. Add `+page.server.ts` — server-side data loading (optional)
4. Add to sidebar navigation in `src/lib/components/app-sidebar.svelte` if needed

### Adding a UI Component

1. Check if shadcn-svelte has it: `npx shadcn-svelte@latest add <component>`
2. Or create custom in `src/lib/components/`
3. Use `cn()` utility for class merging
4. Follow Svelte 5 runes syntax

### Database Migrations

SQLite schema is auto-created on startup via `database.py`. For migrations:

1. Add new CREATE TABLE / ALTER TABLE to `init_db()` in `database.py`
2. Or create a one-off migration script in `backend/scripts/`

## Deployment Notes

### Target Platform

- **Primary**: Raspberry Pi 5 (8GB RAM)
- **OS**: Raspberry Pi OS (Debian-based Linux)
- **Python**: 3.14+

### Build Output

- Frontend builds to `build/` (SvelteKit static adapter)
- Backend runs as Python process with FastAPI

### Required Files for Deployment

```
backend/
  ├── .venv/               # Python virtual environment
  ├── data/
  │   ├── models/
  │   │   └── yolo11n.onnx  # AI model (download or export)
  │   └── coco_classes.json # COCO class names
  ├── main.py
  └── ...
build/                     # Frontend build output
```

### Model Setup

The ONNX model is not in the repo. Generate it:

```bash
cd backend
source .venv/bin/activate
python scripts/export_model.py yolo11n
```

Or download a pre-exported model to `backend/data/models/yolo11n.onnx`.

## Troubleshooting

### Frontend build fails

```bash
rm -rf .svelte-kit node_modules
pnpm install
pnpm build
```

### Backend database locked

SQLite WAL mode should prevent this. If issues persist:

```bash
cd backend/data
rm -f locusvision.db-shm locusvision.db-wal  # Clear WAL files
```

### ONNX model not found

```bash
cd backend
source .venv/bin/activate
python scripts/export_model.py yolo11n
```

### Port conflicts

- Frontend dev: 5173
- Backend API: 8000
- HLS stream: 8181 (configured in camera_worker.py)

## External References

- [SvelteKit Docs](https://svelte.dev/docs/kit)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [shadcn-svelte](https://shadcn-svelte.com/)
- [Tailwind CSS v4](https://tailwindcss.com/docs/v4-beta)
- [ONNX Runtime](https://onnxruntime.ai/docs/)
- [ByteTrack Paper](https://arxiv.org/abs/2110.06864)
