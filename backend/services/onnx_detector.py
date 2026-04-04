"""
ONNX-based YOLO detector with ByteTrack tracking.

Drop-in replacement for ultralytics.YOLO — uses onnxruntime for inference
and supervision for tracking. Drastically reduces the dependency footprint
(no PyTorch required at runtime).
"""

import os
import json
import time
import numpy as np
import cv2
import onnxruntime as ort
import supervision as sv

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "data", "models")
CLASSES_PATH = os.path.join(BASE_DIR, "data", "coco_classes.json")

os.makedirs(MODELS_DIR, exist_ok=True)

# ── Load COCO class names once ───────────────────────────────────
_class_names: dict[int, str] = {}


def _load_class_names() -> dict[int, str]:
    global _class_names
    if _class_names:
        return _class_names
    if os.path.exists(CLASSES_PATH):
        with open(CLASSES_PATH, "r") as f:
            raw = json.load(f)
            _class_names = {int(k): v for k, v in raw.items()}
    else:
        # Fallback: generate placeholder names
        _class_names = {i: f"class_{i}" for i in range(80)}
    return _class_names


# ── NMS (Non-Maximum Suppression) ────────────────────────────────

def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.45) -> np.ndarray:
    """
    Standard greedy NMS. boxes: (N, 4) as x1y1x2y2, scores: (N,).
    Returns indices to keep.
    """
    if len(boxes) == 0:
        return np.array([], dtype=int)

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)

    order = scores.argsort()[::-1]
    keep = []

    while order.size > 0:
        i = order[0]
        keep.append(i)

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)

        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]

    return np.array(keep, dtype=int)


# ── Detection result container ───────────────────────────────────

class DetectionResult:
    """
    Holds detection/tracking results in a shape compatible with the
    existing codebase (replaces ultralytics Results objects).
    """

    def __init__(
        self,
        boxes_xywh: np.ndarray,
        scores: np.ndarray,
        class_ids: np.ndarray,
        track_ids: list[int] | None = None,
    ):
        self.boxes_xywh = boxes_xywh      # (N, 4) — center_x, center_y, w, h
        self.scores = scores               # (N,)
        self.class_ids = class_ids         # (N,) int
        self.track_ids = track_ids         # list[int] or None

    @property
    def has_detections(self) -> bool:
        return len(self.boxes_xywh) > 0


# ── ONNX Detector ────────────────────────────────────────────────

