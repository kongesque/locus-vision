"""
Model management: catalog, hardware detection, model resolution, and download orchestration.

Phase 0 of the Ollama-style model selection redesign.
"""

import asyncio
import json
import logging
import os
import platform
import time
from typing import Any

from services.onnx_detector import MODELS_DIR

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "model_catalog.json")


# ── 0A: Model Catalog ───────────────────────────────────────────

def load_model_catalog() -> dict:
    """
    Load the static model catalog from disk.
    Returns the full catalog dict with 'models' and 'format_priority' keys.
    """
    if not os.path.exists(CATALOG_PATH):
        logger.warning("Model catalog not found at %s — returning empty catalog", CATALOG_PATH)
        return {"models": {}, "format_priority": []}

    with open(CATALOG_PATH, "r") as f:
        catalog = json.load(f)

    logger.info(
        "Loaded model catalog: %d models, priority: %s",
        len(catalog.get("models", {})),
        catalog.get("format_priority", []),
    )
    return catalog


# ── 0B: Hardware Detection ───────────────────────────────────────

def detect_backends() -> list[str]:
    """
    Detect available inference backends. Runs once on startup.

    Returns a list of format keys in priority order (best first).
    These keys correspond to the format keys in model_catalog.json.
    """
    backends: list[str] = []

    # Hailo-8L (Raspberry Pi AI Kit)
    try:
        import hailo_platform  # noqa: F401
        from hailo_platform import VDevice
        vd = VDevice()
        vd.release()
        backends.append("hailo")
        logger.info("Hardware detected: Hailo-8L")
    except Exception:
        pass

    # GPU (CUDA via ONNX Runtime)
    try:
        import onnxruntime as ort
        if "CUDAExecutionProvider" in ort.get_available_providers():
            backends.append("onnx_cuda")
            logger.info("Hardware detected: CUDA GPU")
    except Exception:
        pass

    # CoreML (macOS Apple Silicon)
    try:
        import onnxruntime as ort
        if "CoreMLExecutionProvider" in ort.get_available_providers():
            backends.append("onnx_coreml")
            logger.info("Hardware detected: CoreML (macOS)")
    except Exception:
        pass

    # CPU ONNX is always available — add all precisions as fallback
    backends.append("onnx_int8")
    backends.append("onnx_fp16")
    backends.append("onnx_fp32")

    arch = platform.machine()
    logger.info("Detected backends: %s (arch: %s)", backends, arch)
    return backends


# ── 0C: Model Resolution ────────────────────────────────────────

def fmt_available(fmt: str, backends: list[str]) -> bool:
    """
    Check whether a format key can actually run on the detected hardware.

    - 'hailo'     → requires 'hailo' in backends
    - 'onnx_int8' → requires any onnx backend (always true since CPU is always there)
    - 'onnx_fp16' → same
    - 'onnx_fp32' → same
    """
    if fmt == "hailo":
        return "hailo" in backends
    if fmt.startswith("onnx_"):
        # Any ONNX format can run as long as we have an ONNX backend (CPU always present)
        return True
    return False


def resolve_model(model_name: str, catalog: dict, backends: list[str]) -> dict:
    """
    Given a model name and available backends, return the best format to use.

    Walks the catalog's format_priority list and returns the first format
    that is both supported by the hardware AND has its file installed on disk.

    Returns:
        {
            "file": "yolov8s_h8l.hef",
            "backend": "hailo",
            "model_name": "yolov8s",
            "path": "/abs/path/to/file",
            "size_mb": 35.0,
            "fps_estimate": 59       # optional, may be None
        }

    Raises:
        ValueError: if model_name is not in the catalog
        FileNotFoundError: if no usable format file is installed
    """
    model = catalog.get("models", {}).get(model_name)
    if not model:
        raise ValueError(f"Unknown model: {model_name}")

    priority = catalog.get("format_priority", [])

    for fmt in priority:
        if fmt not in model.get("formats", {}):
            continue
        if not fmt_available(fmt, backends):
            continue

        format_info = model["formats"][fmt]
        file_path = os.path.join(MODELS_DIR, format_info["file"])

        if os.path.exists(file_path):
            return {
                "file": format_info["file"],
                "backend": fmt,
                "model_name": model_name,
                "path": file_path,
                "size_mb": format_info.get("size_mb"),
                "fps_estimate": format_info.get("fps_estimate"),
            }

    raise FileNotFoundError(
        f"No installed format for model '{model_name}'. "
        f"Available formats in catalog: {list(model.get('formats', {}).keys())}. "
        f"Detected backends: {backends}. "
        f"Download models from Settings > Models."
    )


