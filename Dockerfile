# ── Stage 1: Build frontend ──────────────────────────────────────
FROM node:22-slim AS frontend-build

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@latest --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY svelte.config.js vite.config.ts tsconfig.json eslint.config.js components.json ./
COPY src/ src/
COPY static/ static/
RUN pnpm build

# ── Stage 2: Production image ───────────────────────────────────
FROM python:3.12-slim

# System deps for OpenCV headless + video capture
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libv4l-0 \
    v4l-utils \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Backend source
COPY backend/ backend/

# Frontend build output + minimal package.json for node runtime
COPY --from=frontend-build /app/build build/
COPY --from=frontend-build /app/package.json ./

# Backup coco_classes.json so entrypoint can seed it into the volume
RUN cp backend/data/coco_classes.json backend/coco_classes.seed.json 2>/dev/null || true

# Entrypoint seeds data dir on first run
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000 3000
ENTRYPOINT ["docker-entrypoint.sh"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start both processes — exit container if either dies
CMD ["bash", "-c", "\
    cd /app/backend && uvicorn main:app --host 0.0.0.0 --port 8000 & \
    PID_BACKEND=$! && \
    cd /app && PORT=3000 ORIGIN=http://localhost:3000 node build & \
    PID_FRONTEND=$! && \
    trap 'kill $PID_BACKEND $PID_FRONTEND 2>/dev/null' EXIT && \
    wait -n && exit 1"]
