# Locus Vision

Locus is an open-source, high-performance video analytics engine designed specifically for the Raspberry Pi 5 (8GB). Locus parses reality in real-time—turning video feeds into structured data, searchable events, and actionable insights.

It is built to be local-first, privacy-centric, and highly optimized for edge deployment. Lightweight, fast, minimal resource usage.

## Tech Stack

| Category | Technology |
|----------|------------|
| Frontend | SvelteKit 2, TypeScript, Svelte 5 |
| Styling | Tailwind CSS 4 |
| UI Components | shadcn-svelte, bits-ui, mode-watcher (Themes) |
| Backend | FastAPI, Python 3.11+ |
| Database | SQLite (async via aiosqlite), DuckDB for analytics |
| AI / Vision | ONNX Runtime (YOLO11n), ByteTrack (supervision), OpenCV |
| Auth | JWT (access + refresh tokens), Argon2id |
| Build | Vite |
| Testing | Vitest, pytest |
| Linting | ESLint + Prettier |

## Features

### Core Analytics
- **Edge-Optimized AI** — Lightweight ONNX Runtime inference (~15MB engine) with support for **INT8 and FP16 quantization**. Quantized models reduce footprint by up to 70% while boosting FPS on Raspberry Pi 5 hardware.
- **Isolated Per-Camera Tracking** — Stateless inference engine coupled with local `ByteTrack` instances per stream. This architectural decouple ensures multi-stream safety and prevents object ID collision across concurrent feeds.
- **Model Management & Discovery** — Dynamic backend discovery of `.onnx` models. Users can select and switch optimized models (e.g., switching from standard to INT8) directly via the Camera Settings UI.
- **Directional Line Crossing** — A/B region virtual lines with mathematically accurate vector cross-product trajectory detection (A↔B, A→B, B→A).

### Video Processing
- **Video Analytics Job Queue** — Robust background job queue system for batch video uploads, sequential processing via a dedicated multiprocessing worker, and real-time progress tracking.
- **Optimized Background Processing** — OS-level multiprocessing architecture bypassing the Python GIL, coupled with a motion detection pipeline to pre-filter static frames and optimize CPU usage.
- **Live Stream** — Real-time backend video streaming (MJPEG) and synchronized Server-Sent Events (SSE) telemetry for dynamic object filtering and event feeds.

### User Experience
- **Dynamic Activity Feeds** — Actionable UI that automatically maps detected object classes (from backend analytics) into interactive visual filters.
- **Camera Management** — Support for multiple camera sources including USB webcams and RTSP streams.
- **Annotation Tools** — Visual zone and line drawing interface for setting up analytics regions.
- **Heatmap Visualization** — Activity heatmaps for analyzed video content.

### Authentication & Security
- **JWT-based Authentication** — HttpOnly cookies, auto-refresh tokens
- **Role-Based Access Control** — Admin and viewer roles
- **User Management** — Admin panel for user CRUD, role assignment, activation
- **Session Management** — View and revoke active sessions
- **Signup Control** — Admin toggle for public registration (disabled by default)

### System Management
- **Settings** — Account management, password change, security controls, theme mode selection
- **Storage Management** — System storage statistics, media deletion
- **System Monitoring** — Real-time metrics and health checks

## System Requirements

### Target Platform (Optimized For)
- **Raspberry Pi 5** (8GB RAM recommended)
- Raspberry Pi OS (64-bit) or compatible Linux distribution
- Camera Module 3 or USB webcam

### Development Platform
- Python 3.11 or higher
- Node.js 20 or higher
- pnpm package manager
- macOS, Linux, or Windows with WSL2

## Repository Structure

```text
locusvision/
├── backend/               # FastAPI backend & analytics engine
│   ├── routers/           # API endpoints (auth, cameras, analytics, etc.)
│   ├── services/          # Core analytics, vision, and job queue services
│   ├── scripts/           # Model export and optimization scripts
│   ├── main.py            # FastAPI application entry point
│   ├── database.py        # SQLite async database configuration
│   ├── auth.py            # Authentication utilities
│   ├── config.py          # Application configuration
│   └── models.py          # Pydantic models
├── src/                   # SvelteKit frontend application
│   ├── lib/               # Shared UI components and utilities
│   │   ├── components/    # Svelte components
│   │   │   ├── ui/        # shadcn-svelte UI components
│   │   │   ├── livestream/# Livestream-specific components
│   │   │   └── video-analytics/
│   │   └── hooks/         # Custom Svelte hooks
│   └── routes/            # Application pages
│       ├── (app)/         # Authenticated app routes
│       │   ├── livestream/
│       │   ├── video-analytics/
│       │   ├── analytics/
│       │   ├── system/
│       │   └── settings/
│       └── (auth)/        # Public auth routes
│           ├── login/
│           ├── signup/
│           └── get-started/
├── scripts/               # Build and benchmark scripts
├── static/                # Static assets
└── data/                  # Runtime data (SQLite, uploads, processed media)
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- pnpm
- FFmpeg (for video processing)

### Installation

```sh
# 1. Clone the repository
git clone <repository-url>
cd locusvision

