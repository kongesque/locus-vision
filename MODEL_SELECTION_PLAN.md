# Model Selection Redesign — Implementation Plan

## Problem

The current model selection is hardcoded to 5 YOLO11 variants with 3 precision options, all CPU/ONNX only. Users run LocusVision on different hardware (Raspberry Pi + Hailo, Pi CPU-only, Mac, GPU machines) and prefer different YOLO versions. The create page will become overwhelming as we add more models and backends.

## Design Philosophy

**Ollama-style**: user picks a model by name, the system figures out how to run it.

- Model = a name (e.g. `yolov8s`). Not a name + precision + backend combination.
- System auto-detects hardware on startup (Hailo? GPU? CPU arch?)
- System auto-selects the best execution path for each model
- User never picks "backend" or "precision" — those are implementation details
- Model management (download/delete) lives in Settings, not in the create flow
- Create page shows one simple dropdown of installed models

## Architecture Overview

```
Startup:
  backend detects hardware → ["hailo", "onnx_cpu"]
  backend scans data/models/ → catalog of installed models
  each model resolves to best available format automatically

Create Page:
  Model: [yolov8s ▾]  ← installed models only, one dropdown

Settings > Models:
  Browse catalog, download/remove models
  See what hardware was detected
  Optional: override default backend preference
```

---

## Progress

- [x] **Phase 0A** — Model catalog file (`backend/data/model_catalog.json`) — 12 models, 5 YOLO families
- [x] **Phase 0B** — Hardware detection (`detect_backends()`) — probes Hailo/CUDA/CoreML, falls back to CPU
- [x] **Phase 0C** — Model resolution (`resolve_model()`) — Ollama-style name→best-format dispatch
- [x] **Phase 0** — Startup wiring (`main.py` lifespan stores `app.state.backends` + `app.state.model_catalog`)
- [x] **Phase 1A** — Enriched registry endpoint (`GET /api/models/registry`) — returns backends + install status
- [x] **Phase 1B** — Simplified download endpoint (precision optional, auto-resolves from backends)
- [x] **Phase 1C** — Delete endpoint (`DELETE /api/models/{model_name}`) — catalog-aware + glob fallback
- [x] **Phase 1D** — Catalog-aware `get_detector()` — legacy exact match → catalog resolution
- [x] **Phase 2A** — Models tab added to Settings page
- [x] **Phase 2B** — Model library component (`model-library.svelte`)
- [x] **Phase 2C** — Settings data loader fetches model registry
- [ ] **Phase 3A** — Remove hardcoded models from create page
- [ ] **Phase 3B** — Simplify tools panel to single dropdown
- [ ] **Phase 3C** — Update form submission to send simple model name
- [ ] **Phase 4A** — Backwards-compatible model name handling in `get_detector()`
- [ ] **Phase 4B** — Default model setting in database
- [ ] **Phase 4C** — Camera default uses system default
- [ ] **Phase 5A** — Create page respects system default model

> **Note:** Phases 0–2 complete. Backend has full catalog, hardware detection, model resolution, enriched registry, simplified download, delete, and catalog-aware detector. Frontend Settings page has the Model Library tab with hardware badges, installed/available sections, download, and remove. Next up: Phase 3 (simplified create page).

---

## Phase 0: Model Catalog & Hardware Detection

The foundation. Everything else builds on this.

### 0A: Model Catalog File

**New file: `backend/model_catalog.json`**

Static registry of all known models and their available formats. Ships with the app — users don't edit this. Updated when we add support for new models.

