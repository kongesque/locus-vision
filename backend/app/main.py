"""
Locus FastAPI Backend - Main Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api.routes import jobs, camera, system, ws
from app.services.db import init_db

# Initialize database
init_db()

# Create FastAPI app
app = FastAPI(
    title="Locus API",
    description="AI Object Counter & Analytics API",
    version="0.2.0"
)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
os.makedirs("uploads/videos", exist_ok=True)
os.makedirs("uploads/frames", exist_ok=True)
os.makedirs("uploads/outputs", exist_ok=True)
os.makedirs("weights", exist_ok=True)
os.makedirs("instance", exist_ok=True)

# Mount static files for media serving
app.mount("/media", StaticFiles(directory="uploads"), name="media")

# Include routers
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(camera.router, prefix="/api", tags=["camera"])
app.include_router(system.router, prefix="/api", tags=["system"])
app.include_router(ws.router, tags=["websocket"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
