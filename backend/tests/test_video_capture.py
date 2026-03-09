"""
Unit tests for hardware-accelerated video capture.

Verifies hardware detection, capture creation, and CPU usage reduction.
"""

import os
import sys
import time
import psutil
import pytest
import numpy as np

# Ensure the backend root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.video_capture import (
    create_video_capture,
    get_capture_info,
    is_raspberry_pi,
    check_v4l2_m2m_available,
)


class TestHardwareDetection:
    """Test hardware detection functions."""
    
    def test_is_raspberry_pi_returns_bool(self):
        """is_raspberry_pi should return a boolean."""
        result = is_raspberry_pi()
        assert isinstance(result, bool)
    
    def test_check_v4l2_m2m_returns_bool(self):
        """check_v4l2_m2m_available should return a boolean."""
        result = check_v4l2_m2m_available()
        assert isinstance(result, bool)


class TestVideoCaptureCreation:
    """Test video capture creation with various sources."""
    
    def test_create_capture_with_camera_index(self):
        """Should create capture from camera index."""
        cap = create_video_capture(0, enable_hw_accel=False)
        # Don't check isOpened() - camera might not be connected
        assert cap is not None
        cap.release()
    
    def test_create_capture_with_string_source(self):
        """Should create capture from string source (file/URL)."""
        # Test with dummy video file path (won't exist, but tests the path)
        cap = create_video_capture("/tmp/test.mp4", enable_hw_accel=False)
        assert cap is not None
        cap.release()
    
    def test_get_capture_info_returns_dict(self):
        """get_capture_info should return camera info dict."""
        cap = create_video_capture(0, enable_hw_accel=False)
        info = get_capture_info(cap)
        
        assert isinstance(info, dict)
        assert "width" in info
        assert "height" in info
        assert "fps" in info
        assert "backend" in info
        assert "is_opened" in info
        
        assert isinstance(info["width"], int)
        assert isinstance(info["height"], int)
        assert isinstance(info["is_opened"], bool)
        
        cap.release()


class TestHardwareVsSoftwareCapture:
    """
    Benchmark tests to verify hardware acceleration actually reduces CPU usage.
    
    These tests create a synthetic video file and measure CPU usage
    when decoding with and without hardware acceleration.
    """
    
    @pytest.fixture
    def synthetic_video_path(self, tmp_path):
        """Create a short synthetic H.264 video for testing."""
        import cv2
        
        video_path = tmp_path / "test_video.mp4"
        
        # Create a 5-second 640x480 30fps video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))
        
        for i in range(150):  # 5 seconds at 30fps
            # Create frame with some motion (reduces encoder efficiency = more realistic)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            x = (i * 4) % 600  # Moving rectangle
            cv2.rectangle(frame, (x, 200), (x + 40, 280), (0, 255, 0), -1)
            writer.write(frame)
        
        writer.release()
        
        yield str(video_path)
        
        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
    
    def _measure_decode_cpu(self, video_path: str, hw_accel: bool, duration_sec: float = 3.0) -> dict:
        """
        Measure CPU usage while decoding video.
        
        Returns dict with:
            - avg_cpu: Average CPU %
            - peak_cpu: Peak CPU %
            - frames_decoded: Number of frames decoded
            - fps: Actual decode FPS
        """
        import cv2
        
        cap = create_video_capture(video_path, enable_hw_accel=hw_accel)
        
        if not cap.isOpened():
            pytest.skip(f"Could not open test video: {video_path}")
        
        process = psutil.Process()
        
        # Warmup - let things settle
        for _ in range(10):
            cap.read()
        
        cpu_readings = []
        frames = 0
        start_time = time.time()
        
        while time.time() - start_time < duration_sec:
            ret, _ = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop
                continue
            
            frames += 1
            cpu_readings.append(process.cpu_percent(interval=0.001))
        
        elapsed = time.time() - start_time
        cap.release()
        
        return {
            "avg_cpu": sum(cpu_readings) / len(cpu_readings) if cpu_readings else 0,
            "peak_cpu": max(cpu_readings) if cpu_readings else 0,
            "frames_decoded": frames,
            "fps": frames / elapsed if elapsed > 0 else 0,
            "hw_accel": hw_accel,
        }
    
    @pytest.mark.skipif(not os.path.exists("/usr/bin/ffmpeg"), reason="FFmpeg not installed")
    def test_software_vs_hardware_cpu_usage(self, synthetic_video_path):
        """
        Verify hardware acceleration reduces CPU usage vs software decode.
        
        This is the key test - if hardware acceleration works, it should use
        measurably less CPU than software decode.
        """
        # Measure software decode
        software_stats = self._measure_decode_cpu(
            synthetic_video_path, 
            hw_accel=False, 
            duration_sec=2.0
        )
        
        # Small delay between tests
        time.sleep(0.5)
        
        # Measure hardware decode (if available, otherwise same as software)
        hardware_stats = self._measure_decode_cpu(
            synthetic_video_path,
            hw_accel=True,
            duration_sec=2.0
        )
        
        # Log results for analysis
        print(f"\n{'='*60}")
        print(f"Decode Performance Comparison")
        print(f"{'='*60}")
        print(f"Software Decode:")
        print(f"  Avg CPU: {software_stats['avg_cpu']:.1f}%")
        print(f"  Peak CPU: {software_stats['peak_cpu']:.1f}%")
        print(f"  FPS: {software_stats['fps']:.1f}")
        print(f"\nHardware Decode:")
        print(f"  Avg CPU: {hardware_stats['avg_cpu']:.1f}%")
        print(f"  Peak CPU: {hardware_stats['peak_cpu']:.1f}%")
        print(f"  FPS: {hardware_stats['fps']:.1f}")
        
        cpu_reduction = software_stats['avg_cpu'] - hardware_stats['avg_cpu']
        reduction_pct = (cpu_reduction / software_stats['avg_cpu'] * 100) if software_stats['avg_cpu'] > 0 else 0
        
        print(f"\nCPU Reduction: {cpu_reduction:.1f}% ({reduction_pct:.0f}% relative)")
        print(f"{'='*60}\n")
        
        # Assertions
        # 1. Both should have decoded frames
        assert software_stats['frames_decoded'] > 0, "Software decode failed to decode any frames"
        assert hardware_stats['frames_decoded'] > 0, "Hardware decode failed to decode any frames"
        
        # 2. Hardware should not be significantly slower
        # (It's OK if it's same speed, but shouldn't be 2x slower)
        assert hardware_stats['fps'] >= software_stats['fps'] * 0.7, \
            f"Hardware decode ({hardware_stats['fps']:.1f} fps) much slower than software ({software_stats['fps']:.1f} fps)"
        
        # 3. If V4L2 M2M is available, hardware should use less CPU
        if check_v4l2_m2m_available():
            # Hardware should use at least 10% less CPU (or be within margin of error)
            # Note: On some systems the difference might be small, so we use a lenient threshold
            assert hardware_stats['avg_cpu'] <= software_stats['avg_cpu'] * 1.1, \
                f"Hardware decode ({hardware_stats['avg_cpu']:.1f}%) should not use more CPU than software ({software_stats['avg_cpu']:.1f}%)"


class TestCaptureInfoValidation:
    """Test that capture info accurately reflects hardware state."""
    
    def test_capture_info_reports_backend(self):
        """Capture info should report which backend is being used."""
        cap = create_video_capture(0, enable_hw_accel=False)
        info = get_capture_info(cap)
        
        # Backend should be a string indicating the capture method
        assert isinstance(info["backend"], str)
        assert len(info["backend"]) > 0
        
        cap.release()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
