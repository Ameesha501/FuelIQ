import cv2
import numpy as np
import os
from ultralytics import YOLO

# Load your custom YOLOv8 model
# Try multiple possible paths
model = None
model_paths = [
    "FuelIQ/numberplate_detection3/weights/best.pt",
    "numberplate_detection3/weights/best.pt",
    "yolov8n.pt",  # Fallback to default YOLOv8 model
    "datasets/yolov8/yolov8n.pt"
]

for path in model_paths:
    # Try relative path first, then absolute (helps when server cwd differs)
    candidate_paths = [path, os.path.join(os.getcwd(), path)]
    for candidate in candidate_paths:
        if os.path.exists(candidate):
            try:
                model = YOLO(candidate)
                print(f"Loaded YOLO model from: {candidate}")
                break
            except Exception as e:
                print(f"Error loading model from {candidate}: {e}")
                continue
    if model is not None:
        break

if model is None:
    print("Warning: YOLO model not found. Detection will return empty results.")
    # Create a dummy model object to prevent errors
    class DummyModel:
        def predict(self, *args, **kwargs):
            return []
    model = DummyModel()

def detect_plate_bbox(cv_img):
    """
    Detect number plate bounding boxes using YOLOv8.
    Returns list of bboxes: (x1, y1, x2, y2, confidence)
    """
    try:
        if isinstance(model, DummyModel):
            return []
        
        # Increase confidence threshold and image size for better detection
        results = model.predict(
            source=cv_img, 
            imgsz=1280,  # Higher resolution for better detection
            conf=0.15,   # Lower threshold to catch more plates
            iou=0.45,    # NMS threshold
            verbose=False,
            save=False
        )
        bboxes = []

        for r in results:
            if not hasattr(r, "boxes"):
                continue
            boxes = r.boxes
            for i, b in enumerate(boxes.xyxy.cpu().numpy()):
                x1, y1, x2, y2 = map(int, b[:4])
                # Get confidence score
                conf = float(boxes.conf[i].cpu().numpy()) if hasattr(boxes, 'conf') else 0.5
                bboxes.append((x1, y1, x2, y2, conf))

        return bboxes
    except Exception as e:
        print(f"Error in detect_plate_bbox: {e}")
        return []


def detect_and_annotate(cv_img):
    """
    Detect number plates and draw annotations on image.
    Returns: annotated image, list of bboxes with confidence
    """
    try:
        if isinstance(model, DummyModel):
            return cv_img.copy(), []
        
        # Make a copy to avoid modifying original
        annotated_img = cv_img.copy()
        
        # Detect plates
        bboxes = detect_plate_bbox(cv_img)
        
        if not bboxes:
            return annotated_img, []
        
        # Draw bounding boxes and labels
        for i, bbox in enumerate(bboxes):
            if len(bbox) == 5:
                x1, y1, x2, y2, conf = bbox
            else:
                x1, y1, x2, y2 = bbox[:4]
                conf = 0.5
            
            # Ensure coordinates are within image bounds
            h, w = annotated_img.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            # Draw bounding box (green color)
            color = (0, 255, 0)  # Green
            thickness = 3
            cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, thickness)
            
            # Draw confidence label
            label = f"Plate {i+1}: {conf:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            label_y = max(y1 - 10, label_size[1] + 10)
            
            # Draw label background
            cv2.rectangle(
                annotated_img,
                (x1, label_y - label_size[1] - 5),
                (x1 + label_size[0] + 10, label_y + 5),
                color,
                -1
            )
            
            # Draw label text
            cv2.putText(
                annotated_img,
                label,
                (x1 + 5, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                2
            )
        
        return annotated_img, bboxes
    except Exception as e:
        print(f"Error in detect_and_annotate: {e}")
        return cv_img.copy(), []


def extract_plate_crops(cv_img):
    """
    Returns the cropped plate images from YOLO detections.
    """
    crops = []
    bboxes = detect_plate_bbox(cv_img)

    for (x1, y1, x2, y2) in bboxes:
        crop = cv_img[y1:y2, x1:x2]
        if crop is not None and crop.size > 0:
            crops.append(crop)

    return crops


def detect_and_crop(cv_img):
    """
    Detect plates and return:
    - bboxes
    - cropped images
    """
    try:
        if isinstance(model, DummyModel):
            return [], []
        
        results = model.predict(source=cv_img, imgsz=640, conf=0.35, verbose=False)
        bboxes = []
        crops = []

        for r in results:
            if not hasattr(r, "boxes"):
                continue
            for b in r.boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = map(int, b[:4])
                bboxes.append((x1, y1, x2, y2))
                crop = cv_img[y1:y2, x1:x2]
                if crop is not None and crop.size > 0:
                    crops.append(crop)

        return bboxes, crops
    except Exception as e:
        print(f"Error in detect_and_crop: {e}")
        return [], []
