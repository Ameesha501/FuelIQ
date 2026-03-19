from ultralytics import YOLO
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Load pretrained YOLOv8 nano model
model = YOLO("yolov8n.pt")

# Train
model.train(
    data="datasets/yolov8/data.yaml",  # path to your yaml
    epochs=20,                          # adjust as needed
    imgsz=640,
    batch=4 if device=="cpu" else 16,
    device=device,
    project="FuelIQ",                   # folder where best.pt will be saved
    name="numberplate_detection",  
    resume = False     # subfolder name
)