class OnnxDetector:
    """
    Loads a YOLO ONNX model and runs detection + optional ByteTrack tracking.
    """

    def __init__(self, model_path: str, conf_threshold: float = 0.15, iou_threshold: float = 0.45):
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.names = _load_class_names()

        # Pick the best available provider
        providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        available = ort.get_available_providers()
        use_providers = [p for p in providers if p in available] or ["CPUExecutionProvider"]

        self.session = ort.InferenceSession(model_path, providers=use_providers)

        # Determine expected input shape from the model
        input_meta = self.session.get_inputs()[0]
        self.input_name = input_meta.name
        # Shape is typically [1, 3, H, W]
        shape = input_meta.shape
        self.input_h = shape[2] if isinstance(shape[2], int) else 640
        self.input_w = shape[3] if isinstance(shape[3], int) else 640

    def _preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, float, int, int]:
        """
        Letterbox-resize + normalize to [1, 3, H, W] float32.
        Returns (blob, ratio, ratio, pad_w, pad_h).
        """
        img_h, img_w = frame.shape[:2]

        # Compute scale to fit within input dims while preserving aspect ratio
        r = min(self.input_w / img_w, self.input_h / img_h)
        new_w, new_h = int(img_w * r), int(img_h * r)
        pad_w = (self.input_w - new_w) // 2
        pad_h = (self.input_h - new_h) // 2

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Create padded canvas (gray fill)
        canvas = np.full((self.input_h, self.input_w, 3), 114, dtype=np.uint8)
        canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

        # BGR → RGB, HWC → CHW, normalize to 0-1, add batch dim
        blob = canvas[:, :, ::-1].astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[np.newaxis, ...]

        return blob, r, r, pad_w, pad_h

    def _postprocess(
        self, output: np.ndarray, ratio: float, pad_w: int, pad_h: int,
        classes: list[int] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Parse raw ONNX output → (boxes_xyxy, scores, class_ids).
        YOLO output shape: [1, 84, N] where 84 = 4 (box) + 80 (classes).
        """
        # Squeeze batch dim and transpose to (N, 84)
        preds = output[0]  # (84, N)
        if preds.shape[0] < preds.shape[1]:
            preds = preds.T  # → (N, 84)

        # Split box coords and class scores
        box_preds = preds[:, :4]       # cx, cy, w, h
        cls_scores = preds[:, 4:]      # (N, 80)

        # Best class per detection
        class_ids = cls_scores.argmax(axis=1)
        scores = cls_scores[np.arange(len(cls_scores)), class_ids]

        # Confidence filter
        mask = scores >= self.conf_threshold
        box_preds = box_preds[mask]
        scores = scores[mask]
        class_ids = class_ids[mask]

        # Class filter (if specific classes requested)
        if classes is not None and len(classes) > 0:
            cls_mask = np.isin(class_ids, classes)
            box_preds = box_preds[cls_mask]
            scores = scores[cls_mask]
            class_ids = class_ids[cls_mask]

        if len(box_preds) == 0:
            return np.empty((0, 4)), np.empty(0), np.empty(0, dtype=int)

        # Convert cx, cy, w, h → x1, y1, x2, y2
        cx, cy, w, h = box_preds[:, 0], box_preds[:, 1], box_preds[:, 2], box_preds[:, 3]
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2
        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        # Rescale from letterboxed coords to original image coords
        boxes_xyxy[:, [0, 2]] = (boxes_xyxy[:, [0, 2]] - pad_w) / ratio
        boxes_xyxy[:, [1, 3]] = (boxes_xyxy[:, [1, 3]] - pad_h) / ratio

        # NMS
        keep = _nms(boxes_xyxy, scores, self.iou_threshold)
        return boxes_xyxy[keep], scores[keep], class_ids[keep].astype(int)

    def detect(self, frame: np.ndarray, classes: list[int] | None = None) -> DetectionResult:
        """Run detection only (no tracking)."""
        start_time = time.perf_counter()
        
        blob, ratio, _, pad_w, pad_h = self._preprocess(frame)
        outputs = self.session.run(None, {self.input_name: blob})
        boxes_xyxy, scores, class_ids = self._postprocess(outputs[0], ratio, pad_w, pad_h, classes)
        
        # Record inference metrics
        inference_ms = (time.perf_counter() - start_time) * 1000
        self._record_metrics(inference_ms, len(boxes_xyxy))

        if len(boxes_xyxy) == 0:
            return DetectionResult(np.empty((0, 4)), np.empty(0), np.empty(0, dtype=int))

        # Convert xyxy → xywh (center)
        boxes_xywh = self._xyxy_to_xywh(boxes_xyxy)
        return DetectionResult(boxes_xywh, scores, class_ids)

    def get_detections(self, frame: np.ndarray, classes: list[int] | None = None) -> sv.Detections:
        """Run detection and return supervision Detections object for upstream tracking."""
        start_time = time.perf_counter()
        
        blob, ratio, _, pad_w, pad_h = self._preprocess(frame)
        outputs = self.session.run(None, {self.input_name: blob})
        boxes_xyxy, scores, class_ids = self._postprocess(outputs[0], ratio, pad_w, pad_h, classes)
        
        # Record inference metrics
        inference_ms = (time.perf_counter() - start_time) * 1000
        self._record_metrics(inference_ms, len(boxes_xyxy))

        if len(boxes_xyxy) == 0:
            return sv.Detections.empty()

        return sv.Detections(
            xyxy=boxes_xyxy,
            confidence=scores,
            class_id=class_ids,
        )

    @staticmethod
    def _xyxy_to_xywh(boxes: np.ndarray) -> np.ndarray:
        """Convert (x1, y1, x2, y2) → (cx, cy, w, h)."""
        xywh = np.empty_like(boxes)
        xywh[:, 0] = (boxes[:, 0] + boxes[:, 2]) / 2  # cx
        xywh[:, 1] = (boxes[:, 1] + boxes[:, 3]) / 2  # cy
        xywh[:, 2] = boxes[:, 2] - boxes[:, 0]         # w
        xywh[:, 3] = boxes[:, 3] - boxes[:, 1]         # h
        return xywh

    def _record_metrics(self, inference_ms: float, num_detections: int):
        """Record detection metrics to the global collector."""
        try:
            # Import here to avoid circular dependency
            from services.metrics_collector import metrics_collector
            # Get model name from cached detectors
            model_name = "unknown"
            for name, detector in _detector_cache.items():
                if detector is self:
                    model_name = name
                    break
            metrics_collector.record_detection(inference_ms, num_detections, model_name)
        except Exception:
            # Silently fail - metrics should not break detection
            pass


# ── Model cache (singleton per model name) ───────────────────────

_detector_cache: dict[str, OnnxDetector] = {}


def get_detector(model_name: str, conf_threshold: float | None = None) -> OnnxDetector:
    """
    Get or create a cached OnnxDetector for the given model name.

    Resolution order:
    1. Legacy exact match: `data/models/{model_name}.onnx` (backwards-compatible)
    2. Catalog resolution: look up model_name in catalog, pick best available format

    This ensures existing database rows with names like 'yolo11n_int8' still work,
    while new simple names like 'yolo11n' resolve through the catalog.
    """
    cache_key = f"{model_name}@{conf_threshold}" if conf_threshold is not None else model_name
    if cache_key in _detector_cache:
        return _detector_cache[cache_key]

    ct = conf_threshold if conf_threshold is not None else 0.15

    # Strategy 1: Legacy exact filename match (e.g. "yolo11n_int8" → yolo11n_int8.onnx)
    exact_path = os.path.join(MODELS_DIR, f"{model_name}.onnx")
    if os.path.exists(exact_path):
        print(f"[OnnxDetector] Loading model (legacy): {exact_path} (conf={ct})")
        _detector_cache[cache_key] = OnnxDetector(exact_path, conf_threshold=ct)
        return _detector_cache[cache_key]

    # Strategy 2: Catalog resolution (e.g. "yolo11n" → best available format)
    try:
        from services.model_manager import resolve_model, load_model_catalog, detect_backends
        catalog = load_model_catalog()
        backends = detect_backends()
        resolved = resolve_model(model_name, catalog, backends)
        model_path = resolved["path"]
        print(f"[OnnxDetector] Loading model (catalog): {model_path} "
              f"(format={resolved['backend']}, conf={ct})")
        _detector_cache[cache_key] = OnnxDetector(model_path, conf_threshold=ct)
        return _detector_cache[cache_key]
    except (ValueError, FileNotFoundError):
        pass

    # Nothing found
    raise FileNotFoundError(
        f"Model '{model_name}' not found. "
        f"No exact file '{model_name}.onnx' in {MODELS_DIR} and no catalog match. "
        f"Download models from Settings > Models."
    )


def list_models() -> list[str]:
    """List all available .onnx models in the models directory."""
    models = []
    if os.path.exists(MODELS_DIR):
        for f in os.listdir(MODELS_DIR):
            if f.endswith(".onnx"):
                models.append(f.replace(".onnx", ""))
    return sorted(models)

