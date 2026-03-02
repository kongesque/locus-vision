"""
Unit tests for the AnalyticsEngine service.

Verifies tracking isolation, zone counting, and motion detection logic.
"""

import os
import sys
import numpy as np
import pytest
import cv2

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.analytics_engine import AnalyticsEngine, AnalyticsResult
from services.onnx_detector import MODELS_DIR

MODEL_NAME = "yolo11n"
MODEL_PATH = os.path.join(MODELS_DIR, f"{MODEL_NAME}.onnx")

@pytest.fixture
def engine():
    """Create an AnalyticsEngine instance."""
    if not os.path.exists(MODEL_PATH):
        pytest.skip(f"Model not found: {MODEL_PATH}")
    return AnalyticsEngine(model_name=MODEL_NAME)

@pytest.fixture
def blank_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)

class TestAnalyticsEngine:
    def test_initialization(self, engine):
        assert engine.detector is not None
        assert engine.tracker is not None
        assert len(engine.track_history) == 0
        assert len(engine.crossed_objects) == 0

    def test_reset(self, engine):
        engine.track_history[1] = [(100, 100)]
        engine.crossed_objects[1] = True
        engine.reset()
        assert len(engine.track_history) == 0
        assert len(engine.crossed_objects) == 0

    def test_tracking_isolation(self):
        """Verifies that two engines have separate tracking states."""
        engine1 = AnalyticsEngine(model_name=MODEL_NAME)
        engine2 = AnalyticsEngine(model_name=MODEL_NAME)
        
        assert engine1.tracker is not engine2.tracker
        
        engine1.track_history[1] = [(100, 100)]
        assert 1 not in engine2.track_history

    def test_process_frame_returns_result(self, engine, blank_frame):
        result = engine.process_frame(blank_frame)
        assert isinstance(result, AnalyticsResult)
        assert result.total_count == 0
        assert result.resolution == {"w": 640, "h": 480}

    def test_set_zones(self, engine):
        zones = [
            {
                "id": "zone1",
                "type": "polygon",
                "points": [{"x": 0.1, "y": 0.1}, {"x": 0.5, "y": 0.1}, {"x": 0.5, "y": 0.5}, {"x": 0.1, "y": 0.5}],
                "color": "#ff0000",
                "classes": ["person"]
            }
        ]
        engine.set_zones(zones)
        assert len(engine.parsed_zones) == 1
        assert engine.parsed_zones[0].zone_id == "zone1"
        assert engine.parsed_zones[0].zone_type == "polygon"
