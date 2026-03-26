import os
import shutil
from ultralytics import YOLO

models = ['yolo11n.pt', 'yolo11s.pt', 'yolo11m.pt', 'yolo11l.pt', 'yolo11x.pt']

for model_name in models:
    print(f"Downloading {model_name}...")
    model = YOLO(model_name)
    print(f"Downloaded {model_name}")
    
    os.makedirs("weights", exist_ok=True)
    destination = f"weights/{model_name}"
    
    if os.path.exists(model_name):
        if os.path.exists(destination):
            os.remove(destination)
        shutil.move(model_name, destination)
        print(f"Moved to {destination}")

print("All models downloaded successfully.")
