"""
NavigAid — Pi Flask Server + Main Control Loop
Teammate 2's entry point.

Run: python server.py

One serial connection shared between reader thread and control loop.
Flask receives CV data from MacBook over WiFi.
Serial sends single command char to Arduino: F | L | R | S
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
_sensor_data = {"ultrasonic_left_cm": 9999, "ultrasonic_right_cm": 9999, "tilt": False}
_sensor_lock = threading.Lock()

# ── Single shared serial connection ──────────────────────────────────────────
_serial = None
SERIAL_PORT = "/dev/ttyACM0"
SERIAL_BAUD = 9600


def open_serial():
    global _serial
    try:
        if _serial is not None:
            try:
                _serial.close()
            except Exception:
                pass
            _serial = None
        _serial = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        print(f"[SERIAL] Connected on {SERIAL_PORT} at {SERIAL_BAUD} baud", flush=True)
    except Exception as e:
        print(f"[SERIAL] Could not open {SERIAL_PORT}: {e}", flush=True)
        print("[SERIAL] Running without Arduino — commands printed to console only", flush=True)
        _serial = None


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
        if data.get("obstacle"):
            print(f"[CV IN] obstacle={data.get('obstacle')} dir={data.get('direction')} dist={data.get('distance_m')} conf={data.get('confidence')}", flush=True)
    return jsonify({"status": "ok"}), 200


# ── Serial reader thread ───────────────────────────────────────────────────────

def serial_reader():
    """
    Reads sensor data from Arduino continuously.
    Arduino sends: USL:195.96 USR:6.12
    Retries open_serial() every 2s when disconnected.
    """
    while True:
        if _serial is None:
            time.sleep(2)
            open_serial()  # keep retrying until Arduino comes back
            continue
        try:
            line = _serial.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            parts = {}
            for token in line.split():
                if ":" in token:
                    key, _, val = token.partition(":")
                    try:
                        parts[key.strip()] = float(val.strip())
                    except ValueError:
                        pass
            left  = parts.get("USL", 9999)
            right = parts.get("USR", 9999)
            data = {
                # Filter HC-SR04 false-zero readings (< 2cm = physically impossible)
                "ultrasonic_left_cm":  left  if left  > 2 else 9999,
                "ultrasonic_right_cm": right if right > 2 else 9999,
                "tilt": False
            }
            with _sensor_lock:
                _sensor_data.update(data)
        except Exception as e:
            print(f"[SERIAL] Read error: {e}", flush=True)
            time.sleep(0.1)


# ── Control loop ──────────────────────────────────────────────────────────────

def control_loop():
    """
    Runs every 200ms. Reads latest CV + sensor state, calls brain.decide(),
    sends single command char to Arduino on change or 1s heartbeat.
    """
    last_command   = None
    last_sent_cmd  = None
    last_heartbeat = 0.0

    while True:
        try:
            now = time.time()

            with _cv_lock:
                cv        = dict(_cv_data) if _cv_data else None
                cv_age_ms = (now - _cv_timestamp) * 1000 if _cv_timestamp > 0 else 9999

            with _sensor_lock:
                sensors = dict(_sensor_data)

            command = decide(cv, cv_age_ms, sensors)

            if command != last_command:
                conf_str = fusion_confidence(cv, cv_age_ms, sensors)
                print(f"[BRAIN] {command}  cv_age={cv_age_ms:.0f}ms  |  {conf_str}", flush=True)
                last_command = command

            # Write on change or 1s heartbeat — prevents Arduino buffer starvation
            changed   = command != last_sent_cmd
            heartbeat = (now - last_heartbeat) >= 1.0
            if _serial and (changed or heartbeat):
                try:
                    _serial.write(command.encode())
                    last_sent_cmd  = command
                    last_heartbeat = now
                except Exception as e:
                    print(f"[SERIAL] Write error: {e} — attempting reconnect", flush=True)
                    open_serial()

        except Exception as e:
            print(f"[CONTROL LOOP ERROR] {e} — continuing", flush=True)

        time.sleep(0.2)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    open_serial()
    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=control_loop,  daemon=True).start()
    print("[SERVER] Flask starting on port 5000...")
    app.run(host="0.0.0.0", port=5000, threaded=True)
