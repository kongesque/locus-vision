#!/usr/bin/env python3
"""
Inference benchmark for LocusVision ONNX models.

Tests all available models in data/models/ and reports FPS, latency,
CPU, and memory usage. Outputs a markdown table for the README.

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/benchmark_inference.py

    # Output just the markdown table:
    python scripts/benchmark_inference.py --markdown
"""

import os
import sys
import time
import argparse
import platform
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
import psutil
import onnxruntime as ort

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
MODELS_DIR = os.path.join(BASE_DIR, "data", "models")

WARMUP_ITERS = 20
BENCH_ITERS = 200

# Models to benchmark, grouped by family
MODEL_LABELS = {
    "yolo11n": "YOLO11n  FP32",
    "yolo11n_half": "YOLO11n  FP16",
    "yolo11n_int8": "YOLO11n  INT8",
    "yolo11s": "YOLO11s  FP32",
    "yolo11s_half": "YOLO11s  FP16",
    "yolo11s_int8": "YOLO11s  INT8",
    "yolo11m": "YOLO11m  FP32",
    "yolo11m_int8": "YOLO11m  INT8",
}


def get_cpu_name() -> str:
    if platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            ).strip()
            if out:
                return out
        except Exception:
            pass
    try:
        import cpuinfo  # type: ignore
        return cpuinfo.get_cpu_info().get("brand_raw", platform.processor())
    except ImportError:
        pass
    return platform.processor() or platform.machine()


def get_ram_gb() -> float:
    return psutil.virtual_memory().total / (1024**3)


def make_test_frame(h: int = 720, w: int = 1280) -> np.ndarray:
    """Synthetic frame that looks realistic enough for letterbox + inference."""
    rng = np.random.default_rng(42)
    frame = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    cv2.rectangle(frame, (100, 100), (400, 500), (0, 200, 0), -1)
    cv2.circle(frame, (800, 360), 120, (200, 0, 200), -1)
    return frame


def letterbox(frame: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Resize + pad to target size (gray letterbox)."""
    img_h, img_w = frame.shape[:2]
    r = min(target_w / img_w, target_h / img_h)
    new_w, new_h = int(img_w * r), int(img_h * r)
    pad_w = (target_w - new_w) // 2
    pad_h = (target_h - new_h) // 2
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
    canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized
    return canvas


def preprocess(frame: np.ndarray, target_h: int = 640, target_w: int = 640) -> np.ndarray:
    lb = letterbox(frame, target_h, target_w)
    blob = lb[:, :, ::-1].astype(np.float32) / 255.0
    return blob.transpose(2, 0, 1)[np.newaxis, ...]


def benchmark_model(model_path: str, frame: np.ndarray) -> dict | None:
    providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    available = ort.get_available_providers()
    use_providers = [p for p in providers if p in available] or ["CPUExecutionProvider"]

    try:
        session = ort.InferenceSession(model_path, providers=use_providers)
    except Exception as e:
        print(f"  ERROR loading model: {e}")
        return None

    input_meta = session.get_inputs()[0]
    input_name = input_meta.name
    shape = input_meta.shape
    target_h = shape[2] if isinstance(shape[2], int) else 640
    target_w = shape[3] if isinstance(shape[3], int) else 640

    blob = preprocess(frame, target_h, target_w)

    # Warmup
    for _ in range(WARMUP_ITERS):
        session.run(None, {input_name: blob})

    proc = psutil.Process()
    cpu_readings: list[float] = []
    mem_readings: list[float] = []
    latencies: list[float] = []

    for _ in range(BENCH_ITERS):
        t0 = time.perf_counter()
        session.run(None, {input_name: blob})
        latencies.append((time.perf_counter() - t0) * 1000)
        cpu_readings.append(proc.cpu_percent(interval=None))
        mem_readings.append(proc.memory_info().rss / 1024 / 1024)

    size_mb = os.path.getsize(model_path) / (1024 * 1024)
    avg_lat = sum(latencies) / len(latencies)
    p99_lat = sorted(latencies)[int(len(latencies) * 0.99)]

    return {
        "size_mb": size_mb,
        "avg_ms": avg_lat,
        "p99_ms": p99_lat,
        "fps": 1000.0 / avg_lat,
        "avg_cpu": sum(cpu_readings) / len(cpu_readings),
        "avg_mem_mb": sum(mem_readings) / len(mem_readings),
        "provider": use_providers[0].replace("ExecutionProvider", ""),
        "input_res": f"{target_w}x{target_h}",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--markdown", action="store_true", help="Print only the markdown table"
    )
    args = parser.parse_args()

    frame = make_test_frame()
    results: list[tuple[str, dict]] = []

    if not args.markdown:
        print("=" * 70)
        print("LocusVision Inference Benchmark")
        print("=" * 70)
        print(f"\nSystem:   {get_cpu_name()}")
        print(f"RAM:      {get_ram_gb():.1f} GB")
        print(f"Platform: {platform.platform()}")
        print(f"Python:   {platform.python_version()}")
        print(f"ORT:      {ort.__version__}")
        print(f"Warmup:   {WARMUP_ITERS} iters | Benchmark: {BENCH_ITERS} iters")
        print(f"Input:    1280x720 synthetic frame\n")

    for model_name, label in MODEL_LABELS.items():
        model_path = os.path.join(MODELS_DIR, f"{model_name}.onnx")
        if not os.path.exists(model_path):
            continue

        if not args.markdown:
            print(f"Benchmarking {label}...")

        r = benchmark_model(model_path, frame)
        if r:
            results.append((label, r))
            if not args.markdown:
                print(
                    f"  {r['fps']:5.1f} FPS  |  {r['avg_ms']:5.1f} ms avg  "
                    f"|  p99 {r['p99_ms']:5.1f} ms  |  {r['size_mb']:.1f} MB  "
                    f"|  CPU {r['avg_cpu']:.0f}%  |  {r['provider']}"
                )

    if not results:
        print("No models found. Run: python scripts/export_model.py yolo11n")
        return 1

    # Markdown table
    if not args.markdown:
        print("\n" + "=" * 70)
        print("MARKDOWN TABLE (copy into README)")
        print("=" * 70 + "\n")

    header = (
        "| Model | Size | FPS | Latency (avg) | Latency (p99) | CPU | Provider |\n"
        "|-------|------|-----|---------------|---------------|-----|----------|\n"
    )
    rows = ""
    for label, r in results:
        rows += (
            f"| {label} | {r['size_mb']:.0f} MB | **{r['fps']:.0f}** | "
            f"{r['avg_ms']:.1f} ms | {r['p99_ms']:.1f} ms | "
            f"~{r['avg_cpu']:.0f}% | {r['provider']} |\n"
        )

    print(header + rows)

    note = (
        f"> Benchmarked on {get_cpu_name()} ({get_ram_gb():.0f} GB RAM), "
        f"ONNX Runtime {ort.__version__}. "
        f"Input: 1280×720 synthetic frame → 640×640 letterboxed. "
        f"{BENCH_ITERS} iterations after {WARMUP_ITERS}-iteration warmup."
    )
    print(note)

    return 0


if __name__ == "__main__":
    sys.exit(main())