```json
{
  "models": {
    "yolo11n": {
      "label": "YOLO11 Nano",
      "family": "yolo11",
      "purpose": "detection",
      "classes": "coco80",
      "formats": {
        "onnx_fp32": { "file": "yolo11n.onnx", "size_mb": 10.2 },
        "onnx_fp16": { "file": "yolo11n_half.onnx", "size_mb": 5.1 },
        "onnx_int8": { "file": "yolo11n_int8.onnx", "size_mb": 2.7 }
      }
    },
    "yolo11s": {
      "label": "YOLO11 Small",
      "family": "yolo11",
      "purpose": "detection",
      "classes": "coco80",
      "formats": {
        "onnx_fp32": { "file": "yolo11s.onnx", "size_mb": 37.2 },
        "onnx_fp16": { "file": "yolo11s_half.onnx", "size_mb": 18.6 },
        "onnx_int8": { "file": "yolo11s_int8.onnx", "size_mb": 9.5 }
      }
    },
    "yolo11m": {
      "label": "YOLO11 Medium",
      "family": "yolo11",
      "purpose": "detection",
      "classes": "coco80",
      "formats": {
        "onnx_fp32": { "file": "yolo11m.onnx", "size_mb": 77.0 },
        "onnx_fp16": { "file": "yolo11m_half.onnx", "size_mb": 38.5 },
        "onnx_int8": { "file": "yolo11m_int8.onnx", "size_mb": 19.8 }
      }
    },
    "yolo11l": {
      "label": "YOLO11 Large",
      "family": "yolo11",
      "purpose": "detection",
      "classes": "coco80",
      "formats": {
        "onnx_fp32": { "file": "yolo11l.onnx", "size_mb": 99.0 },
        "onnx_fp16": { "file": "yolo11l_half.onnx", "size_mb": 49.5 },
        "onnx_int8": { "file": "yolo11l_int8.onnx", "size_mb": 25.3 }
      }
    },
    "yolo11x": {
      "label": "YOLO11 Extra Large",
      "family": "yolo11",
      "purpose": "detection",
      "classes": "coco80",
      "formats": {
        "onnx_fp32": { "file": "yolo11x.onnx", "size_mb": 224.0 },
        "onnx_fp16": { "file": "yolo11x_half.onnx", "size_mb": 112.0 },
        "onnx_int8": { "file": "yolo11x_int8.onnx", "size_mb": 57.3 }
      }
    },
    "yolov8n": {
      "label": "YOLOv8 Nano",
      "family": "yolov8",
      "purpose": "detection",
      "classes": "coco80",
      "formats": {
        "onnx_fp32": { "file": "yolov8n.onnx", "size_mb": 12.2 },
        "onnx_int8": { "file": "yolov8n_int8.onnx", "size_mb": 3.4 },
        "hailo": { "file": "yolov8n_h8l.hef", "size_mb": 7.0 }
      }
    },
    "yolov8s": {
      "label": "YOLOv8 Small",
      "family": "yolov8",
      "purpose": "detection",
      "classes": "coco80",
      "formats": {
        "onnx_fp32": { "file": "yolov8s.onnx", "size_mb": 44.8 },
        "onnx_int8": { "file": "yolov8s_int8.onnx", "size_mb": 11.5 },
        "hailo": { "file": "yolov8s_h8l.hef", "size_mb": 35.0, "fps_estimate": 59 }
      }
    },
    "yolov8s-pose": {
      "label": "YOLOv8 Small Pose",
      "family": "yolov8",
      "purpose": "pose",
      "classes": "coco-keypoints",
      "formats": {
        "hailo": { "file": "yolov8s_pose_h8l_pi.hef", "size_mb": 23.0, "fps_estimate": 51 }
      }
    },
    "yolov6n": {
      "label": "YOLOv6 Nano",
      "family": "yolov6",
      "purpose": "detection",
      "classes": "coco80",
      "formats": {
        "hailo": { "file": "yolov6n_h8l.hef", "size_mb": 14.0, "fps_estimate": 355 }
      }
    },
    "yolov5n-seg": {
      "label": "YOLOv5 Nano Segmentation",
      "family": "yolov5",
      "purpose": "segmentation",
      "classes": "coco80",
      "formats": {
        "hailo": { "file": "yolov5n_seg_h8l_mz.hef", "size_mb": 7.0, "fps_estimate": 65 }
      }
    },
    "yolov5s-personface": {
      "label": "YOLOv5 Small Person+Face",
      "family": "yolov5",
      "purpose": "person-face",
      "classes": ["person", "face"],
      "formats": {
        "hailo": { "file": "yolov5s_personface_h8l.hef", "size_mb": 26.0, "fps_estimate": 64 }
      }
    },
    "yolox-s": {
      "label": "YOLOX Small",
      "family": "yolox",
      "purpose": "detection",
      "classes": "coco80",
      "formats": {
        "hailo": { "file": "yolox_s_leaky_h8l_mz.hef", "size_mb": 21.0, "fps_estimate": 61 }
      }
    }
  },
  "format_priority": ["hailo", "onnx_int8", "onnx_fp16", "onnx_fp32"]
}
```