# 2. Install frontend dependencies
pnpm install

# 3. Setup backend environment
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# 4. Start the development server
pnpm dev
```

The application will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Model Optimization (Optional)

To generate an optimized INT8 model for Raspberry Pi 5 CPU:

```sh
source backend/.venv/bin/activate
python backend/scripts/export_model.py yolo11n --int8
```

The new `yolo11n_int8` model will automatically appear in the Locus interface for selection.

## Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Security (generate secure random values for production)
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/locus.db

# Storage
DATA_DIR=./data
UPLOADS_DIR=./data/uploads
PROCESSED_DIR=./data/processed

# AI/ML
MODEL_PATH=./data/models
DEFAULT_MODEL=yolo11n
```

## Available Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start fullstack dev server (frontend + backend) |
| `pnpm dev:frontend` | Start frontend dev server only |
| `pnpm dev:backend` | Start backend dev server only |
| `pnpm build` | Production build |
| `pnpm preview` | Preview production build |
| `pnpm test` | Run unit tests (Vitest) |
| `pnpm lint` | Lint code with ESLint |
| `pnpm format` | Format code with Prettier |
| `pnpm check` | Type-check Svelte files |
| `pnpm benchmark` | Run build size & performance benchmark |

## API Overview

### Main Endpoints

| Route | Description |
|-------|-------------|
| `POST /auth/login` | User login |
| `POST /auth/signup` | User registration |
| `POST /auth/refresh` | Refresh access token |
| `GET /cameras` | List all cameras |
| `POST /cameras` | Create new camera |
| `GET /livestream/{id}` | MJPEG video stream |
| `GET /livestream/{id}/telemetry` | SSE telemetry stream |
| `POST /video/upload` | Upload video for processing |
| `GET /video/jobs` | List processing jobs |
| `GET /analytics/metrics` | System metrics |
| `GET /settings` | User settings |

Full API documentation is available at `/docs` when running the backend.

## Development

### Running Tests

```sh
# Frontend tests
pnpm test

# Backend tests
cd backend
pytest
```

### Code Quality

```sh
# Lint all files
pnpm lint

# Format all files
pnpm format

# Type check
pnpm check
```

### Project Conventions

- **Frontend**: Uses Svelte 5 runes (`$state`, `$derived`, etc.)
- **Backend**: Async/await pattern throughout, FastAPI dependency injection
- **Database**: Alembic-style migrations managed via SQL scripts
- **Styling**: Tailwind CSS with CSS variables for theming

## Production Deployment

### Building for Production

```sh
# Build the frontend
pnpm build

# The backend serves static files from the build directory
# Set the environment:
export ENVIRONMENT=production
export FRONTEND_BUILD_DIR=./dist
```

### Raspberry Pi 5 Optimization Tips

1. **Enable GPU acceleration** for OpenCV where possible
2. **Use INT8 quantized models** for 2-3x performance improvement
3. **Mount storage on SSD** rather than SD card for heavy workloads
4. **Enable swap** if processing large video files
5. **Use PM2 or systemd** for process management

### Docker (Optional)

```dockerfile
# Multi-stage Dockerfile example coming soon
```

## Troubleshooting

### Common Issues

**Camera not detected**
- Check camera permissions: `sudo usermod -a -G video $USER`
- Verify with: `v4l2-ctl --list-devices`

**Model loading errors**
- Ensure models are in `./data/models/` directory
- Check ONNX Runtime compatibility with your architecture

**Performance issues on Pi**
- Reduce input resolution in camera settings
- Enable INT8 quantization
- Lower the inference FPS target

## Roadmap

- [ ] HLS streaming support
- [ ] Multi-camera synchronized recording
- [ ] Cloud backup integration
- [ ] Mobile app companion
- [ ] Advanced analytics dashboard
- [ ] Plugin system for custom detectors

## License

[MIT License](LICENSE)

---

Built with ❤️ for the edge computing community.
