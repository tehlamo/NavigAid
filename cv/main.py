"""
NavigAid — Computer Vision Module
iPhone camera -> MacBook (YOLOv8 + MiDaS depth) -> Pi HTTP POST every 100ms

Before running:
  1. Follow PHONE_SETUP.md to connect iPhone and set CAMERA_SOURCE in config.py
  2. pip install -r requirements.txt
  3. Confirm Pi IP: ping pi.local  (or update PI_ENDPOINT in config.py)
"""

import time
import threading
from collections import Counter, deque
import cv2
import requests
import numpy as np

import config
import detector
import estimator

# ── Direction smoothing ───────────────────────────────────────────────────────
# YOLO direction flickers frame-to-frame, which makes the brain oscillate
# between TURN and STOP rapidly.  Keep a rolling window of the last 5 values
# and send the majority-vote winner.  At 100ms POSTs that's a 500ms window —
# fast enough to react to a new obstacle, slow enough to absorb single-frame
# noise.  "none" (no detection) is included in the vote so a brief gap doesn't
# immediately cancel an active steer.
_dir_buffer: deque = deque(maxlen=7)


def _smooth_direction(raw_dir: str) -> str:
    _dir_buffer.append(raw_dir)
    winner, count = Counter(_dir_buffer).most_common(1)[0]
    # Require strict majority (>50%) to commit to a new direction.
    # If tied, return the most recent value so we don't freeze on old data.
    if count > len(_dir_buffer) / 2:
        return winner
    return raw_dir


NO_OBSTACLE_PAYLOAD = {
    "obstacle": False,
    "direction": "none",
    "distance_m": None,
    "confidence": 0.0,
}


# ── Threaded frame reader ─────────────────────────────────────────────────────

