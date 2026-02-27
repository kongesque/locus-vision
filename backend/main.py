"""LocusVision FastAPI backend application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers.auth import router as auth_router
from routers.settings import router as settings_router
from routers.video_processing import router as video_router


import asyncio
from services.job_queue import job_queue

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and async workers on startup."""
    await init_db()
    
    # Start the video processing job queue worker
    job_queue.start()
    
    yield
    
    # Cleanup background workers on shutdown
    job_queue.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS — only needed if accessing FastAPI directly (SvelteKit proxies bypass this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(video_router)


@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "app": settings.app_name}
