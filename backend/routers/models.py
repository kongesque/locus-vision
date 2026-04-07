import os
import glob
import logging
import tempfile
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Any

from services.model_manager import model_manager, get_installed_models, resolve_model, load_model_catalog
from services.onnx_detector import list_models, MODELS_DIR
from database import get_app_setting

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".onnx", ".tflite", ".pt"}
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB

def _check_yolo_output(out_shape: list, warnings: list[str]):
    """Check if output shape looks like YOLO format and warn about non-COCO classes."""
    int_dims = [s for s in out_shape if isinstance(s, int)]
    if len(out_shape) == 3 and len(int_dims) >= 2:
        dim1, dim2 = int_dims[-2], int_dims[-1]
        # The smaller dim is the attributes dim (4 + num_classes)
        attrs_dim = min(dim1, dim2)
        if attrs_dim >= 5:
            num_classes = attrs_dim - 4
            if num_classes != 80:
                warnings.append(
                    f"Model has {num_classes} classes (COCO has 80). "
                    f"Detection will work but class labels may not match."
                )
    else:
        warnings.append(
            f"Unexpected output shape {out_shape}. "
            f"Expected [1, 4+num_classes, N] for YOLO detection models."
        )


def _validate_onnx(path: str) -> tuple[list, list, list[str]]:
    """Validate an ONNX model file. Returns (in_shape, out_shape, warnings)."""
    import onnxruntime as ort

    try:
        session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ONNX file: {e}")

    try:
        in_shape = list(session.get_inputs()[0].shape)
        out_shape = list(session.get_outputs()[0].shape)
        warnings: list[str] = []

        if len(in_shape) != 4:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported input shape {in_shape}. Expected [1, 3, H, W] for YOLO models."
            )
        if isinstance(in_shape[1], int) and in_shape[1] != 3:
            raise HTTPException(
                status_code=400,
                detail=f"Expected 3 input channels, got {in_shape[1]}. Not an RGB image model."
            )

        _check_yolo_output(out_shape, warnings)
        logger.info("Validated ONNX: input=%s, output=%s", in_shape, out_shape)
        return in_shape, out_shape, warnings
    finally:
        del session


def _validate_tflite(path: str) -> tuple[list, list, list[str]]:
    """Validate a TFLite model file. Returns (in_shape, out_shape, warnings)."""
    from services.onnx_detector import _get_tflite_interpreter_class

    Interpreter = _get_tflite_interpreter_class()
    if Interpreter is None:
        raise HTTPException(
            status_code=400,
            detail="No TFLite runtime found. Install one of: "
                   "pip install tflite-runtime, pip install ai-edge-litert, "
                   "or pip install tensorflow"
        )

    try:
        interpreter = Interpreter(model_path=path)
        interpreter.allocate_tensors()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid TFLite file: {e}")

    try:
        in_details = interpreter.get_input_details()[0]
        out_details = interpreter.get_output_details()[0]
        in_shape = list(in_details["shape"].tolist())
        out_shape = list(out_details["shape"].tolist())
        warnings: list[str] = []

        # TFLite YOLO is typically NHWC [1, H, W, 3]
        if len(in_shape) != 4:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported input shape {in_shape}. Expected [1, H, W, 3] for YOLO models."
            )
        channels = in_shape[3] if in_shape[3] in (1, 3) else in_shape[1]
        if channels != 3:
            raise HTTPException(
                status_code=400,
                detail=f"Expected 3 input channels, got {channels}. Not an RGB image model."
            )

        _check_yolo_output(out_shape, warnings)
        logger.info("Validated TFLite: input=%s, output=%s", in_shape, out_shape)
        return in_shape, out_shape, warnings
    finally:
        del interpreter


