"""
NavigAid — Pi Flask Server + Main Control Loop
Teammate 2's entry point.

Run: python server.py

One serial connection shared between reader thread and control loop.
Flask receives CV data from MacBook over WiFi.
"""

import time
import threading
import serial
import json
from flask import Flask, request, jsonify
from brain import decide, fusion_confidence

app = Flask(__name__)

# ── Shared CV state (always use latest POST, never queue) ─────────────────────
_cv_data      = None
_cv_timestamp = 0.0
_cv_lock      = threading.Lock()

# ── Shared sensor state ───────────────────────────────────────────────────────
_sensor_data = {"ultrasonic_cm": 9999, "laser_mm": 9999, "tilt": False}
_sensor_lock = threading.Lock()

# ── Single shared serial connection ──────────────────────────────────────────
# One object, used by both serial_reader (reads) and control_loop (writes).
# pyserial is thread-safe for concurrent read/write on the same object.
_serial = None
SERIAL_PORT = "/dev/ttyACM0"   # update if needed: check with  ls /dev/tty*
SERIAL_BAUD = 9600


def open_serial():
    global _serial
    try:
        _serial = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        print(f"[SERIAL] Connected on {SERIAL_PORT} at {SERIAL_BAUD} baud")
    except Exception as e:
        print(f"[SERIAL] Could not open {SERIAL_PORT}: {e}")
        print("[SERIAL] Running without Arduino — commands printed to console only")


# ── Flask endpoint ─────────────────────────────────────────────────────────────

@app.route("/cv", methods=["POST"])
def receive_cv():
    """MacBook POSTs here every 100ms. Store latest, overwrite old."""
    data = request.get_json(silent=True)
    if data:
        with _cv_lock:
            global _cv_data, _cv_timestamp
            _cv_data      = data
            _cv_timestamp = time.time()
    return jsonify({"status": "ok"}), 200


# ── Serial reader thread ───────────────────────────────────────────────────────

def serial_reader():
    """
    Reads sensor data from Arduino continuously.
    Arduino sends: USL:195.96 USR:6.12
    """
    while True:
        if _serial is None:
            time.sleep(0.1)
            continue
        try:
            line = _serial.readline().decode("utf-8").strip()
            if not line:
                continue
            parts = {}
            for token in line.split():
                if ":" in token:
                    key, val = token.split(":")
                    parts[key] = float(val)
            data = {
                "ultrasonic_left_cm": parts.get("USL", 9999),
                "ultrasonic_right_cm": parts.get("USR", 9999),
                "tilt": False
            }
            with _sensor_lock:
                _sensor_data.update(data)
        except Exception as e:
            print(f"[SERIAL] Read error: {e}")
            time.sleep(0.1)


# ── Control loop ──────────────────────────────────────────────────────────────

def control_loop():
    """
    Runs every 200ms. Reads latest CV + sensor state, calls brain.decide(),
    sends the motor command char to Arduino over the shared serial connection.
    """
    last_command = None

    while True:
        now = time.time()

        with _cv_lock:
            cv        = dict(_cv_data) if _cv_data else None
            cv_age_ms = (now - _cv_timestamp) * 1000 if _cv_timestamp else 9999

        with _sensor_lock:
            sensors = dict(_sensor_data)

        command = decide(cv, cv_age_ms, sensors)

        if command != last_command:
            conf_str = fusion_confidence(cv, cv_age_ms, sensors)
            print(f"[BRAIN] {command} |  {conf_str}")
            last_command = command

        if _serial:
            try:
                _serial.write(command.encode())
            except Exception as e:
                print(f"[SERIAL] Write error: {e}")
        else:
            # No Arduino connected — just log so you can test brain logic alone
            pass

        time.sleep(0.2)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    open_serial()
    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=control_loop,  daemon=True).start()
    print("[SERVER] Flask starting on port 5000...")
    app.run(host="0.0.0.0", port=5000, threaded=True)
