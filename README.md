# NavigAid

A smart cane that uses real-time depth sensing and sensor fusion to automatically steer blind users away from obstacles — no screen, no app, just walk.

---

## How It Works

```
Phone camera → MacBook (YOLOv8 + MiDaS)
                    ↓ WiFi HTTP POST
              Raspberry Pi (sensor fusion + decision logic)
                    ↓ USB Serial
              Arduino Uno (motor control + sensors)
                    ↓
              Two TT motors (differential steering)
```

---
<img width="3377" height="1100" alt="Untitled-2025-10-26-0713 excalidraw(1)" src="https://github.com/user-attachments/assets/8b6db9d3-21e0-460d-b8bb-ed6335b0a84f" />


## Setup

### 1. MacBook (Computer Vision)

```bash
cd cv
pip install -r requirements.txt
python detector.py
```

Streams from phone camera, runs YOLOv8n + MiDaS, POSTs obstacle data to the Pi every 100ms.

### 2. Raspberry Pi (Decision Brain)

SSH into the Pi:
```bash
ssh <username>@<PI_IP>
```

Install dependencies and run:
```bash
cd pi
pip install -r requirements.txt
python server.py
```

Before running, find the Arduino's serial port and update `SERIAL_PORT` in `server.py`:
```bash
ls /dev/tty*   # usually /dev/ttyACM0 or /dev/ttyUSB0
```

The Pi runs a Flask server on port 5000. The MacBook POSTs CV data to `/cv` and sensor readings are available at `/sensors`.

### 3. Arduino

Upload `arduino/NavigAid/NavigAid.ino` using **Arduino IDE** (not VS Code):
1. Open Arduino IDE
2. File → Open → `arduino/NavigAid/NavigAid.ino`
3. Tools → Board → Arduino AVR Boards → Arduino Uno
4. Tools → Port → select the correct COM port
5. Click Upload

---

## Serial Interface

**Pi → Arduino** (single char commands at 9600 baud):

| Command | Action |
|---|---|
| `F` | Move forward |
| `L` | Turn left |
| `R` | Turn right |
| `S` | Stop |

**Arduino → Pi** (every ~100ms):
```
USL:23.4 USR:31.2 LAS:450 PITCH:12.3 ROLL:-5.1
```

---

## CV Interface

MacBook POSTs to `http://<PI_IP>:5000/cv` every 100ms:
```json
{"obstacle": true, "direction": "left", "distance_m": 0.84, "confidence": 0.87}
```

`direction`: `"left"` | `"right"` | `"center"`

---

## Decision Priority

1. Either ultrasonic sensor < 40cm → steer away or stop
2. CV fresh + confidence ≥ 0.55 → steer based on obstacle direction
3. CV stale (>500ms) → crawl forward, hardware sensors still active
4. All clear → cruise forward
