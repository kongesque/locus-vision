# Locus Vision

Locus is an open-source, high-performance video analytics engine designed specifically for the Raspberry Pi 5 (8GB). Locus parses reality in real-time—turning video feeds into structured data, searchable events, and actionable insights.

It is built to be local-first, privacy-centric, and highly optimized for edge deployment. Lightweight, fast, minimal resource usage

## Tech Stack

| Category | Technology |
|----------|------------|
| Frontend | SvelteKit 2, TypeScript |
| Styling | Tailwind CSS 4 |
| UI Components | shadcn-svelte |
| Backend | FastAPI, Python |
| Database | SQLite (async via aiosqlite) |
| Auth | JWT (access + refresh tokens), Argon2id |
| Build | Vite 7 |
| Testing | Vitest |
| Linting | ESLint + Prettier |

## Features

- **Live Stream** — real-time video feed monitoring
- **Video Analytics** — structured data from video feeds
- **Authentication** — JWT-based auth with HttpOnly cookies, auto-refresh
- **Role-Based Access** — admin and viewer roles
- **User Management** — admin panel for user CRUD, role assignment, activation
- **Session Management** — view and revoke active sessions
- **Signup Control** — admin toggle for public registration (disabled by default)
- **Settings** — account management, password change, security controls

## Quick Start

```sh
# Frontend
pnpm install
pnpm dev

# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start dev server |
| `pnpm build` | Production build |
| `pnpm preview` | Preview build |
| `pnpm test` | Run tests |
| `pnpm lint` | Lint code |
| `pnpm format` | Format code |
| `pnpm benchmark` | Run build size & performance benchmark |
