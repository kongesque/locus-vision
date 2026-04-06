#!/usr/bin/env python3
"""
Inference benchmark for LocusVision ONNX models.

Tests all available models in data/models/ and reports FPS and latency.
Outputs a markdown table for the README.

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
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
import onnxruntime as ort

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
MODELS_DIR = os.path.join(BASE_DIR, "data", "models")

WARMUP_SECS = 3.0    # time-based warmup so CoreML JIT fully compiles
BENCH_SECS = 15.0    # minimum benchmark duration per model
COOLDOWN_SECS = 2.0  # pause between models to let thermals settle

MODEL_LABELS = {
    "yolo11n": ("YOLO11n", "FP32"),
    "yolo11n_half": ("YOLO11n", "FP16"),
    "yolo11n_int8": ("YOLO11n", "INT8"),
    "yolo11s": ("YOLO11s", "FP32"),
    "yolo11s_half": ("YOLO11s", "FP16"),
    "yolo11s_int8": ("YOLO11s", "INT8"),
    "yolo11m": ("YOLO11m", "FP32"),
    "yolo11m_int8": ("YOLO11m", "INT8"),
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
    import psutil
    return psutil.virtual_memory().total / (1024**3)


def make_test_frame(h: int = 720, w: int = 1280) -> np.ndarray:
    """Synthetic frame with realistic structure for letterbox + inference."""
    rng = np.random.default_rng(42)
    frame = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    cv2.rectangle(frame, (100, 100), (400, 500), (0, 200, 0), -1)
    cv2.circle(frame, (800, 360), 120, (200, 0, 200), -1)
    cv2.rectangle(frame, (900, 50), (1100, 300), (0, 100, 255), -1)
    return frame


def preprocess(frame: np.ndarray, target_h: int = 640, target_w: int = 640) -> np.ndarray:
    img_h, img_w = frame.shape[:2]
    r = min(target_w / img_w, target_h / img_h)
    new_w, new_h = int(img_w * r), int(img_h * r)
    pad_w = (target_w - new_w) // 2
    pad_h = (target_h - new_h) // 2
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
    canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized
    blob = canvas[:, :, ::-1].astype(np.float32) / 255.0
    return blob.transpose(2, 0, 1)[np.newaxis, ...]


def benchmark_model(model_path: str, frame: np.ndarray, verbose: bool = True) -> dict | None:
    providers = ["CUDAExecutionProvider", "CoreMLExecutionProvider", "CPUExecutionProvider"]
    available = ort.get_available_providers()
    use_providers = [p for p in providers if p in available] or ["CPUExecutionProvider"]

    try:
        session = ort.InferenceSession(model_path, providers=use_providers)
    except Exception as e:
        print(f"  ERROR loading: {e}")
        return None

    input_meta = session.get_inputs()[0]
    input_name = input_meta.name
    shape = input_meta.shape
    target_h = shape[2] if isinstance(shape[2], int) else 640
    target_w = shape[3] if isinstance(shape[3], int) else 640
    blob = preprocess(frame, target_h, target_w)

    # Time-based warmup — lets CoreML finish JIT compilation
    if verbose:
        print(f"  Warming up ({WARMUP_SECS:.0f}s)...", end=" ", flush=True)
    warmup_end = time.perf_counter() + WARMUP_SECS
    while time.perf_counter() < warmup_end:
        session.run(None, {input_name: blob})
    if verbose:
        print("done")

    # Timed benchmark run
    if verbose:
        print(f"  Benchmarking ({BENCH_SECS:.0f}s)...", end=" ", flush=True)
    latencies: list[float] = []
    bench_end = time.perf_counter() + BENCH_SECS
    while time.perf_counter() < bench_end:
        t0 = time.perf_counter()
        session.run(None, {input_name: blob})
        latencies.append((time.perf_counter() - t0) * 1000)
    if verbose:
        print(f"done ({len(latencies)} iters)")

    latencies.sort()
    avg_ms = statistics.mean(latencies)
    median_ms = statistics.median(latencies)
    p99_ms = latencies[int(len(latencies) * 0.99)]
    size_mb = os.path.getsize(model_path) / (1024 * 1024)

    return {
        "size_mb": size_mb,
        "iters": len(latencies),
        "avg_ms": avg_ms,
        "median_ms": median_ms,
        "p99_ms": p99_ms,
        "fps": 1000.0 / median_ms,
        "provider": use_providers[0].replace("ExecutionProvider", ""),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", action="store_true", help="Print only the markdown table")
    args = parser.parse_args()

    frame = make_test_frame()
    results: list[tuple[str, str, dict]] = []
    cpu_name = get_cpu_name()

    if not args.markdown:
        print("=" * 70)
        print("LocusVision Inference Benchmark")
        print("=" * 70)
        print(f"\nSystem:   {cpu_name}")
        print(f"RAM:      {get_ram_gb():.1f} GB")
        print(f"Platform: {platform.platform()}")
        print(f"Python:   {platform.python_version()}")
        print(f"ORT:      {ort.__version__}")
        print(f"Warmup:   {WARMUP_SECS:.0f}s time-based | Benchmark: {BENCH_SECS:.0f}s per model")
        print(f"Cooldown: {COOLDOWN_SECS:.0f}s between models")
        print(f"Input:    1280×720 synthetic frame → 640×640 letterboxed\n")

    first = True
    for model_name, (family, precision) in MODEL_LABELS.items():
        model_path = os.path.join(MODELS_DIR, f"{model_name}.onnx")
        if not os.path.exists(model_path):
            continue

        if not first and not args.markdown:
            print(f"  Cooling down ({COOLDOWN_SECS:.0f}s)...")
            time.sleep(COOLDOWN_SECS)
        first = False

        if not args.markdown:
            print(f"{family} {precision} ({os.path.getsize(model_path) / 1024 / 1024:.1f} MB)")

        r = benchmark_model(model_path, frame, verbose=not args.markdown)
        if not r:
            continue

        results.append((family, precision, r))

        if not args.markdown:
            print(
                f"  → {r['fps']:.1f} FPS  |  median {r['median_ms']:.1f} ms  "
                f"|  avg {r['avg_ms']:.1f} ms  |  p99 {r['p99_ms']:.1f} ms  "
                f"|  {r['provider']}\n"
            )

    if not results:
        print("No models found. Run: python scripts/export_model.py yolo11n")
        return 1

    # Markdown table
    if not args.markdown:
        print("=" * 70)
        print("MARKDOWN TABLE")
        print("=" * 70 + "\n")

    header = (
        "| Model | Precision | Size | FPS | Latency (median) | Latency (p99) | Provider |\n"
        "|-------|-----------|------|-----|-----------------|---------------|----------|\n"
    )
    rows = ""
    for family, precision, r in results:
        rows += (
            f"| {family} | {precision} | {r['size_mb']:.0f} MB | **{r['fps']:.0f}** | "
            f"{r['median_ms']:.1f} ms | {r['p99_ms']:.1f} ms | {r['provider']} |\n"
        )

    print(header + rows)

    note = (
        f"> Benchmarked on {cpu_name} ({get_ram_gb():.0f} GB RAM), "
        f"ONNX Runtime {ort.__version__}. "
        f"Input: 1280×720 → 640×640 letterboxed. "
        f"{BENCH_SECS:.0f}s timed run after {WARMUP_SECS:.0f}s warmup per model, "
        f"{COOLDOWN_SECS:.0f}s cooldown between models. FPS derived from median latency."
    )
    print(note)

    return 0


if __name__ == "__main__":
    sys.exit(main())
