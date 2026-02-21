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
| AI / Vision | YOLO (Object Detection, Tracking & Counting) |
| Auth | JWT (access + refresh tokens), Argon2id |
| Build | Vite 7 |
| Testing | Vitest |
| Linting | ESLint + Prettier |

## Features

- **Live Stream** — real-time RTSP camera feeds with YOLO object detection and HLS streaming
- **Video Analytics** — process videos for object detection, tracking, and counting with customizable zones and class filtering
- **Theme Switching** — built-in support for auto, dark, and light modes
- **Authentication** — JWT-based auth with HttpOnly cookies, auto-refresh
- **Role-Based Access** — admin and viewer roles
- **User Management** — admin panel for user CRUD, role assignment, activation
- **Session Management** — view and revoke active sessions
- **Signup Control** — admin toggle for public registration (disabled by default)
- **Settings** — account management, password change, security controls

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
