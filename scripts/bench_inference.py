#!/usr/bin/env python3
"""
LocusVision Inference Benchmark
Measures real AI/CV performance metrics for edge deployment evaluation.

When run on non-Pi hardware, applies scaling factors to project Pi 5 performance.
Outputs JSON to stdout for integration with benchmark.sh.

Usage: python scripts/bench_inference.py [--frames N] [--warmup N] [--model NAME]
"""

import sys
import os
import json
import time
import argparse
import platform
import traceback

# Ensure backend imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np


# ── Pi 5 Projection Scaling Factors ─────────────────────────────
# Based on published benchmarks:
#   - YOLO11n FP32 ONNX on Pi 5 Cortex-A76: ~77-100ms/frame (10-13 FPS)
#   - YOLO11n FP32 ONNX on Apple M-series w/ CoreML: ~6-7ms/frame (150 FPS)
#   - Ratio: ~12-15× slower on Pi 5
#
# Conservative factors (Pi 5 value = measured × factor):
PI5_LATENCY_FACTOR = 12.0    # Inference is ~12× slower on Pi 5 CPU vs Apple M w/ CoreML
PI5_MEMORY_FACTOR = 0.55     # Pi 5 uses slightly less memory (smaller caches, no CoreML)
PI5_MODEL_LOAD_FACTOR = 3.0  # SD card I/O + slower CPU init


def is_raspberry_pi():
    """Detect if running on Raspberry Pi hardware."""
    try:
        with open("/proc/device-tree/model", "r") as f:
            model = f.read().lower()
            return "raspberry pi" in model
    except (FileNotFoundError, PermissionError):
        pass
    # Also check via platform
    machine = platform.machine().lower()
    return machine in ("aarch64", "armv7l") and os.path.exists("/proc/device-tree")


def get_hardware_info():
    """Get hardware identifier for scaling decisions."""
    machine = platform.machine()
    system = platform.system()

    if is_raspberry_pi():
        return "pi", "Raspberry Pi"

    if system == "Darwin" and machine == "arm64":
        # Apple Silicon
        try:
            import subprocess
            chip = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            return "apple_silicon", chip
        except Exception:
            return "apple_silicon", "Apple Silicon"

    if system == "Darwin":
        return "mac_intel", f"Intel Mac ({machine})"

    if system == "Linux" and machine == "x86_64":
        return "linux_x86", f"Linux x86_64"

    return "unknown", f"{system} {machine}"


def get_rss_mb():
    """Get current process RSS in MB (cross-platform)."""
    try:
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return rss / (1024 * 1024)  # bytes → MB
        return rss / 1024  # KB → MB
    except Exception:
        return 0


def percentile(sorted_list, p):
    """Compute p-th percentile from a sorted list."""
    if not sorted_list:
        return 0
    k = (len(sorted_list) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_list) else f
    d = k - f
    return sorted_list[f] + d * (sorted_list[c] - sorted_list[f])


def make_latency_stats(latencies):
    """Compute stats dict from a list of latency measurements (ms)."""
    latencies.sort()
    avg = sum(latencies) / len(latencies)
    return {
        "avg_ms": round(avg, 2),
        "p50_ms": round(percentile(latencies, 50), 2),
        "p95_ms": round(percentile(latencies, 95), 2),
        "p99_ms": round(percentile(latencies, 99), 2),
        "min_ms": round(latencies[0], 2),
        "max_ms": round(latencies[-1], 2),
        "fps": round(1000 / avg, 1) if avg > 0 else 0,
    }


def project_to_pi5(stats, latency_factor):
    """Apply Pi 5 scaling to a latency stats dict."""
    projected_avg = stats["avg_ms"] * latency_factor
    return {
        "avg_ms": round(projected_avg, 2),
        "p50_ms": round(stats["p50_ms"] * latency_factor, 2),
        "p95_ms": round(stats["p95_ms"] * latency_factor, 2),
        "p99_ms": round(stats["p99_ms"] * latency_factor, 2),
        "min_ms": round(stats["min_ms"] * latency_factor, 2),
        "max_ms": round(stats["max_ms"] * latency_factor, 2),
        "fps": round(1000 / projected_avg, 1) if projected_avg > 0 else 0,
    }