**Key design decisions:**
- `format_priority` defines which execution path the system prefers (best first)
- Each model has a flat name — no precision/backend encoding
- `purpose` field enables future filtering (show only detection models, only pose models, etc.)
- `fps_estimate` is optional — only populated where we have benchmark data
- Easy to extend: add a new model = add an entry to this JSON

### 0B: Hardware Detection

**Modify: `backend/services/model_manager.py`**

Add hardware detection that runs once on startup:

```python
def detect_backends() -> list[str]:
    """Detect available inference backends. Returns list in priority order."""
    backends = []

    # Hailo-8L
    try:
        import hailo_platform
        from hailo_platform import VDevice
        vd = VDevice()
        vd.release()
        backends.append("hailo")
    except Exception:
        pass

    # GPU (CUDA)
    try:
        import onnxruntime as ort
        if "CUDAExecutionProvider" in ort.get_available_providers():
            backends.append("onnx_cuda")
    except Exception:
        pass

    # CoreML (macOS)
    try:
        import onnxruntime as ort
        if "CoreMLExecutionProvider" in ort.get_available_providers():
            backends.append("onnx_coreml")
    except Exception:
        pass

    # CPU always available
    backends.append("onnx_int8")
    backends.append("onnx_fp16")
    backends.append("onnx_fp32")

    return backends
```

**Modify: `backend/main.py` lifespan**

Detect hardware and load catalog on startup:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.backends = detect_backends()
    app.state.model_catalog = load_model_catalog()
    # ... existing startup ...
```

### 0C: Model Resolution Logic

**New function in `backend/services/model_manager.py`:**

When user says "use yolov8s", the system resolves which file to actually load:

```python
def resolve_model(model_name: str, catalog: dict, backends: list[str]) -> dict:
    """
    Given a model name and available backends, return the best format to use.

    Returns: { "file": "yolov8s_h8l.hef", "backend": "hailo", "model_name": "yolov8s" }
    """
    model = catalog["models"].get(model_name)
    if not model:
        raise ValueError(f"Unknown model: {model_name}")

    priority = catalog["format_priority"]
    for fmt in priority:
        if fmt in model["formats"] and fmt_available(fmt, backends):
            format_info = model["formats"][fmt]
            file_path = os.path.join(MODELS_DIR, format_info["file"])
            if os.path.exists(file_path):
                return {
                    "file": format_info["file"],
                    "backend": fmt,
                    "model_name": model_name,
                    "path": file_path
                }

    raise FileNotFoundError(f"No installed format for model: {model_name}")
