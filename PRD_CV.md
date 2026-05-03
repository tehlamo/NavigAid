# Smart Cane — Computer Vision Module PRD
**Owner:** You  
**Hackathon deadline:** 1:00 AM  
**Stack:** iPhone camera → MacBook (Python + OpenCV/YOLO) → Pi (Flask POST)

---

## Goal
Stream phone camera to MacBook, detect obstacles in real time, estimate their direction and distance, and POST structured JSON to the Pi every 100ms.

---

## System Context

```
Phone camera → MacBook (YOUR JOB)
                    ↓ WiFi / HTTP POST every 100ms
               Pi at http://pi.local:5000/cv  (Teammate 1)
                    ↓ Serial
               Arduino → motors (Teammate 2)
```

---

## Output Interface (DO NOT CHANGE WITHOUT TELLING TEAM)

POST to `http://pi.local:5000/cv` every 100ms with this exact JSON:

```json
{
  "obstacle": true,
  "direction": "left",
  "distance_m": 0.84,
  "confidence": 0.87
}
```

**Field definitions:**
- `obstacle`: `true` or `false`
- `direction`: `"left"` | `"right"` | `"center"` | `"none"`
- `distance_m`: float in meters, estimated from bounding box size
- `confidence`: float 0.0–1.0 from model output

**No obstacle detected:**
```json
{
  "obstacle": false,
  "direction": "none",
  "distance_m": null,
  "confidence": 0.0
}
```

---

## Tasks — In Priority Order

### 1. Phone Camera Stream to MacBook
- [ ] Install **IP Webcam** (Android) or **Camo** (iPhone) on phone
- [ ] Connect phone and MacBook to same hotspot (use phone hotspot)
- [ ] Confirm OpenCV can read stream: `cv2.VideoCapture("http://<phone-ip>:8080/video")`
- [ ] Print FPS to confirm stream is live
- **Done when:** MacBook terminal shows live FPS from phone camera

### 2. Obstacle Detection
- [ ] Install YOLOv8 nano: `pip install ultralytics`
- [ ] Run on camera stream frame by frame
- [ ] Filter detections to relevant classes: `person`, `chair`, `car`, `truck`, `bicycle`, `dog`, `backpack`, `suitcase`
- [ ] Draw bounding boxes on frame for visual debugging
- **Done when:** Bounding boxes appear around obstacles in live feed

### 3. Direction Estimation
- [ ] Divide frame into 3 zones: left third, center third, right third
- [ ] Use center X of bounding box to determine zone
- [ ] Map zone → direction string: `"left"` | `"center"` | `"right"`
- **Done when:** Terminal prints correct direction as you move obstacles

### 4. Distance Estimation (bounding box heuristic)
- [ ] Use bounding box height as proxy for distance
- [ ] Calibrate: hold object 1m away, note box height in pixels → use as reference
- [ ] Formula: `distance_m = (reference_height_px * 1.0) / current_box_height_px`
- **Done when:** Terminal prints roughly correct distance in meters

### 5. POST to Pi
- [ ] Install requests: `pip install requests`
- [ ] POST JSON to `http://pi.local:5000/cv` every 100ms in a loop
- [ ] Handle connection errors gracefully (try/except, just print warning, don't crash)
- **Done when:** Teammate 1 confirms Pi is receiving your JSON

---

## Stretch Goals (only if ahead of schedule)

### MiDaS Depth Estimation
- [ ] `pip install torch torchvision timm`
- [ ] Load MiDaS small model
- [ ] Replace bounding box heuristic with real depth map value at obstacle center
- Talking point: *"We're running monocular depth estimation on the MacBook"*

### iPhone LiDAR
- [ ] Use **Depth Camera** app on iPhone to stream depth + RGB
- [ ] Parse depth value at obstacle bounding box center
- [ ] Replace `distance_m` heuristic with real LiDAR reading

---

## Dependencies to Install Now

```bash
pip install ultralytics opencv-python requests numpy
```

---

## Key Numbers to Agree With Team

| Parameter | Value |
|---|---|
| POST endpoint | `http://pi.local:5000/cv` |
| POST frequency | every 100ms |
| Serial baud rate | 9600 |
| Motor commands | F / L / R / S |
| Frame resolution | 640x480 (keep it low for speed) |

---

## Risk Flags
- **Phone hotspot + MacBook WiFi to Pi** — test this connection first before writing any CV code
- **YOLO on MacBook may be slow** — use `yolov8n` (nano), not medium or large
- **Pi IP address** — confirm `pi.local` resolves or get the actual IP from Teammate 1 early
- **Don't let CV crash stop the cane** — Pi should have a fallback if no POST received in 500ms

---

## Definition of Done (your piece)
MacBook terminal shows live detections with direction + distance, and Teammate 1 confirms JSON is arriving at the Pi. Everything else is stretch.