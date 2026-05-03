# Smart Cane — Overall Project PRD
**Type:** Hackathon Build  
**Deadline:** Assembly by 1:00 AM, Pitch ready by morning  
**Team:** 3 people  

---

## Problem
Blind and visually impaired people rely on traditional white canes that only detect ground-level obstacles through physical touch. They provide no advance warning, no directional guidance, and no awareness of obstacles at torso or head height.

---

## Solution
An AI-powered smart cane that autonomously detects obstacles using computer vision and sensors, then physically steers itself to guide the user away from danger — no smartphone app required, no cloud dependency, works in real time at the edge.

---

## How It Works

```
Phone camera → MacBook (Computer Vision)
                    ↓ WiFi HTTP POST
              Raspberry Pi (Edge AI — sensor fusion + decision making)
                    ↓ Serial
              Arduino (Motor control + sensors)
                    ↓
              Two TT motors (differential steering)
```

1. **Phone camera** streams live video to MacBook
2. **MacBook** runs object detection (YOLOv8), identifies obstacles, estimates direction and distance, sends structured data to Pi every 100ms
3. **Raspberry Pi** receives CV data + reads hardware sensors, runs sensor fusion to decide which way to steer
4. **Arduino** executes motor commands, reads ultrasonic + laser sensors, sends data back to Pi
5. **Cane steers itself** — differential wheel speed pulls the user left or right away from obstacles

---

## Hardware Stack

| Component | Purpose |
|---|---|
| PVC pipe | Cane body |
| Raspberry Pi | Edge AI, decision making, sensor fusion |
| Arduino Uno | Motor control, sensor reading |
| 2x TT Gear Motors + wheels | Differential steering |
| L298N Motor Driver | Controls both motors from Arduino |
| HC-SR04 Ultrasonic (x2) | One angled left, one angled right — obstacle detection on each side |
| iPhone | Camera stream |
| MacBook | Computer vision processing |
| 9V battery | Powers Arduino |
| 4xAA battery pack | Powers motors via L298N |
| USB Power Bank | Powers Raspberry Pi |

---

## Software Stack

| Layer | Tech |
|---|---|
| Object detection | YOLOv8 nano (Python, MacBook) |
| Depth estimation | Bounding box heuristic → MiDaS (stretch) |
| CV → Pi communication | HTTP POST, Flask, JSON |
| Pi decision logic | Python, sensor fusion algorithm |
| Pi → Arduino | Serial (9600 baud) |
| Arduino firmware | C++, Arduino IDE |

---

## Team Split

### Teammate 1 — Computer Vision (MacBook)
- Phone camera stream → MacBook via hotspot
- YOLOv8 obstacle detection
- Direction + distance estimation
- POST JSON to Pi every 100ms

### Teammate 2 — Raspberry Pi (Edge AI + Coordinator)
- Flask server receives CV data
- Reads Arduino sensor data over serial
- Sensor fusion: combines CV + ultrasonic + laser
- Decides F/L/R/S and sends to Arduino
- Runs lightweight neural net / decision model (talking point for judges)

### Teammate 3 — Arduino (Hardware)
- Motor control (differential steering)
- HC-SR04 ultrasonic reading — left sensor angled left, right sensor angled right
- Serial communication with Pi

---

## Shared Interfaces (DO NOT CHANGE WITHOUT TELLING TEAM)

### Interface 1: MacBook → Pi
POST `http://pi.local:5000/cv` every 100ms

```json
{
  "obstacle": true,
  "direction": "left",
  "distance_m": 0.84,
  "confidence": 0.87
}
```

### Interface 2: Pi → Arduino
Serial at 9600 baud, full-word commands:

```
FORWARD = go forward
LEFT    = turn left
RIGHT   = turn right
STOP    = stop
```

### Interface 3: Arduino → Pi
Serial response with sensor data every 100ms:

```
USL:45.00 USR:62.00
```

`USL` = left ultrasonic distance (cm), `USR` = right ultrasonic distance (cm)

---

## Decision Logic (Pi)

```
IF USL < 40 AND USR < 40:
    stop (obstacle directly ahead on both sides)
ELSE IF USL < 40:
    turn right (obstacle on left)
ELSE IF USR < 40:
    turn left (obstacle on right)
ELSE IF CV obstacle AND direction == "left":
    turn right
ELSE IF CV obstacle AND direction == "right":
    turn left
ELSE IF CV obstacle AND direction == "center":
    stop
ELSE:
    forward
```

Hardware sensors always override CV — safety first.

---

## Build Timeline

| Time | Milestone |
|---|---|
| Now | Install dependencies, agree on interfaces, split up |
| +1 hr | Each component works independently (motors move, sensors print, CV detects) |
| +2 hrs | MacBook → Pi connection working |
| +3 hrs | Pi → Arduino connection working |
| +4 hrs | Full pipeline: obstacle detected → cane steers |
| 1:00 AM | Assembly on cane, full integration test |
| After 1am | Pitch refinement, demo rehearsal |

---

## MVP Definition
A physical cane that detects an obstacle placed in front of it and steers away from it during a live demo. Everything else is stretch.

---

## Stretch Goals
- iPhone LiDAR for real depth instead of CV estimation
- Text-to-speech audio feedback ("obstacle on your left")
- Haptic/buzzer feedback
- Raspberry Pi running MobileNet for on-device vision
- GPS for outdoor navigation

---

## Pitch Talking Points
- **Edge AI** — decision making runs locally on Raspberry Pi, no cloud, no latency, works anywhere
- **Multi-sensor fusion** — combines computer vision, ultrasonic, and laser for redundancy and safety
- **Hardware sensors override CV** — safety-first architecture, if sensors detect imminent obstacle they always win
- **Modular architecture** — each layer (CV, AI, hardware) can be upgraded independently
- **Real problem** — 253 million people worldwide live with visual impairment

---

## Risk Register

| Risk | Mitigation |
|---|---|
| WiFi drops between MacBook and Pi | Pi falls back to hardware sensors only |
| Motors too weak to steer | Test early, increase voltage if needed |
| CV too slow on MacBook | Drop to YOLOv8 nano, reduce resolution to 640x480 |
| Pi and Arduino serial miscommunication | Test serial independently before full integration |
| Assembly takes longer than expected | Each component must work standalone by 1am |