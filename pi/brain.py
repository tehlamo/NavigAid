"""
NavigAid — Pi Decision Brain
Sensor fusion + motor command logic.

Inputs (every decision cycle ~200ms):
  cv_data    : latest POST from MacBook {obstacle, direction, distance_m, confidence}
  cv_age_ms  : milliseconds since last CV POST received
  sensors    : latest Arduino reading
               {ultrasonic_left_cm, ultrasonic_right_cm, laser, pitch, roll}

Output: command str
  "F" | "L" | "R" | "S"

Priority (hard rules, in order):
  1. Pitch >= -60                       → STOP (on/off safety switch)
  2. Both ultrasonic sensors < 80cm     → STOP
  3. One ultrasonic sensor < 80cm       → turn away from that side
  4. Laser <= 1m                        → choose a clear side using US + CV
  5. CV fresh + confident               → steer based on obstacle direction (no CV stop)
  6. CV stale / offline                 → forward, hardware sensors still active
  7. All clear                          → forward

Hysteresis: once a command is issued it holds for COMMAND_HOLD_MS before
switching. Emergency stops (Rule 1) always override immediately.
"""

import time

# ── Thresholds ─────────────────────────────────────────────────────────────────
ULTRASONIC_STOP_CM   = 80      # sensor reaction zone: side-specific turn, both sides stop
LASER_BLOCK_CM       = 100     # laser trigger distance (1 meter)
PITCH_STOP_THRESHOLD = -60     # pitch >= -60 means stop/off
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
    laser_cm = sensors.get("laser", 9999)
    pitch    = sensors.get("pitch", 9999)

    cv_online = (cv_age_ms < CV_TIMEOUT_MS) and (cv_data is not None)

    # ── Rule 1: Pitch safety switch ────────────────────────────────────────────
    if pitch >= PITCH_STOP_THRESHOLD:
        return _set("S", now)

    # ── Rule 2/3: Ultrasonic reaction (unchanged) ─────────────────────────────
    left_blocked = left_cm < ULTRASONIC_STOP_CM
    right_blocked = right_cm < ULTRASONIC_STOP_CM

    if left_blocked and right_blocked:
        return _set("S", now)
    if left_blocked:
        return _set("R", now)
    if right_blocked:
        return _set("L", now)

    # ── Rule 4: Laser reaction (use US + CV for side clearance) ───────────────
    if laser_cm <= LASER_BLOCK_CM:
        cv_left_blocked = False
        cv_right_blocked = False

        if cv_online and cv_data.get("obstacle"):
            confidence = cv_data.get("confidence", 0.0)
            if confidence >= CV_MIN_CONFIDENCE:
                direction = cv_data.get("direction", "center")
                if direction == "left":
                    cv_left_blocked = True
                elif direction == "right":
                    cv_right_blocked = True
                elif direction == "center":
                    cv_left_blocked = True
                    cv_right_blocked = True

        left_side_blocked = left_blocked or cv_left_blocked
        right_side_blocked = right_blocked or cv_right_blocked

        if not left_side_blocked and not right_side_blocked:
            return _set("R", now)
        if left_side_blocked and not right_side_blocked:
            return _set("R", now)
        if right_side_blocked and not left_side_blocked:
            return _set("L", now)
        return _set("S", now)

    # ── Hysteresis ────────────────────────────────────────────────────────────
    hold_active = (now - _last_command_ts) * 1000 < COMMAND_HOLD_MS
    if hold_active and _last_command != "S":
        return _last_command

    # ── Rule 5: CV-based steering ─────────────────────────────────────────────

    if cv_online and cv_data.get("obstacle"):
        confidence = cv_data.get("confidence", 0.0)

        if confidence < CV_MIN_CONFIDENCE:
            return _set("F", now)

        direction = cv_data.get("direction", "center")

        if direction == "left":
            return _set("L", now)
        elif direction == "right":
            return _set("R", now)
        else:
            # For "center"/"none"/unknown CV direction, bias toward the side
            # with more ultrasonic clearance so CV never causes a stop command.
            if right_cm > left_cm:
                return _set("R", now)
            if left_cm > right_cm:
                return _set("L", now)
            return _set("R" if _last_command not in ("L", "R") else _last_command, now)

    # ── Rule 6: CV offline ────────────────────────────────────────────────────
    if not cv_online:
        return _set("F", now)

    # ── Rule 7: All clear ─────────────────────────────────────────────────────
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
