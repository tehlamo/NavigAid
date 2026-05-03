import torch
from ultralytics import YOLO
import config

_model = None


def get_model():
    global _model
    if _model is None:
        _model = YOLO(config.YOLO_MODEL)
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _model.to(device)
        print(f"[YOLO] Using device: {device}")
    return _model


def detect(frame):
    """
    Run YOLOv8 on frame. Returns the most urgent obstacle or None.

    Priority rules:
      1. Closest non-person obstacle wins (chairs, cars, dogs etc. can't move)
      2. A person only counts if they are in the CENTER zone (directly blocking path)
         — people to the sides are ignored since they'll step aside
      3. Among eligible detections, closest (largest box_h) wins
    """
    results = get_model()(frame, imgsz=config.FRAME_WIDTH, verbose=False)[0]

    best_object = None   # closest non-person obstacle
    best_person = None   # closest center-zone person

    for box in results.boxes:
        conf = float(box.conf[0])
        if conf < config.MIN_CONFIDENCE:
            continue
        label = results.names[int(box.cls[0])]
        if label not in config.OBSTACLE_CLASSES:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        box_h = y2 - y1
        cx = (x1 + x2) // 2

        det = {
            "label": label,
            "confidence": conf,
            "cx": cx,
            "cy": (y1 + y2) // 2,
            "box_h": box_h,
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        }

        if label == "person":
            # Only care about people who are directly in your path (center zone)
            in_center = config.LEFT_ZONE_END <= cx <= config.RIGHT_ZONE_START
            if in_center:
                if best_person is None or box_h > best_person["box_h"]:
                    best_person = det
        else:
            if best_object is None or box_h > best_object["box_h"]:
                best_object = det

    # Non-person objects take priority; fall back to center person
    return best_object if best_object is not None else best_person
