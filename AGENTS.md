# NavigAid — Agent Context

Hackathon project. AI-powered smart cane for visually impaired users.
**Deadline:** 1:00 AM. **Team:** 3 people.

## What This Repo Is

A physical cane that detects obstacles using computer vision (YOLOv8 on MacBook),
makes steering decisions on a Raspberry Pi, and physically moves via Arduino-controlled motors.

## Folder Map

| Folder | Owner | What it does |
|--------|-------|-------------|
| `cv/` | You (MacBook) | iPhone stream → YOLO → POST JSON to Pi |
| `pi/` | Teammate 2 | Flask server, sensor fusion, motor commands |
| `arduino/` | Teammate 3 | Motor control, ultrasonic, laser, IMU |
| `ios/` | Stretch | ARKit LiDAR depth stream |
| `model/` | Stretch | Custom model training |

## Your Job: `cv/`

```
main.py      — main loop: capture → detect → post
detector.py  — YOLOv8 wrapper
estimator.py — direction (left/center/right) + distance (bounding box heuristic)
config.py    — all tuneables (PI_ENDPOINT, CAMERA_SOURCE, thresholds)
requirements.txt
```

Run: `cd cv && python main.py`

## Critical Interface (DO NOT CHANGE)

POST `http://pi.local:5000/cv` every 100ms:
```json
{"obstacle": true/false, "direction": "left|right|center|none", "distance_m": 0.84|null, "confidence": 0.87}
```

## Phone Camera Setup

See `PHONE_SETUP.md` — connect iPhone to MacBook via Camo app (USB preferred).
After connecting, update `config.CAMERA_SOURCE` to the correct device index.

## First Commands to Run

```bash
# 1. Install deps
cd cv && pip install -r requirements.txt

# 2. Test camera is reachable
python -c "import cv2; cap=cv2.VideoCapture(1); print(cap.read()[0])"

# 3. Pre-download YOLO model (do this NOW while you have internet)
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# 4. Run CV
python main.py
```

## Key Risks

- If `pi.local` doesn't resolve → get Pi's actual IP from Teammate 2 and update `config.PI_ENDPOINT`
- If FPS drops below 5 → ensure `yolov8n.pt` is being used, reduce `FRAME_WIDTH` to 320
- POST errors are non-fatal (just warnings) — the loop must never crash
