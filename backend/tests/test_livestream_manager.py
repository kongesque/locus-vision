"""
Unit tests for Livestream Manager hardware acceleration integration.

Verifies that StreamContext properly uses hardware-accelerated video capture.
"""

import os
import sys
import time
import pytest

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.livestream_manager import StreamContext, LivestreamManager
from services.video_capture import is_raspberry_pi


class TestStreamContext:
    """Test StreamContext with hardware acceleration options."""
    
    def test_stream_context_accepts_hw_accel_param(self):
        """StreamContext should accept enable_hw_accel parameter."""
        ctx = StreamContext(
            camera_id="test_cam",
            enable_hw_accel=True,
            source=0
        )
        assert ctx.enable_hw_accel is True
        assert ctx.source == 0
        ctx.stop()
    
    def test_stream_context_accepts_custom_source(self):
        """StreamContext should accept custom video source."""
        ctx = StreamContext(
            camera_id="test_cam",
            source="/tmp/test.mp4",
            enable_hw_accel=False
        )
        assert ctx.source == "/tmp/test.mp4"
        ctx.stop()
    
    def test_stream_context_defaults(self):
        """StreamContext should have sensible defaults."""
        ctx = StreamContext(camera_id="test_cam")
        assert ctx.source == 0  # Default to webcam
        assert ctx.enable_hw_accel is True  # Default to try hardware
        assert ctx.target_fps == 24
        ctx.stop()


class TestLivestreamManager:
    """Test LivestreamManager integration."""
    
    def test_manager_passes_hw_accel_to_context(self):
        """Manager should pass hardware acceleration setting to StreamContext."""
        manager = LivestreamManager()
        
        # Create stream with hardware acceleration disabled
        stream = manager.get_or_create_stream(
            camera_id="test_hw",
            enable_hw_accel=False,
            source=0
        )
        
        assert stream.enable_hw_accel is False
        stream.stop()
    
    def test_manager_passes_source_to_context(self):
        """Manager should pass source to StreamContext."""
        manager = LivestreamManager()
        
        stream = manager.get_or_create_stream(
            camera_id="test_source",
            source="rtsp://example.com/stream"
        )
        
        assert stream.source == "rtsp://example.com/stream"
        stream.stop()


class TestHardwareIntegration:
    """
    Integration tests for hardware acceleration.
    
    These tests verify the full pipeline works with hardware acceleration.
    """
    
    @pytest.mark.skipif(not is_raspberry_pi(), reason="Not running on Raspberry Pi")
    def test_pi_hw_detection(self):
        """Verify Raspberry Pi detection works."""
        from services.video_capture import check_v4l2_m2m_available
        
        # This just verifies the functions don't crash
        result = check_v4l2_m2m_available()
        assert isinstance(result, bool)
    
    def test_stream_start_stop(self):
        """Stream should start and stop cleanly."""
        ctx = StreamContext(
            camera_id="test_start_stop",
            enable_hw_accel=False,  # Disable to avoid camera issues
            source=0
        )
        
        # Should not raise
        ctx.start()
        time.sleep(0.1)  # Brief moment to start
        ctx.stop()
        
        # Verify stopped state
        assert not ctx._running


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
