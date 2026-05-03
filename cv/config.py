PI_ENDPOINT = "http://192.168.68.60:5000/cv"
POST_INTERVAL_S = 0.1  # 100ms

# Phone camera stream
# Camo (USB/WiFi) -> use integer index, e.g. CAMERA_SOURCE = 1
# HTTP MJPEG app  -> CAMERA_SOURCE = "http://<phone-ip>:8080/video"
CAMERA_SOURCE = 1  # iPhone via Camo (index 0 = built-in MacBook camera)

YOLO_MODEL = "yolov8n.pt"
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

OBSTACLE_CLASSES = {
    "person", "chair", "car", "truck", "bicycle",
    "dog", "backpack", "suitcase", "bench", "bus",
}

LEFT_ZONE_END = FRAME_WIDTH / 3
RIGHT_ZONE_START = 2 * FRAME_WIDTH / 3

# Calibrate: hold any medium object 1.0m away, note bounding box height in px
REFERENCE_HEIGHT_PX = 200
REFERENCE_DISTANCE_M = 1.0

MIN_CONFIDENCE = 0.45

# Per-class bounding-box height (px) when the object is exactly 1 m away.
# Used by estimator.get_distance() so that a chair at 1m is not mistaken for
# a person at 2m — the single shared REFERENCE_HEIGHT_PX caused CV obstacles
# at realistic distances to be discarded as "too far" (> MAX_REACT_DISTANCE_M).
CLASS_REFERENCE_HEIGHT_PX = {
    "person":    200,
    "chair":     100,
    "car":       150,
    "truck":     180,
    "bicycle":   130,
    "dog":        90,
    "backpack":  130,
    "suitcase":  140,
    "bench":      90,
    "bus":       200,
}

# ── Depth Hazard Detection (MiDaS) ───────────────────────────────────────────
# Set to False to disable entirely if MiDaS causes issues at the hackathon
ENABLE_DEPTH_HAZARD = True

# Step detection: how much the floor depth must DROP between adjacent columns
# 0.0–1.0 scale (normalized depth). Lower = more sensitive, more false positives.
DEPTH_STEP_DROP_THRESHOLD = 0.25

# Pothole detection: how much a column must dip below its neighbors
DEPTH_POTHOLE_DIP_THRESHOLD = 0.30

# Distance estimate scale for depth hazards (rough — tunable)
# distance_m ≈ DEPTH_DISTANCE_SCALE / floor_mean_depth
DEPTH_DISTANCE_SCALE = 0.5

# How many consecutive analyses must agree before reporting a hazard
# (prevents one noisy frame from stopping the cane)
DEPTH_DEBOUNCE_COUNT = 3

# Row-based step detection: drop between near floor and far floor in strip
# Higher = less sensitive. Start at 0.30, tune down if real stairs are missed.
DEPTH_STEP_ROW_THRESHOLD = 0.28

# Maximum distance at which CV reports an obstacle to the Pi.
# Beyond this, the object exists but is not yet an immediate threat — don't act.
# At walking speed (~1 m/s), 2.5m = ~2.5 seconds of reaction time.
# Raise if cane should respond earlier; lower if too many false steers in crowds.
MIN_REACT_DISTANCE_M = 0.45  # below this, hardware sensors take over — CV is too noisy
MAX_REACT_DISTANCE_M = 2.5
