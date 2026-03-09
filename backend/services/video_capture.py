"""Hardware-accelerated video capture utility for Raspberry Pi 5 and other platforms."""

import cv2
import platform
import subprocess
from typing import Optional


def is_raspberry_pi() -> bool:
    """Check if running on Raspberry Pi."""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            return 'BCM2711' in f.read() or 'BCM2712' in f.read()
    except:
        return False


def check_v4l2_m2m_available() -> bool:
    """Check if V4L2 M2M hardware decoder is available."""
    try:
        result = subprocess.run(
            ['v4l2-ctl', '--list-devices'],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout.lower()
        # Look for bcm2835 codec (Pi 4) or bcm2836 codec (Pi 5)
        return 'bcm2835' in output or 'bcm2836' in output or 'codec' in output
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def create_video_capture(
    source: str | int,
    enable_hw_accel: bool = True
) -> cv2.VideoCapture:
    """
    Create a VideoCapture with optional hardware acceleration.
    
    Args:
        source: Video source (camera index int, file path, or URL)
        enable_hw_accel: Whether to try hardware acceleration
        
    Returns:
        OpenCV VideoCapture object
    """
    # For non-string sources (camera indices), use default
    if not isinstance(source, str):
        return cv2.VideoCapture(int(source))
    
    # For file paths (not URLs), use default
    if not (source.startswith('rtsp://') or 
            source.startswith('http://') or 
            source.startswith('https://')):
        return cv2.VideoCapture(source)
    
    if not enable_hw_accel:
        return cv2.VideoCapture(source)
    
    # Try hardware acceleration for network streams
    # V4L2 M2M is available on Raspberry Pi for H.264/H.265 decode
    if is_raspberry_pi() and check_v4l2_m2m_available():
        # Use FFmpeg with V4L2 M2M hardware acceleration
        cap = cv2.VideoCapture(
            source,
            cv2.CAP_FFMPEG,
            [
                cv2.CAP_PROP_HW_ACCELERATION,
                cv2.VIDEO_ACCELERATION_V4L2_M2M
            ]
        )
        if cap.isOpened():
            print(f"[VideoCapture] Hardware acceleration (V4L2 M2M) enabled for {source}")
            return cap
        cap.release()
        print(f"[VideoCapture] Hardware acceleration failed, falling back to software decode")
    
    # Try generic hardware acceleration (Intel QuickSync, NVIDIA NVDEC, etc.)
    cap = cv2.VideoCapture(
        source,
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_HW_ACCELERATION,
            cv2.VIDEO_ACCELERATION_ANY
        ]
    )
    if cap.isOpened():
        print(f"[VideoCapture] Hardware acceleration enabled for {source}")
        return cap
    
    cap.release()
    
    # Fallback to software decoding
    print(f"[VideoCapture] Using software decode for {source}")
    return cv2.VideoCapture(source)


def get_capture_info(cap: cv2.VideoCapture) -> dict:
    """Get information about the video capture."""
    return {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "backend": cap.getBackendName(),
        "is_opened": cap.isOpened(),
    }