def get_installed_models(catalog: dict, backends: list[str]) -> list[dict]:
    """
    Return a list of all catalog models with their installation and resolution status.

    Each entry includes:
      - name, label, family, purpose, classes (from catalog)
      - installed: bool — whether at least one usable format exists on disk
      - active_format: str | None — the format that would be used
      - size_mb: float | None — size of the active format file
      - fps_estimate: float | None — estimated FPS (if known)
      - available_formats: list[str] — formats compatible with detected hardware
    """
    results = []

    for name, model in catalog.get("models", {}).items():
        entry: dict[str, Any] = {
            "name": name,
            "label": model.get("label", name),
            "family": model.get("family"),
            "purpose": model.get("purpose"),
            "classes": model.get("classes"),
            "installed": False,
            "active_format": None,
            "size_mb": None,
            "fps_estimate": None,
            "available_formats": [],
        }

        # Determine which formats are compatible with this hardware
        priority = catalog.get("format_priority", [])
        for fmt in priority:
            if fmt in model.get("formats", {}) and fmt_available(fmt, backends):
                entry["available_formats"].append(fmt)

        # Try to resolve the best installed format
        try:
            resolved = resolve_model(name, catalog, backends)
            entry["installed"] = True
            entry["active_format"] = resolved["backend"]
            entry["size_mb"] = resolved.get("size_mb")
            entry["fps_estimate"] = resolved.get("fps_estimate")
        except (FileNotFoundError, ValueError):
            # Not installed — populate size from the best available format
            if entry["available_formats"]:
                best_fmt = entry["available_formats"][0]
                fmt_info = model["formats"][best_fmt]
                entry["size_mb"] = fmt_info.get("size_mb")
                entry["fps_estimate"] = fmt_info.get("fps_estimate")

        results.append(entry)

    return results


# ── Download Manager (existing, preserved) ───────────────────────

class ModelManager:
    """Manages downloading and exporting YOLO models."""
    def __init__(self):
        self.download_jobs: dict[str, dict[str, Any]] = {}

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Return the current status of all downloads."""
        return self.download_jobs

    async def start_download(self, base_model: str, precision: str = "fp32"):
        """
        Starts a background download/export job.
        precision: 'fp32', 'fp16', or 'int8'
        """
        job_id = f"{base_model}_{precision}"

        if job_id in self.download_jobs and self.download_jobs[job_id]["status"] in ["downloading", "exporting"]:
            return self.download_jobs[job_id]

        self.download_jobs[job_id] = {
            "status": "starting",
            "model": base_model,
            "precision": precision,
            "error": None,
            "started_at": time.time(),
            "updated_at": time.time()
        }

        # Run export in background so we don't block the API
        asyncio.create_task(self._run_export(job_id, base_model, precision))

        return self.download_jobs[job_id]

    async def _run_export(self, job_id: str, base_model: str, precision: str):
        try:
            self.download_jobs[job_id]["status"] = "downloading"
            self.download_jobs[job_id]["updated_at"] = time.time()

            # The export script handles both download (.pt) and export (.onnx)
            # Find python executable for the current venv
            import sys
            python_exe = sys.executable

            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "export_model.py")

            cmd = [python_exe, script_path, base_model]
            if precision == "fp16":
                cmd.append("--half")
            elif precision == "int8":
                cmd.append("--int8")

            # We assume downloading if it takes a while before exporting
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Monitor output to update state to 'exporting'
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded_line = line.decode('utf-8').strip()
                print(f"[ModelManager] {decoded_line}")

                if "Exporting" in decoded_line:
                    self.download_jobs[job_id]["status"] = "exporting"
                    self.download_jobs[job_id]["updated_at"] = time.time()

            await process.wait()

            if process.returncode == 0:
                self.download_jobs[job_id]["status"] = "done"
            else:
                stderr = (await process.stderr.read()).decode('utf-8')
                print(f"[ModelManager] Error: {stderr}")
                self.download_jobs[job_id]["status"] = "error"
                self.download_jobs[job_id]["error"] = stderr

        except Exception as e:
            print(f"[ModelManager] Exception: {e}")
            self.download_jobs[job_id]["status"] = "error"
            self.download_jobs[job_id]["error"] = str(e)
        finally:
            self.download_jobs[job_id]["updated_at"] = time.time()

model_manager = ModelManager()