```

This is the core Ollama-like behavior — user picks a name, system picks the best way to run it.

---

## Phase 1: Backend API Changes

### 1A: Enriched Model Registry Endpoint

**Modify: `backend/routers/models.py`**

Replace the current `GET /api/models/registry` (which returns flat filenames) with a richer response:

```
GET /api/models/registry
```

Response:
```json
{
  "backends": ["hailo", "onnx_int8", "onnx_fp16", "onnx_fp32"],
  "models": [
    {
      "name": "yolo11n",
      "label": "YOLO11 Nano",
      "family": "yolo11",
      "purpose": "detection",
      "installed": true,
      "active_format": "onnx_int8",
      "size_mb": 2.7,
      "fps_estimate": 14
    },
    {
      "name": "yolov8s",
      "label": "YOLOv8 Small",
      "family": "yolov8",
      "purpose": "detection",
      "installed": true,
      "active_format": "hailo",
      "size_mb": 35.0,
      "fps_estimate": 59
    },
    {
      "name": "yolov8s-pose",
      "label": "YOLOv8 Small Pose",
      "family": "yolov8",
      "purpose": "pose",
      "installed": false,
      "available_formats": ["hailo"],
      "size_mb": 23.0
    }
  ]
}
```

**Key fields:**
- `installed`: whether any usable format file exists on disk
- `active_format`: which format will be used (auto-resolved from hardware + priority)
- `fps_estimate`: from catalog or from benchmarks if available
- Frontend only needs `name` and `installed` for the create page dropdown

### 1B: Model Download Endpoint Changes

**Modify: `POST /api/models/download`**

Current: takes `model_name` + `precision` separately.
New: takes just `model_name`. Backend decides which format to download based on detected hardware.

```
POST /api/models/download
{ "model_name": "yolov8s" }
```

Backend logic:
1. Look up model in catalog
2. Check detected backends
3. Download/export the best available format
   - Hailo detected + HEF available → copy from `/usr/share/hailo-models/` (instant)
   - CPU only + ONNX available → run `export_model.py` for best precision
4. Return job status as before

### 1C: Model Delete Endpoint

**New: `DELETE /api/models/{model_name}`**

Removes all format files for a model from `data/models/`.

### 1D: Update get_detector() Resolution

**Modify: `backend/services/onnx_detector.py`**

The `get_detector()` function currently expects exact filenames like `yolo11n_int8`. Change it to accept simple names like `yolo11n` and resolve internally:

```python
def get_detector(model_name: str, conf_threshold=None):
    # If model_name is a simple name (no _int8/_half suffix), resolve it
    resolved = resolve_model(model_name, catalog, backends)
    if resolved["backend"] == "hailo":
        return get_hailo_detector(resolved["path"], conf_threshold)
    else:
        return OnnxDetector(resolved["path"], conf_threshold)
```

This is backwards-compatible — existing `yolo11n_int8` style names still work as direct file lookups.

---

## Phase 2: Frontend — Settings Model Library

### 2A: New Models Tab in Settings

**Modify: `src/routes/(app)/settings/+page.svelte`**

Add a "Models" tab (visible to all users, not just admins):

```
Tabs: [Profile] [Security] [Appearance] [Models] [Admin]
```

### 2B: Model Library UI

**New component: `src/lib/components/settings/model-library.svelte`**

```
┌─────────────────────────────────────────────────────┐
│  Models                                             │
│                                                     │
│  Hardware detected:  Hailo-8L · ARM64 CPU           │
│                                                     │
│  ── Installed ──────────────────────────────────    │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  YOLO11 Nano                        2.7 MB    │  │
│  │  detection · coco80 · CPU INT8 · ~14 fps      │  │
│  │                                    [Remove]   │  │
│  ├───────────────────────────────────────────────┤  │
│  │  YOLOv8 Small                       35 MB     │  │
│  │  detection · coco80 · Hailo · ~59 fps         │  │
│  │                                    [Remove]   │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ── Available ──────────────────────────────────    │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  YOLO11 Small                       9.5 MB    │  │
│  │  detection · coco80 · CPU INT8                │  │
│  │                                  [Download]   │  │
│  ├───────────────────────────────────────────────┤  │
│  │  YOLOv8 Small Pose                  23 MB     │  │
│  │  pose · Hailo · ~51 fps                       │  │
│  │                                  [Download]   │  │
│  ├───────────────────────────────────────────────┤  │
│  │  YOLOv6 Nano                        14 MB     │  │
│  │  detection · coco80 · Hailo · ~355 fps        │  │
│  │                                  [Download]   │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Preferred backend:  [Auto ▾]                       │
│  (Auto uses Hailo when available, falls back to CPU)│
└─────────────────────────────────────────────────────┘
```

**Design notes:**
- Models show one line of metadata: purpose, classes, backend, estimated fps
- "Available" section only shows models compatible with detected hardware
- No precision picker — system auto-selects the best
- Download button triggers `POST /api/models/download` with just the model name
- Download progress shown inline (same polling as current implementation)
- "Preferred backend" dropdown at bottom — defaults to Auto, power users can force CPU/Hailo

### 2C: Settings Page Data Loader

**Modify: `src/routes/(app)/settings/+page.ts` (or +page.server.ts)**

Fetch model registry data for the Models tab:

```typescript
// Fetch model registry for Models tab
const modelsRes = await fetch(`${API_URL}/api/models/registry`);
const modelRegistry = modelsRes.ok ? await modelsRes.json() : { backends: [], models: [] };
```

---

## Phase 3: Frontend — Simplified Create Page

### 3A: Remove Hardcoded Models

**Modify: `src/routes/(app)/create/[taskId]/+page.svelte`**

Remove:
- `YOLO11_MODELS` constant (lines 15-21)
- `selectedPrecision` state (line 46)
- `resolvedModelName` derived (lines 63-67)
- `isModelMissing` check (line 69)
- `handleDownloadModel()` (lines 86-104)
- `pollDownloadStatus()` (lines 106-131)

Replace with:
```typescript
// Fetch installed models on mount
let installedModels = $state<{ name: string; label: string; fps_estimate?: number }[]>([]);
let selectedModel = $state<string>('');

