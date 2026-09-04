"""
Video capture utility — Frigate-style FFmpeg subprocess for RTSP streams,
OpenCV VideoCapture for local cameras and files.

RTSP streams are decoded by an ffmpeg child process. A dedicated reader thread
drains stdout continuously and keeps only the latest frame, so ffmpeg never
stalls and the RTSP server never sees a slow reader.
"""

import cv2
import numpy as np
import shutil
import subprocess
import threading
from typing import Optional


def is_raspberry_pi() -> bool:
    """Check if running on Raspberry Pi."""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            content = f.read()
            return 'BCM2711' in content or 'BCM2712' in content
    except Exception:
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
        return 'bcm2835' in output or 'bcm2836' in output or 'codec' in output
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


class FFmpegCapture:
    """
    Frigate-style RTSP capture: spawns ffmpeg to decode the stream and pipes
    raw BGR24 frames via stdout. A background thread continuously reads frames
    and keeps only the latest one, so ffmpeg is never blocked by slow consumers.
    """

    def __init__(self, source: str, width: int = 0, height: int = 0):
        self._source = source
        self._process: Optional[subprocess.Popen] = None
        self._width = width
        self._height = height
        self._opened = False

        # Latest-frame buffer (reader thread writes, .read() reads)
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._frame_ready = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None

        self._start(source)

    def _start(self, source: str):
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            print("[FFmpegCapture] ffmpeg not found in PATH")
            return

        if self._width == 0 or self._height == 0:
            self._width, self._height = self._probe(source)
            if self._width == 0:
                print(f"[FFmpegCapture] Failed to probe resolution for {source}")
                return

        input_args = ["-rtsp_transport", "tcp"] if source.startswith("rtsp://") else []

        cmd = [
            ffmpeg_bin,
            *input_args,
            "-i", source,
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-an",
            "-sn",
            "-v", "error",
            "pipe:1",
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=self._width * self._height * 3 * 4,
            )
            self._opened = True
            print(f"[FFmpegCapture] Started: {self._width}x{self._height} from {source}")

            # Start the background reader thread that drains ffmpeg stdout
            self._reader_thread = threading.Thread(
                target=self._reader_loop, daemon=True
            )
            self._reader_thread.start()
        except Exception as e:
            print(f"[FFmpegCapture] Failed to start ffmpeg: {e}")
            self._opened = False

    def _reader_loop(self):
        """Continuously read frames from ffmpeg stdout, keeping only the latest."""
        frame_size = self._width * self._height * 3
        while self._opened and self._process and self._process.poll() is None:
            try:
                raw = self._process.stdout.read(frame_size)
                if len(raw) != frame_size:
                    break
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                    (self._height, self._width, 3)
                ).copy()
                with self._frame_lock:
                    self._latest_frame = frame
                self._frame_ready.set()
            except Exception:
                break
        self._opened = False
        self._frame_ready.set()  # Unblock any waiting .read()

    def _probe(self, source: str) -> tuple[int, int]:
        """Use ffprobe to get stream resolution."""
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            return 0, 0
        try:
            input_args = ["-rtsp_transport", "tcp"] if source.startswith("rtsp://") else []
            result = subprocess.run(
                [
                    ffprobe_bin,
                    *input_args,
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "csv=p=0:s=x",
                    source,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            parts = result.stdout.strip().split("x")
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        except Exception as e:
            print(f"[FFmpegCapture] Probe failed: {e}")
        return 0, 0

    def isOpened(self) -> bool:
        return self._opened and self._process is not None and self._process.poll() is None

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        """Return the latest decoded frame. Blocks briefly if no frame yet."""
        if not self._frame_ready.wait(timeout=5):
            return False, None
        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None
        self._frame_ready.clear()
        if frame is None:
            return False, None
        return True, frame

    def get(self, prop_id: int):
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self._width)
        if prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(self._height)
        if prop_id == cv2.CAP_PROP_FPS:
            return 0.0
        return 0.0

    def set(self, prop_id: int, value) -> bool:
        return False

    def getBackendName(self) -> str:
        return "ffmpeg-pipe"

    def release(self):
        self._opened = False
        if self._process:
            try:
                self._process.stdout.close()
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        if self._reader_thread:
            self._reader_thread.join(timeout=2)
            self._reader_thread = None


def create_video_capture(
    source: str | int,
    enable_hw_accel: bool = True
):
    """
    Create a video capture.

    RTSP/HTTP streams use FFmpegCapture (subprocess pipe — no frame loss).
    Local cameras and files use OpenCV VideoCapture.
    """
    if not isinstance(source, str):
        return cv2.VideoCapture(int(source))

    if (source.startswith('rtsp://') or
            source.startswith('http://') or
            source.startswith('https://')):
        return FFmpegCapture(source)

    return cv2.VideoCapture(source)


def get_capture_info(cap) -> dict:
    """Get information about the video capture."""
    try:
        backend = cap.getBackendName()
    except (AttributeError, cv2.error):
        # OpenCV raises when a local camera cannot be opened (common on
        # headless systems). Capture diagnostics should still be safe to call.
        backend = "unavailable"

    return {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "backend": backend,
        "is_opened": cap.isOpened(),
    }
