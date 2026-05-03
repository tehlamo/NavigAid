"""
Quick brain.py sanity test — run from pi/ folder:
    python test_brain.py

No hardware needed. Feeds mock data and prints what motor command fires.
"""

import importlib
import brain

SENSORS_CLEAR = {"ultrasonic_left_cm": 9999, "ultrasonic_right_cm": 9999, "tilt": False}
SENSORS_LEFT_CLOSE = {"ultrasonic_left_cm": 20, "ultrasonic_right_cm": 9999, "tilt": False}
SENSORS_TILT = {"ultrasonic_left_cm": 9999, "ultrasonic_right_cm": 9999, "tilt": True}

cases = [
    # ── Baseline ──────────────────────────────────────────────────────────────
    ("CV offline",
     None, 9999, SENSORS_CLEAR),

    # ── Real CV frames from your phone run (terminal output 2026-05-02) ───────
    # These are verbatim from the [FPS] lines you got — noisy, flickery, real.
    ("REAL: no detection frame  conf=0.0",
     {"obstacle": False, "direction": "none", "distance_m": None, "confidence": 0.0}, 80, SENSORS_CLEAR),

    ("REAL: center 0.45m conf=0.82 — STOP",
     {"obstacle": True, "direction": "center", "distance_m": 0.45, "confidence": 0.82}, 80, SENSORS_CLEAR),

    ("REAL: center 0.42m conf=0.86 — STOP (closest seen)",
     {"obstacle": True, "direction": "center", "distance_m": 0.42, "confidence": 0.86}, 80, SENSORS_CLEAR),

    ("REAL: center 0.42m conf=0.79 — still above 0.55 threshold",
     {"obstacle": True, "direction": "center", "distance_m": 0.42, "confidence": 0.79}, 80, SENSORS_CLEAR),

    ("REAL: left 0.93m conf=0.80 — turn RIGHT",
     {"obstacle": True, "direction": "left",   "distance_m": 0.93, "confidence": 0.80}, 80, SENSORS_CLEAR),

    ("REAL: center 0.96m conf=0.80 — STOP (farther but still center)",
     {"obstacle": True, "direction": "center", "distance_m": 0.96, "confidence": 0.80}, 80, SENSORS_CLEAR),

    ("REAL: left 1.18m conf=0.80 — turn RIGHT (low urgency)",
     {"obstacle": True, "direction": "left",   "distance_m": 1.18, "confidence": 0.80}, 80, SENSORS_CLEAR),

    ("REAL: center 1.03m conf=0.80 — STOP",
     {"obstacle": True, "direction": "center", "distance_m": 1.03, "confidence": 0.80}, 80, SENSORS_CLEAR),

    # ── Edge cases the real camera will hit ───────────────────────────────────
    ("EDGE: confidence 0.74 just above threshold — should act",
     {"obstacle": True, "direction": "center", "distance_m": 0.56, "confidence": 0.74}, 80, SENSORS_CLEAR),

    ("EDGE: confidence 0.54 just below threshold — should IGNORE → FORWARD",
     {"obstacle": True, "direction": "center", "distance_m": 0.56, "confidence": 0.54}, 80, SENSORS_CLEAR),

    ("EDGE: detection then gap (obstacle=False after seeing one) — FORWARD",
     {"obstacle": False, "direction": "none",  "distance_m": None, "confidence": 0.0}, 80, SENSORS_CLEAR),

    ("EDGE: CV stale 600ms (phone briefly blocked) — crawl FORWARD",
     {"obstacle": True, "direction": "center", "distance_m": 0.42, "confidence": 0.86}, 600, SENSORS_CLEAR),

    # ── Hardware override ──────────────────────────────────────────────────────
    ("HW: left ultrasonic 20cm — STOP overrides clear CV",
     {"obstacle": False, "direction": "none",  "distance_m": None, "confidence": 0.0}, 80, SENSORS_LEFT_CLOSE),

    ("HW: tilt — emergency STOP",
     None, 80, SENSORS_TILT),
]

COMMANDS = {"F": "FORWARD", "S": "STOP", "L": "TURN LEFT", "R": "TURN RIGHT"}
PAD = 52

print(f"\n{'─' * 80}")
print(f"  {'TEST CASE':<{PAD}}  CMD    SPEED  CONFIDENCE STRING")
print(f"{'─' * 80}")

for label, cv, age, sensors in cases:
    # Reset hysteresis state between cases so each is independent
    brain._last_command    = "F"
    brain._last_command_ts = 0.0

    cmd, speed = brain.decide(cv, age, sensors)
    conf_str   = brain.fusion_confidence(cv, age, sensors)
    print(f"  {label:<{PAD}}  {cmd} ({COMMANDS[cmd]:<11})  {speed:>3}    {conf_str}")

print(f"{'─' * 80}\n")