def run_benchmark(model_name="yolo11n", num_frames=100, num_warmup=10):
    """Run the full inference benchmark suite."""
    hw_type, hw_name = get_hardware_info()
    on_pi = hw_type == "pi"
    needs_projection = not on_pi

    results = {
        "success": False,
        "error": None,
        "model_name": model_name,
        "num_frames": num_frames,
        "num_warmup": num_warmup,
        "hardware": hw_name,
        "hardware_type": hw_type,
        "is_projected": needs_projection,
    }

    if needs_projection:
        results["projection_note"] = (
            f"Measured on {hw_name}. Pi 5 values projected using "
            f"{PI5_LATENCY_FACTOR}x latency / {PI5_MEMORY_FACTOR}x memory scaling."
        )

    # ── 1. Measure model load time ──────────────────────────────
    rss_before = get_rss_mb()

    try:
        from services.onnx_detector import _detector_cache, get_detector
        _detector_cache.clear()
    except ImportError as e:
        results["error"] = f"Cannot import backend: {e}"
        return results

    # Suppress stdout prints during model load
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    t0 = time.monotonic()
    try:
        detector = get_detector(model_name)
    except FileNotFoundError as e:
        sys.stdout = old_stdout
        results["error"] = str(e)
        return results
    t1 = time.monotonic()
    sys.stdout = old_stdout

    raw_load_ms = round((t1 - t0) * 1000, 1)
    results["model_load_ms_measured"] = raw_load_ms
    results["model_load_ms"] = round(raw_load_ms * PI5_MODEL_LOAD_FACTOR, 1) if needs_projection else raw_load_ms

    rss_after_load = get_rss_mb()
    results["model_memory_mb"] = round((rss_after_load - rss_before) * (PI5_MEMORY_FACTOR if needs_projection else 1), 1)

    # ── 2. Generate synthetic test frames ───────────────────────
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # ── 3. Warm-up (discard results) ────────────────────────────
    for _ in range(num_warmup):
        detector.track(frame)
    detector.reset_tracker()

    # ── 4. Detection-only benchmark ─────────────────────────────
    detect_latencies = []
    for _ in range(num_frames):
        t_start = time.monotonic()
        detector.detect(frame)
        t_end = time.monotonic()
        detect_latencies.append((t_end - t_start) * 1000)

    raw_detect = make_latency_stats(detect_latencies)
    results["detect_measured"] = raw_detect
    results["detect"] = project_to_pi5(raw_detect, PI5_LATENCY_FACTOR) if needs_projection else raw_detect

    # ── 5. Detection + Tracking benchmark ───────────────────────
    detector.reset_tracker()
    track_latencies = []
    for _ in range(num_frames):
        t_start = time.monotonic()
        detector.track(frame)
        t_end = time.monotonic()
        track_latencies.append((t_end - t_start) * 1000)

    raw_track = make_latency_stats(track_latencies)
    results["track_measured"] = raw_track
    results["track"] = project_to_pi5(raw_track, PI5_LATENCY_FACTOR) if needs_projection else raw_track

    # ── 6. Full analytics pipeline benchmark ────────────────────
    try:
        from services.analytics_engine import AnalyticsEngine

        zones = [{
            "id": "bench-zone",
            "type": "polygon",
            "points": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.9, "y": 0.1},
                {"x": 0.9, "y": 0.9},
                {"x": 0.1, "y": 0.9},
            ],
            "color": "#00ff00",
            "classes": [],
        }]
        engine = AnalyticsEngine(model_name=model_name, zones=zones)

        for _ in range(num_warmup):
            engine.process_frame(frame)
        engine.reset()

        pipeline_latencies = []
        for _ in range(num_frames):
            t_start = time.monotonic()
            engine.process_frame(frame)
            t_end = time.monotonic()
            pipeline_latencies.append((t_end - t_start) * 1000)

        raw_pipeline = make_latency_stats(pipeline_latencies)
        results["pipeline_measured"] = raw_pipeline
        results["pipeline"] = project_to_pi5(raw_pipeline, PI5_LATENCY_FACTOR) if needs_projection else raw_pipeline
    except Exception as e:
        results["pipeline"] = {"error": str(e)}

    # ── 7. Peak memory ──────────────────────────────────────────
    rss_peak = get_rss_mb()
    results["peak_rss_mb_measured"] = round(rss_peak, 1)
    results["peak_rss_mb"] = round(rss_peak * (PI5_MEMORY_FACTOR if needs_projection else 1), 1)

    # ── 8. ONNX model file size ─────────────────────────────────
    model_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "data", "models", f"{model_name}.onnx"
    )
    if os.path.exists(model_path):
        results["model_size_mb"] = round(os.path.getsize(model_path) / (1024 * 1024), 1)

    results["success"] = True
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LocusVision Inference Benchmark")
    parser.add_argument("--frames", type=int, default=100, help="Number of frames to benchmark (default: 100)")
    parser.add_argument("--warmup", type=int, default=10, help="Number of warm-up frames (default: 10)")
    parser.add_argument("--model", type=str, default="yolo11n", help="Model name (default: yolo11n)")
    args = parser.parse_args()

    try:
        results = run_benchmark(
            model_name=args.model,
            num_frames=args.frames,
            num_warmup=args.warmup,
        )
    except Exception as e:
        results = {"success": False, "error": traceback.format_exc()}

    print(json.dumps(results))
