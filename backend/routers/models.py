import os
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Any

from services.model_manager import model_manager, get_installed_models, resolve_model
from services.onnx_detector import list_models, MODELS_DIR

router = APIRouter(prefix="/api/models", tags=["Models"])


class DownloadRequest(BaseModel):
    model_name: str  # e.g., 'yolo11s'
    precision: str   # 'fp32', 'fp16', 'int8'


@router.get("/registry")
async def get_model_registry(request: Request):
    """
    Get the enriched model registry.

    Returns detected backends and all catalog models with installation status
    and auto-resolved active format. If the catalog hasn't been loaded yet
    (e.g. during tests), falls back to the legacy flat file list.
    """
    catalog = getattr(request.app.state, "model_catalog", None)
    backends = getattr(request.app.state, "backends", None)

    # Fallback: catalog not loaded — return legacy format
    if catalog is None or backends is None:
        return {"backends": [], "models": [], "legacy": list_models()}

    models = get_installed_models(catalog, backends)
    return {"backends": backends, "models": models}


@router.get("/registry/legacy")
async def get_model_registry_legacy():
    """Legacy endpoint: flat list of .onnx filenames on disk."""
    return list_models()


@router.post("/download")
async def trigger_download(req: DownloadRequest):
    """Trigger an async download/export for a model size and precision."""
    job = await model_manager.start_download(req.model_name, req.precision)
    return job


@router.get("/download/status")
async def get_download_status() -> dict[str, dict[str, Any]]:
    """Poll the status of active and recent model downloads."""
    return model_manager.get_status()