onMount(async () => {
    const res = await fetch(`${API_URL}/api/models/registry`);
    if (res.ok) {
        const data = await res.json();
        installedModels = data.models.filter((m: any) => m.installed);
        // Default to first installed model, or 'yolo11n' if available
        selectedModel = installedModels.find(m => m.name === 'yolo11n')?.name
            || installedModels[0]?.name || '';
    }
});
```

Now `selectedModel` is the simple name (e.g. `yolov8s`), and the backend resolves everything.

### 3B: Simplify Tools Panel

**Modify: `src/lib/components/create/tools-panel.svelte`**

The entire model section becomes:

```
┌─────────────────────────────────────────┐
│  Model                                  │
│                                         │
│  [YOLO11 Nano          ▾]              │
│   ~14 fps on CPU                        │
│                                         │
│  No models installed?                   │
│  Go to Settings > Models to download.   │
│                                         │
│  ── FPS ──────────────────────────      │
│  [====●================] 12             │
│                                         │
│  ── Confidence ───────────────────      │
│  [======●==============] 0.25           │
└─────────────────────────────────────────┘
```

Remove:
- `ModelInfo` interface (lines 32-37)
- `allModels` prop
- `selectedPrecision` prop and related UI
- Precision toggle group (lines 220-268)
- Download status section (lines 272-316) — downloading now lives in Settings
- `isPrecisionDownloaded()` helper

Add:
- `installedModels` prop (from registry API)
- Single `<Select>` dropdown showing `label` and optional fps hint
- Link to Settings > Models if no models installed

### 3C: Update Form Submission

**Modify: `src/routes/(app)/create/[taskId]/+page.svelte`**

Current (line 205, 240): sends `resolvedModelName` (e.g. `yolo11n_int8`)
New: sends `selectedModel` (e.g. `yolo11n`) — backend resolves the rest

```typescript
// Video processing
formData.append('model_name', selectedModel);  // just the name

// Camera setup
body.model_name = selectedModel;  // just the name
```

---

## Phase 4: Backend Compatibility

### 4A: Backwards-Compatible Model Name Handling

The database has existing rows with `model_name = "yolo11n_int8"`. The new system uses `model_name = "yolo11n"`. We need both to work.

**Modify: `get_detector()` in `backend/services/onnx_detector.py`**

```python
def get_detector(model_name: str, conf_threshold=None):
    # Legacy: exact filename match (e.g. "yolo11n_int8")
    exact_path = os.path.join(MODELS_DIR, f"{model_name}.onnx")
    if os.path.exists(exact_path):
        return OnnxDetector(exact_path, conf_threshold)

    # New: resolve from catalog (e.g. "yolo11n" → best available format)
    resolved = resolve_model(model_name)
    ...
