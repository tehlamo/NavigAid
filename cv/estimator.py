import config


def get_direction(cx: int) -> str:
    """Map bounding box center X to left/center/right zone."""
    if cx < config.LEFT_ZONE_END:
        return "left"
    elif cx > config.RIGHT_ZONE_START:
        return "right"
    else:
        return "center"


def get_distance(box_h: int) -> float:
    """
    Estimate distance in meters from bounding box height.
    Formula: distance = (ref_height * ref_distance) / current_height
    Calibrate REFERENCE_HEIGHT_PX in config.py.
    """
    if box_h == 0:
        return 9.9
    return (config.REFERENCE_HEIGHT_PX * config.REFERENCE_DISTANCE_M) / box_h