class FrameReader:
    def __init__(self, source):
        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera source: {source!r}")
        self.frame = None
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        while not self._stop.is_set():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
                with self.lock:
                    self.frame = frame
            else:
                time.sleep(0.01)

    def read(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self._stop.set()
        self.cap.release()


# ── Fire-and-forget POST ──────────────────────────────────────────────────────

def post_to_pi(payload):
    def _send():
        try:
            requests.post(config.PI_ENDPOINT, json=payload, timeout=0.5)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            pass
        except Exception as e:
            print(f"[WARN] POST: {e}")
    threading.Thread(target=_send, daemon=True).start()


# ── Payload builders ──────────────────────────────────────────────────────────

def build_yolo_payload(det):
    if det is None:
        return None
    distance_m = estimator.get_distance(det["box_h"], det["label"])
    if distance_m > config.MAX_REACT_DISTANCE_M:
        return None
    raw_dir = estimator.get_direction(det["x1"], det["x2"], config.FRAME_WIDTH)
    # Only smooth actual detections — never inject "none" into the buffer so
    # the buffer doesn't vote against a real obstacle when it first appears.
    return {
        "obstacle": True,
        "direction": _smooth_direction(raw_dir),
        "distance_m": distance_m,
        "confidence": round(det["confidence"], 2),
    }


def build_depth_payload(depth_result):
    if depth_result is None:
        return None
    hazard_type, direction, distance_m = depth_result
    if distance_m > config.MAX_REACT_DISTANCE_M:
        return None
    return {
        "obstacle": True,
        "direction": direction,
        "distance_m": distance_m,
        "confidence": 0.80,
    }


def merge_payloads(yolo_payload, depth_payload):
    """
    Send the most urgent obstacle to the Pi.

    Rules (in order):
      1. If only one source has a detection, send it.
      2. If both fire, send whichever is CLOSER (smaller distance_m).
         Depth hazards win ties — stairs/potholes are uniquely dangerous
         because hardware sensors on the cane can't see them.
      3. If neither fires, send no-obstacle.
    """
    if depth_payload is None and yolo_payload is None:
        return NO_OBSTACLE_PAYLOAD
    if depth_payload is None:
        return yolo_payload
    if yolo_payload is None:
        return depth_payload

    # Both fired — pick the closer one; depth wins on equal distance
    yolo_dist = yolo_payload.get("distance_m") or 9.9
    depth_dist = depth_payload.get("distance_m") or 9.9
    return depth_payload if depth_dist <= yolo_dist else yolo_payload


# ── Debug display ─────────────────────────────────────────────────────────────

def draw_debug(frame, det, payload, depth_result):
    if det:
        cv2.rectangle(frame, (det["x1"], det["y1"]), (det["x2"], det["y2"]), (0, 255, 0), 2)
        direction = estimator.get_direction(det["x1"], det["x2"], config.FRAME_WIDTH)
        dist = estimator.get_distance(det["box_h"], det["label"])
        label = f"{det['label']} {direction} {dist:.1f}m"
        cv2.putText(frame, label, (det["x1"], det["y1"] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    if depth_result:
        hazard_type, direction, dist = depth_result
        cv2.putText(frame, f"[DEPTH] {hazard_type} {direction} {dist}m",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2)

    status = f"-> {payload['direction']}  {payload['distance_m']}m  conf={payload['confidence']}"
    color = (0, 0, 255) if payload["obstacle"] else (0, 200, 100)
    cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return frame


# ── Startup check ─────────────────────────────────────────────────────────────

def check_pi_connection():
    try:
        requests.post(config.PI_ENDPOINT, json=NO_OBSTACLE_PAYLOAD, timeout=1.0)
        print(f"[INFO] Pi reachable at {config.PI_ENDPOINT}")
    except Exception:
        print(f"[WARN] Pi not reachable at {config.PI_ENDPOINT} — CV will run, cane won't move yet")
        print(f"[WARN] Once Pi is up, POSTs start automatically (no restart needed)")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    check_pi_connection()

    reader = FrameReader(config.CAMERA_SOURCE)
    print(f"[INFO] Camera open ({config.FRAME_WIDTH}x{config.FRAME_HEIGHT})")

    # Start depth analyzer in background (loads MiDaS async, won't block startup)
    depth_analyzer = None
    if config.ENABLE_DEPTH_HAZARD:
        from depth_analyzer import DepthAnalyzer
        depth_analyzer = DepthAnalyzer()
        print("[INFO] MiDaS loading in background — depth hazard detection coming online...")
    else:
        print("[INFO] Depth hazard detection disabled (ENABLE_DEPTH_HAZARD=False)")

    print(f"[INFO] Posting to {config.PI_ENDPOINT} every {config.POST_INTERVAL_S*1000:.0f}ms")
    print("[INFO] Press 'q' to quit, 'c' to recalibrate distance")

    print("[INFO] Warming up YOLO...")
    detector.detect(np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype="uint8"))
    print("[INFO] YOLO ready.")

    last_post = 0.0
    fps_start = time.time()
    frame_count = 0

    while True:
        frame = reader.read()
        if frame is None:
            time.sleep(0.01)
            continue

        # Feed frame to depth analyzer (non-blocking)
        if depth_analyzer is not None:
            depth_analyzer.update_frame(frame)

        det = detector.detect(frame)
        yolo_payload = build_yolo_payload(det)

        depth_result = depth_analyzer.get_result() if depth_analyzer and depth_analyzer.ready else None
        depth_payload = build_depth_payload(depth_result)

        payload = merge_payloads(yolo_payload, depth_payload)

        now = time.time()
        if now - last_post >= config.POST_INTERVAL_S:
            post_to_pi(payload)
            last_post = now

        draw_debug(frame, det, payload, depth_result)

        frame_count += 1
        elapsed = time.time() - fps_start
        if elapsed >= 2.0:
            fps = frame_count / elapsed
            depth_status = "online" if (depth_analyzer and depth_analyzer.ready) else "loading..."
            print(f"[FPS] {fps:.1f}  depth={depth_status}  |  {payload}")
            frame_count = 0
            fps_start = time.time()

        cv2.imshow("NavigAid CV", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("c"):
            if det:
                config.REFERENCE_HEIGHT_PX = det["box_h"]
                print(f"[CALIBRATE] Reference height set to {det['box_h']}px at 1.0m")
            else:
                print("[CALIBRATE] No obstacle in frame — point camera at something first")

    reader.stop()
    if depth_analyzer:
        depth_analyzer.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
