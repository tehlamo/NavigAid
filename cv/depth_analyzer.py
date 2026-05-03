"""
Depth hazard detection using MiDaS small.
Runs in a background thread — never blocks the YOLO inference loop.

Detects ground-level hazards that hardware sensors miss:
  - Stairs going DOWN (floor drops away ahead) — column AND row based
  - Potholes / curbs (local depth dip in floor plane)

Returns a (hazard_type, direction, distance_m) tuple or None.
"""

import threading
import time
import numpy as np
import torch
import config

_model = None
_transform = None
_device = None


def _load_model():
    global _model, _transform, _device
    _device = "mps" if torch.backends.mps.is_available() else "cpu"
    print("[DEPTH] Loading MiDaS small...")
    _model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small", trust_repo=True)
    _transform = torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True).small_transform
    _model.to(_device).eval()
    print(f"[DEPTH] MiDaS ready on {_device}")


def _get_depth_map(frame):
    """Return a normalized depth map (higher value = closer to camera)."""
    input_tensor = _transform(frame).to(_device)
    with torch.no_grad():
        depth = _model(input_tensor)
    depth_np = depth.squeeze().cpu().numpy()
    d_min, d_max = depth_np.min(), depth_np.max()
    if d_max - d_min < 1e-5:
        return None
    return (depth_np - d_min) / (d_max - d_min)


def _analyze_floor(depth_map):
    """
    Inspect the bottom-center floor strip for ground hazards.

    MiDaS: higher normalized value = closer. Lower value = further away.

    Check 1 — STRAIGHT-AHEAD STAIRS (row-based):
      Compare very-bottom rows (floor right in front) vs upper rows (floor ahead).
      If near floor is significantly closer than far floor → step ahead.
      This catches full-width staircases you're walking straight into.

    Check 2 — SIDE STEP / PARTIAL CURB (column-based):
      Scan columns left-to-right for a drop between adjacent columns.
      Catches curbs/steps visible on one side of path.

    Check 3 — POTHOLE:
      A column that dips below both neighbors = hole in the floor.

    Returns (hazard_type, direction, distance_m) or None.
    """
    h, w = depth_map.shape

    # Floor strip: bottom 40% height (was 25%), center 50% width.
    # Expanded so the stair edge 1-2m ahead is captured when the camera is
    # near-horizontal — at that angle the transition zone is in the middle
    # rows of the frame, not just the very bottom.
    strip_top = int(h * 0.60)
    strip_left = int(w * 0.25)
    strip_right = int(w * 0.75)
    strip = depth_map[strip_top:, strip_left:strip_right]
    sh, sw = strip.shape

    # Column means (for left/right hazard direction)
    col_w = sw // 4
    col_means = [strip[:, i * col_w:(i + 1) * col_w].mean() for i in range(4)]
    floor_mean = float(np.mean(col_means))

    def _distance_from_floor(mean_val):
        return round(max(0.3, config.DEPTH_DISTANCE_SCALE / (mean_val + 0.01)), 2)

    def _direction_from_ratio(ratio):
        if ratio < 0.33:
            return "left"
        elif ratio > 0.66:
            return "right"
        return "center"

    # ── Check 1: straight-ahead stairs (row-based) ────────────────────────
    # Near floor = bottom 20% of strip rows (closest to camera)
    # Far floor  = top 20% of strip rows (further ahead on the ground)
    near_rows = strip[int(sh * 0.80):, :]
    far_rows = strip[:int(sh * 0.20), :]
    near_mean = float(near_rows.mean())
    far_mean = float(far_rows.mean())
    # near_mean should be > far_mean (closer = higher value) on normal floor,
    # but the drop is about HOW MUCH further the far floor is vs near floor.
    row_drop = near_mean - far_mean
    if row_drop > config.DEPTH_STEP_ROW_THRESHOLD:
        # Floor falls away ahead — stairs or steep drop straight in front
        distance_m = _distance_from_floor(far_mean)
        return ("step_down", "center", distance_m)

    # ── Check 2: side step / partial curb (column-based) ─────────────────
    for i in range(len(col_means) - 1):
        drop = col_means[i] - col_means[i + 1]
        if drop > config.DEPTH_STEP_DROP_THRESHOLD:
            ratio = (i + 0.5) / len(col_means)
            direction = _direction_from_ratio(ratio)
            distance_m = _distance_from_floor(floor_mean)
            return ("step_down", direction, distance_m)

    # ── Check 3: pothole (column dip) ────────────────────────────────────
    for i in range(1, len(col_means) - 1):
        neighbor_avg = (col_means[i - 1] + col_means[i + 1]) / 2
        if neighbor_avg - col_means[i] > config.DEPTH_POTHOLE_DIP_THRESHOLD:
            ratio = i / len(col_means)
            direction = _direction_from_ratio(ratio)
            distance_m = _distance_from_floor(floor_mean)
            return ("pothole", direction, distance_m)

    return None


# ── Background thread ─────────────────────────────────────────────────────────

class DepthAnalyzer:
    def __init__(self):
        self._latest_frame = None
        self._result = None
        self._frame_lock = threading.Lock()
        self._result_lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = False
        self._consecutive = 0  # debounce counter
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            _load_model()
            self._ready = True
        except Exception as e:
            print(f"[DEPTH] Failed to load MiDaS: {e}")
            print("[DEPTH] Depth hazard detection disabled")
            return

        while not self._stop.is_set():
            with self._frame_lock:
                frame = self._latest_frame

            if frame is None:
                time.sleep(0.05)
                continue

            try:
                small = _resize_for_midas(frame)
                depth_map = _get_depth_map(small)
                if depth_map is None:
                    continue

                raw = _analyze_floor(depth_map)

                # Debounce: require DEPTH_DEBOUNCE_COUNT consecutive detections
                # before reporting, and clear immediately when gone.
                if raw is not None:
                    self._consecutive += 1
                    if self._consecutive >= config.DEPTH_DEBOUNCE_COUNT:
                        with self._result_lock:
                            self._result = raw
                else:
                    self._consecutive = 0
                    with self._result_lock:
                        self._result = None

            except Exception as e:
                print(f"[DEPTH] Analysis error: {e}")

    def update_frame(self, frame):
        with self._frame_lock:
            self._latest_frame = frame

    def get_result(self):
        with self._result_lock:
            return self._result

    @property
    def ready(self):
        return self._ready

    def stop(self):
        self._stop.set()


def _resize_for_midas(frame):
    import cv2
    return cv2.resize(frame, (256, 192))
