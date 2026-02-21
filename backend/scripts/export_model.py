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

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/export_model.py <model_name>")
        print("Example: python scripts/export_model.py yolo11n")
        sys.exit(1)

    model_name = sys.argv[1]

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
    print(f"Exporting {model_name} to ONNX format ...")
    export_path = model.export(format="onnx", imgsz=640, simplify=True)
    
    # The export typically saves next to the .pt file
    # Move to our models dir if needed
    target_path = os.path.join(models_dir, f"{model_name}.onnx")
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
