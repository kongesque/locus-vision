"""
Unit tests for the ONNX detector service.

Verifies model loading, preprocessing, detection, tracking,
class name mapping, and result shapes using the real yolo11n.onnx model.

Run:
    cd backend && source .venv/bin/activate && pytest tests/ -v
"""

import os
import sys
import numpy as np
import pytest

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.onnx_detector import (
    OnnxDetector,
    DetectionResult,
    get_detector,
    _load_class_names,
    _nms,
    MODELS_DIR,
)


# ── Fixtures ─────────────────────────────────────────────────────

MODEL_NAME = "yolo11n"
MODEL_PATH = os.path.join(MODELS_DIR, f"{MODEL_NAME}.onnx")

@pytest.fixture(scope="module")
def detector():
    """Load the real ONNX model once for the whole test module."""
    if not os.path.exists(MODEL_PATH):
        pytest.skip(f"Model not found: {MODEL_PATH}. Run: python scripts/export_model.py {MODEL_NAME}")
    return OnnxDetector(MODEL_PATH)


@pytest.fixture
def blank_frame():
    """A 640×480 black frame (no objects)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def noisy_frame():
    """A 640×480 frame with random noise (may trigger some detections)."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)


# ── Class Names ──────────────────────────────────────────────────

class TestClassNames:
    def test_loads_coco_classes(self):
        names = _load_class_names()
        assert isinstance(names, dict)
        assert len(names) == 80

    def test_first_class_is_person(self):
        names = _load_class_names()
        assert names[0] == "person"

    def test_all_values_are_strings(self):
        names = _load_class_names()
        for k, v in names.items():
            assert isinstance(k, int)
            assert isinstance(v, str)
            assert len(v) > 0


# ── NMS ──────────────────────────────────────────────────────────

class TestNMS:
    def test_empty_input(self):
        result = _nms(np.empty((0, 4)), np.empty(0))
        assert len(result) == 0

    def test_single_box(self):
        boxes = np.array([[10, 10, 50, 50]], dtype=np.float32)
        scores = np.array([0.9])
        keep = _nms(boxes, scores, iou_threshold=0.5)
        assert len(keep) == 1
        assert keep[0] == 0

    def test_suppresses_overlapping(self):
        boxes = np.array([
            [10, 10, 50, 50],
            [12, 12, 52, 52],  # heavily overlapping with first
            [200, 200, 300, 300],  # no overlap
        ], dtype=np.float32)
        scores = np.array([0.9, 0.8, 0.7])
        keep = _nms(boxes, scores, iou_threshold=0.5)
        # Should keep box 0 (highest score) and box 2 (no overlap)
        assert 0 in keep
        assert 2 in keep
        assert 1 not in keep

    def test_no_suppression_when_no_overlap(self):
        boxes = np.array([
            [0, 0, 10, 10],
            [100, 100, 110, 110],
            [200, 200, 210, 210],
        ], dtype=np.float32)
        scores = np.array([0.5, 0.6, 0.7])
        keep = _nms(boxes, scores, iou_threshold=0.5)
        assert len(keep) == 3


# ── DetectionResult ──────────────────────────────────────────────

class TestDetectionResult:
    def test_empty_result(self):
        r = DetectionResult(np.empty((0, 4)), np.empty(0), np.empty(0, dtype=int))
        assert not r.has_detections
        assert r.track_ids is None

    def test_result_with_detections(self):
        boxes = np.array([[100, 100, 50, 50]], dtype=np.float32)
        scores = np.array([0.9])
        class_ids = np.array([0])
        r = DetectionResult(boxes, scores, class_ids, track_ids=[1])
        assert r.has_detections
        assert r.track_ids == [1]
        assert r.class_ids[0] == 0


# ── OnnxDetector ─────────────────────────────────────────────────

class TestOnnxDetector:
    def test_model_loads(self, detector):
        """Model loads without error and has correct input shape."""
        assert detector.session is not None
        assert detector.input_h == 640
        assert detector.input_w == 640

    def test_has_class_names(self, detector):
        """Detector has COCO class names loaded."""
        assert len(detector.names) == 80
        assert detector.names[0] == "person"

    def test_preprocess_shape(self, detector, blank_frame):
        """Preprocessing produces correct tensor shape."""
        blob, ratio, _, pad_w, pad_h = detector._preprocess(blank_frame)
        assert blob.shape == (1, 3, 640, 640)
        assert blob.dtype == np.float32
        assert 0.0 <= blob.min() <= blob.max() <= 1.0

    def test_preprocess_preserves_aspect_ratio(self, detector):
        """Letterboxing a non-square image preserves ratio with padding."""
        wide_frame = np.zeros((360, 1280, 3), dtype=np.uint8)
        blob, ratio, _, pad_w, pad_h = detector._preprocess(wide_frame)
        assert blob.shape == (1, 3, 640, 640)
        assert pad_h > 0  # vertical padding expected for wide image

    def test_detect_returns_result(self, detector, blank_frame):
        """detect() returns a DetectionResult even on blank frames."""
        result = detector.detect(blank_frame)
        assert isinstance(result, DetectionResult)
        assert isinstance(result.boxes_xywh, np.ndarray)
        assert isinstance(result.scores, np.ndarray)
        assert isinstance(result.class_ids, np.ndarray)

    def test_detect_shapes_consistent(self, detector, noisy_frame):
        """All output arrays have the same length."""
        result = detector.detect(noisy_frame)
        n = len(result.boxes_xywh)
        assert len(result.scores) == n
        assert len(result.class_ids) == n

    def test_track_returns_track_ids(self, detector, blank_frame):
        """track() returns a result with track_ids (possibly empty)."""
        result = detector.track(blank_frame)
        assert isinstance(result, DetectionResult)
        assert result.track_ids is not None  # always a list for track()
        assert isinstance(result.track_ids, list)

    def test_track_shapes_consistent(self, detector, noisy_frame):
        """track() output arrays all match in length."""
        result = detector.track(noisy_frame)
        n = len(result.boxes_xywh)
        assert len(result.scores) == n
        assert len(result.class_ids) == n
        if result.has_detections:
            assert len(result.track_ids) == n

    def test_class_filter(self, detector, noisy_frame):
        """Passing a class filter only returns that class."""
        result = detector.detect(noisy_frame, classes=[0])  # person only
        for cls_id in result.class_ids:
            assert cls_id == 0

    def test_reset_tracker(self, detector):
        """reset_tracker() does not error and creates a fresh tracker."""
        detector.reset_tracker()
        assert detector.tracker is not None

    def test_xyxy_to_xywh_conversion(self):
        """Static conversion from xyxy to xywh is correct."""
        xyxy = np.array([[10, 20, 50, 80]], dtype=np.float32)
        xywh = OnnxDetector._xyxy_to_xywh(xyxy)
        assert xywh.shape == (1, 4)
        np.testing.assert_allclose(xywh[0], [30, 50, 40, 60])  # cx=30, cy=50, w=40, h=60


# ── get_detector cache ───────────────────────────────────────────

class TestGetDetector:
    def test_returns_detector(self):
        if not os.path.exists(MODEL_PATH):
            pytest.skip(f"Model not found: {MODEL_PATH}")
        d = get_detector(MODEL_NAME)
        assert isinstance(d, OnnxDetector)

    def test_caches_same_instance(self):
        if not os.path.exists(MODEL_PATH):
            pytest.skip(f"Model not found: {MODEL_PATH}")
        d1 = get_detector(MODEL_NAME)
        d2 = get_detector(MODEL_NAME)
        assert d1 is d2

    def test_missing_model_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            get_detector("nonexistent_model_xyz")