def _convert_pt_to_onnx(pt_path: str, target_dir: str) -> str:
    """
    Convert a PyTorch .pt model to ONNX using ultralytics export.
    Returns the path to the exported .onnx file.
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        raise HTTPException(
            status_code=400,
            detail="Ultralytics is not installed. Cannot convert .pt files. "
                   "Upload an ONNX file instead, or install with: pip install ultralytics"
        )

    try:
        model = YOLO(pt_path)
        onnx_path = model.export(format="onnx", imgsz=640)
        logger.info("Converted .pt → .onnx: %s", onnx_path)
        return str(onnx_path)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to convert .pt to ONNX: {e}"
        )


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
        return {"backends": [], "models": [], "default_model": "yolo11n", "legacy": list_models()}

    models = get_installed_models(catalog, backends)
    default_model = await get_app_setting("default_model", "yolo11n")
    return {"backends": backends, "models": models, "default_model": default_model}


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


@router.post("/upload")
async def upload_model(file: UploadFile = File(...)):
    """
    Upload a custom ONNX model file.

    Validates the file extension and ONNX header, then saves to data/models/.
    The model becomes immediately available for selection.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Sanitize filename: keep only alphanumeric, hyphens, underscores
    base_name = os.path.splitext(os.path.basename(file.filename))[0]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    target_filename = f"{safe_name}{ext}"
    target_path = os.path.join(MODELS_DIR, target_filename)
    tmp_path = target_path + ".tmp"

    os.makedirs(MODELS_DIR, exist_ok=True)

    try:
        # Stream to temp file with size check
        total_size = 0
        with open(tmp_path, "wb") as f:
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB"
                    )
                f.write(chunk)

        # Handle .pt → auto-convert to ONNX
        converted_from_pt = False
        if ext == ".pt":
            # Ultralytics exports next to the source file, so use a temp dir
            # with the proper .pt extension for it to work correctly
            with tempfile.TemporaryDirectory() as tmpdir:
                pt_path = os.path.join(tmpdir, f"{safe_name}.pt")
                os.replace(tmp_path, pt_path)
                onnx_path = _convert_pt_to_onnx(pt_path, tmpdir)
                # Move the resulting ONNX to our tmp_path location
                tmp_path = target_path + ".tmp"
                os.replace(onnx_path, tmp_path)

            ext = ".onnx"
            target_filename = f"{safe_name}.onnx"
            target_path = os.path.join(MODELS_DIR, target_filename)
            total_size = os.path.getsize(tmp_path)
            converted_from_pt = True

        # Validate model structure based on format
        warnings: list[str] = []
        in_shape: list = []
        out_shape: list = []

        if ext == ".onnx":
            in_shape, out_shape, warnings = _validate_onnx(tmp_path)
        elif ext == ".tflite":
            in_shape, out_shape, warnings = _validate_tflite(tmp_path)

        # Atomic rename (skip if conversion already placed it correctly)
        if tmp_path != target_path:
            os.replace(tmp_path, target_path)
        size_mb = round(total_size / (1024 * 1024), 1)
        logger.info("Uploaded model: %s (%.1f MB)", target_filename, size_mb)

        result = {
            "filename": target_filename,
            "model_name": safe_name,
            "size_mb": size_mb,
            "input_shape": [s if isinstance(s, int) else None for s in in_shape],
            "output_shape": [s if isinstance(s, int) else None for s in out_shape],
        }
        if converted_from_pt:
            warnings.append("Converted from PyTorch (.pt) to ONNX format.")
        if warnings:
            result["warnings"] = warnings
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload failed: %s", e)
        raise HTTPException(status_code=500, detail="Upload failed")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


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
    for pattern in [f"{model_name}.onnx", f"{model_name}_*.onnx", f"{model_name}.tflite", f"{model_name}_*.tflite", f"{model_name}*.hef"]:
        for path in glob.glob(os.path.join(MODELS_DIR, pattern)):
            basename = os.path.basename(path)
            if basename not in deleted_files:
                os.remove(path)
                deleted_files.append(basename)

    if not deleted_files:
        raise HTTPException(status_code=404, detail=f"No files found for model '{model_name}'")

    return {"deleted": deleted_files, "model_name": model_name}
