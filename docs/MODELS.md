# Model System

How LocusVision discovers, resolves, downloads, and runs YOLO models.

## Architecture

```
Startup:
  detect_backends()  → ["onnx_int8", "onnx_fp16", "onnx_fp32"]  (or ["hailo", ...] on Pi)
  load_model_catalog() → 12 models from model_catalog.json
  Both stored on app.state for the lifetime of the process

Create Page:
  GET /api/models/registry → installed models + system default
  Model: [YOLO11 Nano ▾]  ← single dropdown, no precision picker

Settings > Models:
  Browse catalog, download/remove models
  See detected hardware
  Admin sets system-wide default model

Inference:
  get_detector("yolo11n") → resolve_model() → best installed format → OnnxDetector
```

## Key Files

| File | Role |
|------|------|
| `backend/model_catalog.json` | Static registry of all known models, formats, sizes, and download URLs |
| `backend/services/model_manager.py` | Catalog loading, hardware detection, model resolution, HTTP download manager |
| `backend/services/onnx_detector.py` | `get_detector()` — loads models with legacy fallback then catalog resolution |
| `backend/routers/models.py` | API: `/api/models/registry`, `/api/models/download`, `DELETE /api/models/{name}` |
| `backend/scripts/export_model.py` | Dev-only CLI: converts `.pt` to `.onnx` (requires `ultralytics`, not a runtime dep) |
| `src/lib/components/settings/model-library.svelte` | Settings UI: browse, download, remove models |
| `src/lib/components/create/tools-panel.svelte` | Create page: single model dropdown |

## Model Catalog (`model_catalog.json`)

Static JSON shipped with the app. Each model has:

- **name** — flat identifier (e.g., `yolo11n`, `yolov8s`). No precision/backend encoding.
- **formats** — map of format keys to `{ file, size_mb, url? }`. Format keys: `onnx_fp32`, `onnx_fp16`, `onnx_int8`, `hailo`.
- **format_priority** — global preference order: `["hailo", "onnx_int8", "onnx_fp16", "onnx_fp32"]`

To add a new model: add an entry to this JSON and upload the file to the GitHub release.

## Hardware Detection

`detect_backends()` runs once at startup and probes in order:

1. **Hailo-8L** — imports `hailo_platform`, opens a VDevice
2. **CUDA** — checks `CUDAExecutionProvider` in onnxruntime
3. **CoreML** — checks `CoreMLExecutionProvider` in onnxruntime
4. **CPU** — always appended (`onnx_int8`, `onnx_fp16`, `onnx_fp32`)

Result stored in `app.state.backends`.

## Model Resolution

`resolve_model(name, catalog, backends)` walks `format_priority` and returns the first format that:

1. Exists in the model's format list
2. Is compatible with detected hardware (`fmt_available()`)
3. Has its file on disk (`backend/data/models/`)

This is the core behavior — user picks a name, system picks the best way to run it.

## Downloads

Pre-built ONNX files are hosted on GitHub Releases (`models-v1` tag). The download flow:

1. Frontend sends `POST /api/models/download` with `{ model_name }` (precision auto-resolved from hardware)
2. `ModelManager._resolve_url()` looks up the `url` field in the catalog for the target format
3. `_run_download()` streams the file via `httpx` to a `.tmp` file, then atomic `os.replace`
4. Frontend polls `GET /api/models/download/status` for progress

Hailo `.hef` models have no download URL — they ship on the Pi at `/usr/share/hailo-models/`.

### Adding models to the release

On a dev machine with `ultralytics` installed:

```bash
source backend/.venv/bin/activate
pip install ultralytics

# Export
python backend/scripts/export_model.py <model_name>
python backend/scripts/export_model.py <model_name> --half
python backend/scripts/export_model.py <model_name> --int8

# Upload to existing release
gh release upload models-v1 backend/data/models/<file>.onnx

# Uninstall (not a runtime dependency)
pip uninstall ultralytics torch torchvision -y
```

Then add the `url` field to the new format entry in `model_catalog.json`.

## Detector Loading (`get_detector`)

Resolution order in `get_detector()`:

1. **Legacy exact match** — checks `data/models/{model_name}.onnx` directly (handles old DB rows like `yolo11n_int8`)
2. **Catalog resolution** — calls `resolve_model()` to find the best format
3. **Error** — raises `FileNotFoundError` with instructions to download from Settings

Detector instances are cached per `(model_name, conf_threshold)`.

## Default Model

- Database: `app_settings` table, key `default_model` (initialized to `yolo11n`)
- Admin UI: Settings > Admin tab > Default Model dropdown
- Create page: fetches default from `GET /api/models/registry` response (`default_model` field)
- Camera creation: if `model_name` is `None`, falls back to system default via `get_app_setting()`

## Current Models (models-v1 release)

| Model | FP32 | FP16 | INT8 | Hailo |
|-------|------|------|------|-------|
| yolo11n | 10 MB | 5 MB | 3 MB | - |
| yolo11s | 36 MB | 18 MB | 10 MB | - |
| yolo11m | 77 MB | 39 MB | 20 MB | - |
| yolo11l | 97 MB | 49 MB | 25 MB | - |
| yolo11x | 218 MB | 109 MB | 56 MB | - |
| yolov8n | 12 MB | - | 3 MB | 7 MB |
| yolov8s | 43 MB | - | 11 MB | 35 MB |
| yolov8s-pose | - | - | - | 23 MB |
| yolov6n | - | - | - | 14 MB |
| yolov5n-seg | - | - | - | 7 MB |
| yolov5s-personface | - | - | - | 26 MB |
| yolox-s | - | - | - | 21 MB |
