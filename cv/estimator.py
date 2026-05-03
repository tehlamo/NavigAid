import config


def get_direction(x1: int, x2: int, frame_width: int) -> str:
    """
    Decide which side the obstacle is blocking based on clearance.

    Convention: return where the obstacle IS (brain steers the OTHER way).
      "left"  → obstacle on left,  brain goes RIGHT
      "right" → obstacle on right, brain goes LEFT

    Never returns "center" for a YOLO obstacle — "center" is reserved for
    MiDaS stair/hazard detections where stopping is the correct response.
    When clearance is tied, we use the obstacle's cx as a tiebreaker so the
    brain always gets a steering direction rather than freezing.
    Without this, a centered obstacle (equal clearance both sides) would loop
    the brain between "stop" and "stop" forever because the side-angled
    ultrasonic sensors can't see a directly-forward obstacle.
    """
    left_clear = x1
    right_clear = frame_width - x2
    dead_band = frame_width * 0.05  # 32 px at 640 wide

    if right_clear > left_clear + dead_band:
        return "left"
    elif left_clear > right_clear + dead_band:
        return "right"

    # Clearance is tied — use cx to break the tie.
    cx = (x1 + x2) // 2
    return "left" if cx < frame_width // 2 else "right"


def get_distance(box_h: int, label: str = "default") -> float:
    """
    Estimate distance in metres from bounding box height.
    Formula: distance = (ref_height * ref_distance) / current_height

    Uses per-class reference heights from config.CLASS_REFERENCE_HEIGHT_PX so
    that a chair at 1m (box_h ≈ 100px) is not estimated as 2m the way it was
    with the shared 200px reference — which caused valid detections to be
    silently dropped because distance_m exceeded MAX_REACT_DISTANCE_M.
    """
    if box_h == 0:
        return 9.9
    ref_h = config.CLASS_REFERENCE_HEIGHT_PX.get(label, config.REFERENCE_HEIGHT_PX)
    return round((ref_h * config.REFERENCE_DISTANCE_M) / box_h, 2)
