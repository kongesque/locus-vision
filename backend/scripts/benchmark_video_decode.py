#!/usr/bin/env python3
"""
Benchmark script to verify hardware video decode acceleration.

This script:
1. Creates a test video file
2. Measures CPU usage with software decode
3. Measures CPU usage with hardware decode (if available)
4. Reports actual CPU reduction

Usage:
    cd backend
    python scripts/benchmark_video_decode.py

Output:
    Reports whether hardware acceleration is actually reducing CPU usage.
"""

import os
import sys
import time
import tempfile
import argparse

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
import psutil
from services.video_capture import (
    create_video_capture,
    get_capture_info,
    is_raspberry_pi,
    check_v4l2_m2m_available,
)


def create_test_video(path: str, duration_sec: int = 5, fps: int = 30) -> bool:
    """Create a test H.264 video file."""
    print(f"Creating {duration_sec}s test video...")
    
    fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec
    writer = cv2.VideoWriter(path, fourcc, float(fps), (1280, 720))
    
    if not writer.isOpened():
        # Try alternative codec
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), float(fps), (1280, 720))
    
    if not writer.isOpened():
        print("ERROR: Could not create video writer")
        return False
    
    frame_count = duration_sec * fps
    for i in range(frame_count):
        # Create frame with motion (harder to compress = more realistic)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        
        # Moving gradient background
        for y in range(720):
            frame[y, :] = [(y + i * 2) % 255, (y + i) % 255, (y // 2) % 255]
        
        # Moving objects
        x = (i * 8) % 1200
        cv2.circle(frame, (x + 40, 360), 50, (0, 255, 255), -1)
        cv2.rectangle(frame, (x, 200), (x + 80, 520), (255, 0, 0), 3)
        
        # Text overlay (reduces compression efficiency)
        cv2.putText(frame, f"Frame {i}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        writer.write(frame)
    
    writer.release()
    file_size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"  Created: {path} ({file_size_mb:.1f} MB)")
    return True


def measure_decode_performance(video_path: str, hw_accel: bool, duration_sec: float = 5.0) -> dict:
    """Measure CPU and performance metrics while decoding video."""
    label = "Hardware" if hw_accel else "Software"
    print(f"\nTesting {label} decode...")
    
    cap = create_video_capture(video_path, enable_hw_accel=hw_accel)
    
    if not cap.isOpened():
        print(f"  ERROR: Could not open video")
        return None
    
    info = get_capture_info(cap)
    print(f"  Backend: {info['backend']}")
    print(f"  Resolution: {info['width']}x{info['height']}")
    print(f"  FPS: {info['fps']:.1f}")
    
    process = psutil.Process()
    
    # Warmup
    print("  Warming up...")
    for _ in range(30):
        ret, _ = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    # Measure
    cpu_readings = []
    mem_readings = []
    frames = 0
    start_time = time.time()
    
    print(f"  Measuring for {duration_sec}s...")
    while time.time() - start_time < duration_sec:
        loop_start = time.time()
        
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        frames += 1
        
        # Force frame processing (simulate real workload)
        _ = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Record metrics
        cpu_readings.append(process.cpu_percent(interval=None))
        mem_readings.append(process.memory_info().rss / 1024 / 1024)  # MB
        
        # Small sleep to not dominate CPU with benchmark overhead
        elapsed = time.time() - loop_start
        if elapsed < 0.001:
            time.sleep(0.001 - elapsed)
    
    actual_duration = time.time() - start_time
    cap.release()
    
    return {
        "mode": label,
        "hw_accel": hw_accel,
        "frames": frames,
        "duration": actual_duration,
        "fps": frames / actual_duration,
        "avg_cpu": sum(cpu_readings) / len(cpu_readings),
        "peak_cpu": max(cpu_readings),
        "min_cpu": min(cpu_readings),
        "avg_mem_mb": sum(mem_readings) / len(mem_readings),
        "backend": info['backend'],
    }


def print_comparison(software: dict, hardware: dict):
    """Print comparison table."""
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    
    # Header
    print(f"{'Metric':<25} {'Software':>15} {'Hardware':>15} {'Change':>12}")
    print("-" * 70)
    
    # Rows
    metrics = [
        ("Frames Decoded", "frames", "%.0f", ""),
        ("Duration (s)", "duration", "%.2f", ""),
        ("Decode FPS", "fps", "%.1f", "fps"),
        ("Avg CPU (%)", "avg_cpu", "%.1f", "%"),
        ("Peak CPU (%)", "peak_cpu", "%.1f", "%"),
        ("Min CPU (%)", "min_cpu", "%.1f", "%"),
        ("Avg Memory (MB)", "avg_mem_mb", "%.1f", "MB"),
    ]
    
    for label, key, fmt, unit in metrics:
        s_val = software[key]
        h_val = hardware[key]
        
        s_str = fmt % s_val
        h_str = fmt % h_val
        
        if key in ["avg_cpu", "peak_cpu"]:
            change = s_val - h_val
            change_str = f"{change:+.1f}%"
            if change > 0:
                change_str += " ✅"
            elif change < -5:
                change_str += " ⚠️"
        elif key == "fps":
            change = ((h_val - s_val) / s_val) * 100 if s_val > 0 else 0
            change_str = f"{change:+.1f}%"
        else:
            change_str = "-"
        
        print(f"{label:<25} {s_str:>15} {h_str:>15} {change_str:>12}")
    
    # Backend info
    print("-" * 70)
    print(f"{'Backend':<25} {software['backend']:>15} {hardware['backend']:>15}")
    print("=" * 70)
    
    # Summary
    cpu_reduction = software['avg_cpu'] - hardware['avg_cpu']
    if cpu_reduction > 5:
        print(f"\n✅ SUCCESS: Hardware decode saves {cpu_reduction:.1f}% CPU")
        print(f"   You can handle ~{(software['avg_cpu'] / hardware['avg_cpu'] - 1) * 100:.0f}% more streams")
    elif cpu_reduction > -2:
        print(f"\n⚠️  NEUTRAL: Minimal difference ({cpu_reduction:+.1f}%)")
        if not check_v4l2_m2m_available():
            print("   V4L2 M2M not available - hardware acceleration not working")
        else:
            print("   Video may not be H.264 or FFmpeg not built with hardware support")
    else:
        print(f"\n❌ ISSUE: Hardware decode uses {abs(cpu_reduction):.1f}% MORE CPU")
        print("   This shouldn't happen - check FFmpeg and driver configuration")
    
    # Check for pseudo-reduction (fake improvement)
    fps_ratio = hardware['fps'] / software['fps'] if software['fps'] > 0 else 0
    if hardware['avg_cpu'] < software['avg_cpu'] * 0.8 and fps_ratio < 0.8:
        print(f"\n⚠️  WARNING: Possible 'pseudo-reduction'")
        print("   CPU is lower but FPS is also significantly lower.")
        print("   Hardware decode may be falling back silently.")


def main():
    parser = argparse.ArgumentParser(description="Benchmark video decode performance")
    parser.add_argument("--duration", type=float, default=5.0, help="Benchmark duration per test (seconds)")
    parser.add_argument("--video", type=str, help="Use existing video file instead of creating one")
    args = parser.parse_args()
    
    print("=" * 70)
    print("Video Decode Hardware Acceleration Benchmark")
    print("=" * 70)
    
    # System info
    print("\nSystem Information:")
    print(f"  Platform: {'Raspberry Pi' if is_raspberry_pi() else 'Other'}")
    print(f"  V4L2 M2M Available: {check_v4l2_m2m_available()}")
    print(f"  FFmpeg: {'Found' if os.path.exists('/usr/bin/ffmpeg') else 'Not found'}")
    print(f"  OpenCV Version: {cv2.__version__}")
    
    # Create or use video
    if args.video:
        video_path = args.video
        if not os.path.exists(video_path):
            print(f"ERROR: Video not found: {video_path}")
            return 1
    else:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            video_path = f.name
        
        if not create_test_video(video_path, duration_sec=5):
            return 1
    
    try:
        # Run benchmarks
        print("\n" + "=" * 70)
        print("Running Benchmarks")
        print("=" * 70)
        
        software = measure_decode_performance(video_path, hw_accel=False, duration_sec=args.duration)
        if not software:
            return 1
        
        time.sleep(1)  # Cooldown
        
        hardware = measure_decode_performance(video_path, hw_accel=True, duration_sec=args.duration)
        if not hardware:
            return 1
        
        # Print results
        print_comparison(software, hardware)
        
        # Exit code based on result
        cpu_reduction = software['avg_cpu'] - hardware['avg_cpu']
        return 0 if cpu_reduction > -5 else 1
        
    finally:
        # Cleanup
        if not args.video and os.path.exists(video_path):
            os.remove(video_path)
            print(f"\nCleaned up: {video_path}")


if __name__ == "__main__":
    sys.exit(main())
