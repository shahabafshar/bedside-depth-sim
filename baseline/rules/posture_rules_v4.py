"""
Rules version 4: v3 with a fall rule that allows for the depth camera seeing the body's surface
==============================================================================================
Purpose: v3 placed body points at the depth of the surface the camera sees, so a patient lying on
the floor measured about 0.4 m up and never met v3's 0.30 m floor threshold (renders, 2026-10-19;
research/synthetic_video/pilot/results/RENDERS_diagnosis.md). v4 changes only the fall rule:
a fast drop ending low, rather than an absolute floor height. Everything else is v3's.
Date: 2026-10-19. Thresholds in rules_v4.json; reasons in rules_v4.md.
"""

import numpy as np
import posture_rules as pr
import posture_rules_v3 as p3


def detect_floor_fall(t, f, cfg):
    """A fall: within fall_descent_window_s the hip height drops by at least fall_drop_min_m and ends at
    or below floor_surface_max_m (floor_surface_upright_max_m if the trunk is upright then, so sitting
    down on a chair is not a fall); the hips then stay at or below that limit plus floor_hold_margin_m
    for floor_hold_s (share floor_hold_fraction of the frames with a known hip height)."""
    fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 15.0
    h = pr._median_filter(f["hip_h"], 5)
    a = pr._median_filter(f["trunk_deg"], 5)
    w_back, w_hold = int(round(cfg["fall_descent_window_s"] * fps)), int(round(cfg["floor_hold_s"] * fps))
    for i in range(1, len(t)):
        if not np.isfinite(h[i]):
            continue
        limit = cfg["floor_surface_upright_max_m"] if (np.isfinite(a[i]) and a[i] <= cfg["trunk_upright_max_deg"]) else cfg["floor_surface_max_m"]
        if h[i] > limit:
            continue
        before = h[max(0, i - w_back):i]
        if not (np.any(np.isfinite(before)) and np.nanmax(before) - h[i] >= cfg["fall_drop_min_m"]):
            continue
        after = h[i:i + w_hold]
        known = after[np.isfinite(after)]
        if len(after) >= w_hold and len(known) >= cfg["floor_hold_fraction"] * w_hold and np.all(known <= limit + cfg["floor_hold_margin_m"]):
            return True, float(t[i])
    return False, None


def evaluate_clip(t, kpts, scores, boxes, size, depth, K, cam_to_world, cfg):
    """v3's evaluate_clip with v4's fall rule."""
    saved = p3.detect_floor_fall
    p3.detect_floor_fall = detect_floor_fall
    try:
        return p3.evaluate_clip(t, kpts, scores, boxes, size, depth, K, cam_to_world, cfg)
    finally:
        p3.detect_floor_fall = saved
