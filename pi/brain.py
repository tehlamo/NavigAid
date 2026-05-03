"""
NavigAid — Pi Decision Brain
Sensor fusion + motor command logic.

Inputs (every decision cycle ~200ms):
  cv_data    : latest POST from MacBook {obstacle, direction, distance_m, confidence}
  cv_age_ms  : milliseconds since last CV POST received
  sensors    : latest Arduino reading {ultrasonic_left_cm, ultrasonic_right_cm}

Output: command str
  "F" | "L" | "R" | "S"

Priority (hard rules, in order):
  1. Either ultrasonic sensor too close  → STOP (imminent collision, overrides CV)
  2. CV fresh + confident               → steer based on obstacle direction
  3. CV stale / offline                 → slow forward, hardware sensors still active
  4. All clear                          → cruise forward

Hysteresis: once a command is issued it holds for COMMAND_HOLD_MS before
switching. Emergency stops (Rule 1) always override immediately.
"""

import time

# ── Thresholds ─────────────────────────────────────────────────────────────────
ULTRASONIC_STOP_CM   = 40      # hardware override: either sensor sees obstacle < 40cm
CV_TIMEOUT_MS        = 500     # treat CV as offline if no POST in 500ms
CV_MIN_CONFIDENCE    = 0.55    # ignore CV detections below this confidence
MAX_REACT_DISTANCE_M = 2.5     # must match cv/config.py MAX_REACT_DISTANCE_M

COMMAND_HOLD_MS = 400

# ── Internal state (hysteresis) ────────────────────────────────────────────────
_last_command    = "F"
_last_command_ts = 0.0


def decide(cv_data: dict | None, cv_age_ms: float, sensors: dict) -> str:
    """
    Returns command: "F" | "L" | "R" | "S".
    Call from the Pi main loop every ~200ms.
    """
    global _last_command, _last_command_ts

    now = time.time()

    left_cm  = sensors.get("ultrasonic_left_cm", 9999)
    right_cm = sensors.get("ultrasonic_right_cm", 9999)

    # ── Rule 1: Hardware sensor override ──────────────────────────────────────
    if left_cm < ULTRASONIC_STOP_CM or right_cm < ULTRASONIC_STOP_CM:
        if left_cm < right_cm:
            # obstacle closer on left → steer right
            return _set("R", now)
        elif right_cm < left_cm:
            # obstacle closer on right → steer left
            return _set("L", now)
        else:
            # both equally close → stop
            _last_command = "S"
            _last_command_ts = now
            return "S"

    # ── Hysteresis ────────────────────────────────────────────────────────────
    hold_active = (now - _last_command_ts) * 1000 < COMMAND_HOLD_MS
    if hold_active and _last_command != "S":
        return _last_command

    # ── Rule 2: CV-based steering ─────────────────────────────────────────────
    cv_online = (cv_age_ms < CV_TIMEOUT_MS) and (cv_data is not None)

    if cv_online and cv_data.get("obstacle"):
        confidence = cv_data.get("confidence", 0.0)

        if confidence < CV_MIN_CONFIDENCE:
            return _set("F", now)

        direction = cv_data.get("direction", "center")

        if direction == "left":
            return _set("R", now)
        elif direction == "right":
            return _set("L", now)
        else:
            return _set("S", now)

    # ── Rule 3: CV offline ────────────────────────────────────────────────────
    if not cv_online:
        return _set("F", now)

    # ── Rule 4: All clear ─────────────────────────────────────────────────────
    return _set("F", now)


def _set(command: str, now: float) -> str:
    global _last_command, _last_command_ts
    if command != _last_command:
        _last_command    = command
        _last_command_ts = now
    return command


# ── Debug / pitch helper ───────────────────────────────────────────────────────

def fusion_confidence(cv_data: dict | None, cv_age_ms: float, sensors: dict) -> str:
    cv_online = cv_age_ms < CV_TIMEOUT_MS and cv_data is not None
    left_cm   = sensors.get("ultrasonic_left_cm", 9999)
    right_cm  = sensors.get("ultrasonic_right_cm", 9999)
    hw_clear  = left_cm >= ULTRASONIC_STOP_CM and right_cm >= ULTRASONIC_STOP_CM

    if not hw_clear:
        return f"HIGH — hardware override (L:{left_cm}cm R:{right_cm}cm)"
    if not cv_online:
        return "MED  — CV offline, hardware-only crawl"
    if cv_data and cv_data.get("obstacle"):
        conf = cv_data.get("confidence", 0)
        tag  = "HIGH" if conf >= CV_MIN_CONFIDENCE else "LOW (ignored)"
        return f"{tag} — CV obstacle  conf={conf:.2f}  dir={cv_data.get('direction')}  dist={cv_data.get('distance_m')}m"
    return "HIGH — all sensors clear, cruising"