```

No database migration needed. Old names keep working. New tasks use simple names.

### 4B: Default Model Setting

**Modify: `backend/database.py`**

Add a `settings` table entry for default model:

```sql
-- in the existing app_settings or a new key-value store
INSERT OR IGNORE INTO app_settings (key, value) VALUES ('default_model', 'yolo11n');
```

**New endpoint: `GET/PUT /api/settings/default-model`**

Used by the Settings page to get/set the default model. The create page uses this as the initial `selectedModel` value.

### 4C: Camera Default

**Modify: `backend/models.py`**

Change camera default from hardcoded `yolo11n` to use the system default:

```python
class CameraCreate(BaseModel):
    model_name: str | None = None  # None = use system default
```

When `model_name` is None, the camera router reads the default from settings.

---

## Phase 5: Global Default on Create Page

### 5A: Respect System Default

**Modify: `src/routes/(app)/create/[taskId]/+page.svelte`**

```typescript
onMount(async () => {
    // Fetch installed models + system default
    const [registryRes, defaultRes] = await Promise.all([
        fetch(`${API_URL}/api/models/registry`),
        fetch(`${API_URL}/api/settings/default-model`)
    ]);

    if (registryRes.ok) {
        const data = await registryRes.json();
        installedModels = data.models.filter((m: any) => m.installed);
    }

    if (defaultRes.ok) {
        const { model } = await defaultRes.json();
        selectedModel = model;
    } else {
        selectedModel = installedModels[0]?.name || '';
    }
});
```

Most users never change the default. Power users override per-task in the dropdown.

---

## Migration & Rollout

### Step 1: Ship catalog + detection + enriched API (Phase 0 + 1)
- No frontend changes yet
- Existing UI still works via backwards-compatible `get_detector()`
- Validate hardware detection works on Pi, Mac, GPU machines

### Step 2: Ship Settings model library (Phase 2)
- Users can now browse and download models from Settings
- Create page still works the old way

### Step 3: Ship simplified create page (Phase 3 + 4 + 5)
- Remove precision/download UI from create flow
- Switch to simple model names
- Old database entries still work

---

## Files Changed Summary

| File | Action | Phase | What Changes |
|------|--------|-------|-------------|
| `backend/data/model_catalog.json` | NEW | 0 | Static model registry |
| `backend/services/model_manager.py` | MODIFY | 0, 1 | Hardware detection, model resolution, download logic |
| `backend/main.py` | MODIFY | 0 | Detect hardware on startup |
| `backend/routers/models.py` | MODIFY | 1 | Enriched registry endpoint, simplified download |
| `backend/services/onnx_detector.py` | MODIFY | 1, 4 | Catalog-aware `get_detector()` with legacy fallback |
| `backend/models.py` | MODIFY | 4 | Optional `model_name` on CameraCreate |
| `backend/database.py` | MODIFY | 4 | Default model setting |
| `backend/routers/settings.py` | MODIFY | 4 | Default model endpoint |
| `src/routes/(app)/settings/+page.svelte` | MODIFY | 2 | Add Models tab |
| `src/lib/components/settings/model-library.svelte` | NEW | 2 | Model library UI component |
| `src/routes/(app)/create/[taskId]/+page.svelte` | MODIFY | 3 | Remove hardcoded models, use registry |
| `src/lib/components/create/tools-panel.svelte` | MODIFY | 3 | Single dropdown, remove precision/download UI |

---

## What This Enables

1. **Pi + Hailo user**: downloads `yolov8s`, system auto-runs on Hailo at 59fps
2. **Pi CPU-only user**: downloads `yolo11n`, system auto-picks INT8 at 14fps
3. **Mac user**: downloads `yolo11n`, system uses CoreML or FP32 ONNX
4. **GPU user**: downloads `yolo11s`, system uses CUDA provider
5. **"I like YOLOv8" user**: downloads `yolov8s`, uses it — no friction
6. **Simple user**: never touches model selection, system default just works
7. **Power user**: browses full catalog in Settings, picks exactly what they want

All from the same UI. One dropdown on create. One library page in Settings.
