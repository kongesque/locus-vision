"""LocusVision FastAPI backend application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers.auth import router as auth_router
from routers.settings import router as settings_router
from routers.video_processing import router as video_router
from routers.livestream import router as livestream_router
from routers.cameras import router as cameras_router
from routers.system import router as system_router
from routers.metrics import router as metrics_router
from routers.analytics import router as analytics_router
from routers.models import router as models_router

from services.job_queue import job_queue
from services.metrics_collector import metrics_collector
from services.downsampler import downsampler
from services.archiver import archiver

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and async workers on startup."""
    await init_db()
    
    # Start the video processing job queue worker
    job_queue.start()
    
    # Start the metrics collector
    await metrics_collector.start()
    
    # Start the data downsampler and archiver
    downsampler.start()
    archiver.start()
    
    yield
    
    # Cleanup background workers on shutdown
    job_queue.stop()
    metrics_collector.stop()
    downsampler.stop()
    archiver.stop()


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
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(video_router)
app.include_router(livestream_router)
app.include_router(cameras_router)
app.include_router(system_router)
app.include_router(metrics_router)
app.include_router(analytics_router)
app.include_router(models_router)


@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "app": settings.app_name}
