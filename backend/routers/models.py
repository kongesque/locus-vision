import os
import glob
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Any

from services.model_manager import model_manager, get_installed_models, resolve_model, load_model_catalog
from services.onnx_detector import list_models, MODELS_DIR

router = APIRouter(prefix="/api/models", tags=["Models"])


class DownloadRequest(BaseModel):
    model_name: str        # e.g., 'yolo11s'
    precision: str | None = None  # Optional — auto-resolved from hardware if omitted


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
async def trigger_download(req: DownloadRequest, request: Request):
    """
    Trigger an async download/export for a model.

    If precision is omitted, auto-selects the best precision based on
    detected hardware backends (prefers int8 > fp16 > fp32).
    """
    precision = req.precision
    if precision is None:
        # Auto-resolve: pick best precision from detected backends
        backends = getattr(request.app.state, "backends", [])
        if "onnx_int8" in backends:
            precision = "int8"
        elif "onnx_fp16" in backends:
            precision = "fp16"
        else:
            precision = "fp32"

    job = await model_manager.start_download(req.model_name, precision)
    return job


@router.get("/download/status")
async def get_download_status() -> dict[str, dict[str, Any]]:
    """Poll the status of active and recent model downloads."""
    return model_manager.get_status()


@router.delete("/{model_name}")
async def delete_model(model_name: str, request: Request):
    """
    Remove all format files for a model from data/models/.

    Looks up the model in the catalog to find its known filenames,
    then deletes any that exist on disk. Also removes any files
    matching the model name pattern as a fallback.
    """
    catalog = getattr(request.app.state, "model_catalog", None)
    deleted_files: list[str] = []

    # Strategy 1: Delete known catalog files
    if catalog:
        model_entry = catalog.get("models", {}).get(model_name, {})
        for fmt_info in model_entry.get("formats", {}).values():
            file_path = os.path.join(MODELS_DIR, fmt_info["file"])
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_files.append(fmt_info["file"])

    # Strategy 2: Fallback — delete any files matching the model name pattern
    # Catches legacy files like yolo11n_int8.onnx, yolo11n_half.onnx, yolo11n.onnx
    for pattern in [f"{model_name}.onnx", f"{model_name}_*.onnx", f"{model_name}*.hef"]:
        for path in glob.glob(os.path.join(MODELS_DIR, pattern)):
            basename = os.path.basename(path)
            if basename not in deleted_files:
                os.remove(path)
                deleted_files.append(basename)

    if not deleted_files:
        raise HTTPException(status_code=404, detail=f"No files found for model '{model_name}'")

    return {"deleted": deleted_files, "model_name": model_name}
