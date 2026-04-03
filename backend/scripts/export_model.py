#!/usr/bin/env python3
"""
One-time model exporter: converts YOLO .pt → .onnx

Usage:
    python scripts/export_model.py yolo11n
    python scripts/export_model.py yolov8n

Requires `ultralytics` to be installed (only needed on your dev machine,
NOT on the Raspberry Pi at runtime).

The exported .onnx file will be saved to data/models/<model_name>.onnx
"""

import sys
import os
import shutil
import argparse

def main():
    parser = argparse.ArgumentParser(description="One-time model exporter: converts YOLO .pt → .onnx")
    parser.add_argument("model_name", help="Name of the model (e.g., yolo11n)")
    parser.add_argument("--half", action="store_true", help="Export to FP16 half-precision ONNX")
    parser.add_argument("--int8", action="store_true", help="Export to INT8 quantized ONNX")
    args = parser.parse_args()

    model_name = args.model_name
    half_precision = args.half
    int8_precision = args.int8

    try:
        from ultralytics import YOLO
    except ImportError:
        print("ERROR: 'ultralytics' is required for model export.")
        print("Install it on your dev machine: pip install ultralytics")
        sys.exit(1)

    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "models")
    os.makedirs(models_dir, exist_ok=True)

    pt_path = os.path.join(models_dir, f"{model_name}.pt")

    # Load model (downloads if not found)
    if os.path.exists(pt_path):
        print(f"Loading model from {pt_path}")
        model = YOLO(pt_path)
    else:
        print(f"Model not found at {pt_path}, downloading {model_name}.pt ...")
        model = YOLO(f"{model_name}.pt")
        # Move the downloaded file to models dir
        downloaded = f"{model_name}.pt"
        if os.path.exists(downloaded):
            shutil.move(downloaded, pt_path)
            model = YOLO(pt_path)

    # Export to ONNX
    print(f"Exporting {model_name} to ONNX format (half={half_precision}, int8={int8_precision}) ...")
    
    export_kwargs = {"format": "onnx", "imgsz": 640, "simplify": True}
    if half_precision:
        export_kwargs["half"] = True
        
    export_path = model.export(**export_kwargs)
    
    # Define suffixes and paths
    suffix = ""
    if int8_precision:
        suffix = "_int8"
    elif half_precision:
        suffix = "_half"
        
    target_path = os.path.join(models_dir, f"{model_name}{suffix}.onnx")
    
    if int8_precision and export_path and os.path.exists(export_path):
        import onnx
        from onnxruntime.quantization import (
            quantize_static,
            CalibrationDataReader,
            QuantFormat,
            QuantType,
        )

        class _CalibReader(CalibrationDataReader):
            def __init__(self, model_path: str, n_samples: int = 50):
                import numpy as np
                from onnxruntime import InferenceSession
                sess = InferenceSession(model_path, providers=["CPUExecutionProvider"])
                inp = sess.get_inputs()[0]
                self._shape = inp.shape
                self._name = inp.name
                self._idx = 0
                self._n = n_samples
                h = self._shape[2] if isinstance(self._shape[2], int) else 640
                w = self._shape[3] if isinstance(self._shape[3], int) else 640
                self._data = [
                    {self._name: np.random.randn(1, 3, h, w).astype(np.float32)}
                    for _ in range(n_samples)
                ]

            def get_next(self):
                if self._idx >= self._n:
                    return None
                feed = self._data[self._idx]
                self._idx += 1
                return feed

        print(f"Running static ONNX quantization to INT8 for {export_path}...")
        try:
            calib = _CalibReader(export_path, n_samples=50)
            quantize_static(
                model_input=export_path,
                model_output=target_path,
                calibration_data_reader=calib,
                quant_format=QuantFormat.QDQ,
                per_channel=True,
                reduce_range=True,
                weight_type=QuantType.QInt8,
            )
            print(f"Static quantization complete. Saved as {target_path}")
        except Exception as e:
            print(f"Static quantization failed ({e}), falling back to dynamic...")
            from onnxruntime.quantization import quantize_dynamic
            try:
                quantize_dynamic(
                    model_input=export_path,
                    model_output=target_path,
                    per_channel=True,
                    reduce_range=True,
                    weight_type=QuantType.QInt8,
                )
                print(f"Dynamic quantization complete. Saved as {target_path}")
            except Exception as e2:
                print(f"Dynamic quantization also failed: {e2}")
                if os.path.abspath(export_path) != os.path.abspath(target_path):
                    shutil.move(export_path, target_path)
    else:
        # Move to our models dir if needed
        if export_path and os.path.exists(export_path) and os.path.abspath(export_path) != os.path.abspath(target_path):
            shutil.move(export_path, target_path)
            print(f"Moved exported model to {target_path}")
        elif os.path.exists(target_path):
            print(f"Model exported successfully: {target_path}")
        else:
            print(f"Export completed. Check {export_path}")

    # Print file sizes for comparison
    if os.path.exists(pt_path):
        pt_size = os.path.getsize(pt_path) / (1024 * 1024)
        print(f"  .pt  size: {pt_size:.1f} MB")
    if os.path.exists(target_path):
        onnx_size = os.path.getsize(target_path) / (1024 * 1024)
        print(f"  .onnx size: {onnx_size:.1f} MB")

    print("\nDone! You can now remove 'ultralytics' from your Pi's requirements.txt.")


if __name__ == "__main__":
    main()
