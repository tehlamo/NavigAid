"""
NavigAid — Pi Decision Brain
Sensor fusion + motor command logic.

Inputs (every decision cycle ~200ms):
  cv_data    : latest POST from MacBook {obstacle, direction, distance_m, confidence}
  cv_age_ms  : milliseconds since last CV POST received
  sensors    : latest Arduino reading {ultrasonic_cm, laser_mm, tilt}

Output: (command, speed)
  command : "F" | "L" | "R" | "S"
  speed   : 0–100 (scale to PWM on Arduino side — agree protocol with Teammate 3)

Priority (hard rules, in order):
  1. Tilt detected              → STOP immediately (cane has fallen)
  2. Hardware sensor too close  → STOP (imminent collision, overrides CV)
  3. CV fresh + confident       → steer proportional to distance_m
  4. CV stale / offline         → slow forward, hardware sensors still active
  5. All clear                  → cruise forward

Hysteresis: once a command is issued it holds for COMMAND_HOLD_MS before
switching. Emergency stops (Rules 1 & 2) always override immediately.
"""

import time

# ── Thresholds ─────────────────────────────────────────────────────────────────
LASER_STOP_MM        = 300     # hardware override: laser sees obstacle < 30cm
ULTRASONIC_STOP_CM   = 40      # hardware override: ultrasonic sees obstacle < 40cm
CV_TIMEOUT_MS        = 500     # treat CV as offline if no POST in 500ms
CV_MIN_CONFIDENCE    = 0.55    # ignore CV detections below this confidence
MAX_REACT_DISTANCE_M = 2.5     # must match cv/config.py MAX_REACT_DISTANCE_M

SPEED_CRUISE    = 55           # forward speed when all clear
SPEED_MIN_STEER = 50           # gentlest steer (far obstacle)
SPEED_MAX_STEER = 100          # hardest steer (close obstacle, or center=stop)
SPEED_CRAWL     = 35           # fallback speed when CV is offline

# How long to hold a command before allowing a direction change.
# Prevents rapid motor switching from jittery CV detections.
# Emergency stops (tilt, hardware sensor) always override instantly.
COMMAND_HOLD_MS = 400

# ── Internal state (hysteresis) ────────────────────────────────────────────────
_last_command    = "F"
_last_command_ts = 0.0         # time.time() when last command was issued


def decide(cv_data: dict | None, cv_age_ms: float, sensors: dict) -> tuple[str, int]:
    """
    Returns (command: str, speed: int).
    Call from the Pi main loop every ~200ms.
    """
    global _last_command, _last_command_ts

    now = time.time()

    # ── Rule 1: Tilt / fall ────────────────────────────────────────────────
    # Always immediate — no hysteresis. Motors stop the moment cane falls.
    if sensors.get("tilt", False):
        _last_command = "S"
        _last_command_ts = now
        return ("S", 0)

    laser_mm      = sensors.get("laser_mm", 9999)
    ultrasonic_cm = sensors.get("ultrasonic_cm", 9999)

    # ── Rule 2: Hardware sensor override ──────────────────────────────────
    # Imminent physical collision — always immediate, no hysteresis.
    if laser_mm < LASER_STOP_MM or ultrasonic_cm < ULTRASONIC_STOP_CM:
        _last_command = "S"
        _last_command_ts = now
        return ("S", SPEED_MAX_STEER)

    # ── Rules 3-5: Check hysteresis before any direction change ───────────
    # If we're within the hold window, keep current command unless it was a
    # stop (stops should be re-evaluated immediately so we don't freeze).
    hold_active = (now - _last_command_ts) * 1000 < COMMAND_HOLD_MS
    if hold_active and _last_command != "S":
        return (_last_command, _speed_for_command(_last_command, cv_data))

    # ── Rule 3: CV-based steering ─────────────────────────────────────────
    cv_online = (cv_age_ms < CV_TIMEOUT_MS) and (cv_data is not None)

    if cv_online and cv_data.get("obstacle"):
        confidence = cv_data.get("confidence", 0.0)

        # Don't act on weak detections — send forward instead
        if confidence < CV_MIN_CONFIDENCE:
            return _set("F", SPEED_CRUISE, now)

        direction  = cv_data.get("direction", "center")
        distance_m = cv_data.get("distance_m") or MAX_REACT_DISTANCE_M

        urgency = 1.0 - min(distance_m / MAX_REACT_DISTANCE_M, 1.0)
        speed   = int(SPEED_MIN_STEER + urgency * (SPEED_MAX_STEER - SPEED_MIN_STEER))

        if direction == "left":
            return _set("R", speed, now)
        elif direction == "right":
            return _set("L", speed, now)
        else:                            # center or unknown → stop
            return _set("S", SPEED_MAX_STEER, now)

    # ── Rule 4: CV offline ────────────────────────────────────────────────
    if not cv_online:
        return _set("F", SPEED_CRAWL, now)

    # ── Rule 5: All clear ─────────────────────────────────────────────────
    return _set("F", SPEED_CRUISE, now)


def _set(command: str, speed: int, now: float) -> tuple[str, int]:
    global _last_command, _last_command_ts
    if command != _last_command:
        _last_command    = command
        _last_command_ts = now
    return (command, speed)


def _speed_for_command(command: str, cv_data: dict | None) -> int:
    """Return the appropriate speed for maintaining the current command."""
    if command == "F":
        return SPEED_CRUISE
    if command == "S":
        return 0
    # L or R — scale by distance if we still have fresh CV data
    if cv_data and cv_data.get("distance_m"):
        urgency = 1.0 - min(cv_data["distance_m"] / MAX_REACT_DISTANCE_M, 1.0)
        return int(SPEED_MIN_STEER + urgency * (SPEED_MAX_STEER - SPEED_MIN_STEER))
    return SPEED_MIN_STEER


# ── Debug / pitch helper ───────────────────────────────────────────────────────

def fusion_confidence(cv_data: dict | None, cv_age_ms: float, sensors: dict) -> str:
    cv_online = cv_age_ms < CV_TIMEOUT_MS and cv_data is not None
    hw_clear  = (sensors.get("laser_mm", 9999) >= LASER_STOP_MM and
                 sensors.get("ultrasonic_cm", 9999) >= ULTRASONIC_STOP_CM)

    if sensors.get("tilt", False):
        return "TILT — emergency stop"
    if not hw_clear:
        return "HIGH — hardware override (imminent collision)"
    if not cv_online:
        return "MED  — CV offline, hardware-only crawl"
    if cv_data and cv_data.get("obstacle"):
        conf = cv_data.get("confidence", 0)
        tag  = "HIGH" if conf >= CV_MIN_CONFIDENCE else "LOW (ignored)"
        return f"{tag} — CV obstacle  conf={conf:.2f}  dir={cv_data.get('direction')}  dist={cv_data.get('distance_m')}m"
    return "HIGH — all sensors clear, cruising"
