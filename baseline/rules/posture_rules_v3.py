"""
Posture and event rules, version 3: the same body points, placed in 3D with the depth camera
==============================================================================================
Purpose: rules that work from the product's camera position. From the wall in front of the bed, a
patient lying down has the head above the hips in the picture, so v1 and v2 (which use the trunk's
angle in the image) never see "lying" (synthetic pilot, research/synthetic_video/pilot/results).
v3 looks up the depth at each body point, places the points in the room, and measures the trunk
against gravity and the hips' height above the floor. Lying is lying from any camera position.
Date: 2026-10-19. Thresholds in rules_v3.json; reasons in rules_v3.md.

Inputs per clip, besides what v1 takes (t, kpts, scores, boxes, size):
  depth   (T, H, W) uint16, millimetres along the camera's optical axis, 0 = no data, on the
          same pixels as the image the body points came from (on the OAK-D Pro W: the
          mono cameras; depth aligned to them)
  K       (fx, fy, cx, cy) of that camera
  cam_to_world  4x4: camera coordinates (OpenCV: x right, y down, z forward) to room coordinates
          with z up and the floor at z = 0. On the product: gravity from the camera's motion
          sensor (BNO086) and the floor from a plane fitted to the depth; in renders: the scene.
Pure numpy, so it runs in Colab and here. Tracking, smoothing, state runs and staff are v1's.
"""

import numpy as np
import posture_rules as pr

LYING, SITTING, STANDING, UPRIGHT, UNKNOWN = pr.LYING, pr.SITTING, pr.STANDING, pr.UPRIGHT, pr.UNKNOWN
NOSE, LSHO, RSHO, LHIP, RHIP, LKNEE, RKNEE = pr.NOSE, pr.LSHO, pr.RSHO, pr.LHIP, pr.RHIP, pr.LKNEE, pr.RKNEE


def depth_at(depth, u, v, cfg):
    """Depth (m) near pixel (u, v): a low percentile of the valid values in a small window, so that
    a point on the body's edge takes the body rather than the wall behind it. NaN if none."""
    if not (np.isfinite(u) and np.isfinite(v)):
        return np.nan
    h, w = depth.shape
    r = cfg["depth_window_px"] // 2
    x, y = int(round(u)), int(round(v))
    if x < 0 or y < 0 or x >= w or y >= h:
        return np.nan
    win = depth[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1].astype(float).ravel()
    win = win[(win >= cfg["depth_valid_min_mm"]) & (win <= cfg["depth_valid_max_mm"])]
    return float(np.percentile(win, cfg["depth_percentile"])) / 1000 if len(win) else np.nan


def to_room(uv, z, K, cam_to_world):
    fx, fy, cx, cy = K
    pc = np.array([(uv[0] - cx) * z / fx, (uv[1] - cy) * z / fy, z, 1.0])
    return (cam_to_world @ pc)[:3]


def joints_3d(Kp, S, depth, K, cam_to_world, cfg):
    """Room coordinates of the shoulder, hip and knee centres per frame (NaN where unknown)."""
    T = len(Kp)
    out = {k: np.full((T, 3), np.nan) for k in ("sho", "hip", "knee")}
    pairs = {"sho": (LSHO, RSHO), "hip": (LHIP, RHIP), "knee": (LKNEE, RKNEE)}
    for i in range(T):
        for name, (a, b) in pairs.items():
            pts = []
            for j in (a, b):
                if S[i, j] >= cfg["keypoint_score_min"] and np.all(np.isfinite(Kp[i, j])):
                    z = depth_at(depth[i], Kp[i, j, 0], Kp[i, j, 1], cfg)
                    if np.isfinite(z):
                        pts.append(to_room(Kp[i, j], z, K, cam_to_world))
            if pts:
                out[name][i] = np.mean(pts, axis=0)
    return out


def _angle_to(v, ref):
    n = np.linalg.norm(v, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.degrees(np.arccos(np.clip((v @ ref) / n, -1, 1)))


def features_3d(j):
    """Trunk angle to vertical (0 upright, 90 lying), thigh angle to straight down (0 standing,
    about 90 sitting), and hip height above the floor (m)."""
    return {"trunk_deg": _angle_to(j["sho"] - j["hip"], np.array([0, 0, 1.0])),
            "thigh_deg": _angle_to(j["knee"] - j["hip"], np.array([0, 0, -1.0])),
            "hip_h": j["hip"][:, 2]}


def posture_3d(f, cfg):
    a, th, h = f["trunk_deg"], f["thigh_deg"], f["hip_h"]
    out = np.full(a.shape, UNKNOWN, dtype=object)
    for i in range(len(a)):
        if not np.isfinite(a[i]):
            continue
        if a[i] >= cfg["trunk_lying_min_deg"]:
            out[i] = LYING
        elif a[i] <= cfg["trunk_upright_max_deg"]:
            if np.isfinite(th[i]) and th[i] <= cfg["thigh_standing_max_deg"] and h[i] >= cfg["standing_hip_min_m"]:
                out[i] = STANDING
            elif np.isfinite(th[i]) and th[i] >= cfg["thigh_sitting_min_deg"]:
                out[i] = SITTING
            elif not np.isfinite(th[i]) and np.isfinite(h[i]) and h[i] < cfg["standing_hip_min_m"]:
                out[i] = SITTING  # knees hidden (blanket): hips at bed or chair height, trunk up
            else:
                out[i] = UPRIGHT
    return out


def detect_floor_fall(t, f, cfg):
    """A fall: the hips come down to the floor (at most floor_hip_max_m) within fall_descent_window_s
    of being off it (at least off_floor_hip_min_m), and stay there for floor_hold_s (share
    floor_hold_fraction of the frames with a known hip height). A slow, deliberate descent to the
    floor that takes longer than the window is not a fall."""
    fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 15.0
    h = pr._median_filter(f["hip_h"], 5)
    w_back, w_hold = int(round(cfg["fall_descent_window_s"] * fps)), int(round(cfg["floor_hold_s"] * fps))
    for i in range(len(t)):
        if not (np.isfinite(h[i]) and h[i] <= cfg["floor_hip_max_m"]):
            continue
        before = h[max(0, i - w_back):i]
        if not np.any(before >= cfg["off_floor_hip_min_m"]):
            continue
        after = h[i:i + w_hold]
        known = after[np.isfinite(after)]
        if len(after) >= w_hold and len(known) >= cfg["floor_hold_fraction"] * w_hold and np.all(known <= cfg["off_floor_hip_min_m"]):
            return True, float(t[i])
    return False, None


def detect_transitions_3d(t, f, st, cfg):
    """As v1: sit_up is a lying run followed by a sitting or upright run; stand_up is a sitting or
    lying run followed by a standing run, or by an upright run with the hips risen by stand_hip_rise_m."""
    sit_up = stand_up = None
    for k, (a, sa, ea) in enumerate(st):
        for b, sb, eb in st[k + 1:]:
            if b == a:
                continue
            if sit_up is None and a == LYING and b in (SITTING, UPRIGHT):
                sit_up = float(t[sb])
            if stand_up is None and a in (SITTING, LYING):
                if b == STANDING:
                    stand_up = float(t[sb])
                elif b == UPRIGHT:
                    h0, h1 = np.nanmedian(f["hip_h"][sa:ea + 1]), np.nanmedian(f["hip_h"][sb:eb + 1])
                    if np.isfinite(h0 + h1) and h1 - h0 >= cfg["stand_hip_rise_m"]:
                        stand_up = float(t[sb])
            break
    return sit_up, stand_up


def evaluate_clip(t, kpts, scores, boxes, size, depth, K, cam_to_world, cfg):
    """All rule outputs for one clip, in the same form as v1's evaluate_clip, plus 3D measures."""
    fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 15.0
    Kp, S, B, n_people = pr.people(kpts, scores, boxes, size, cfg)
    j = joints_3d(Kp, S, depth, K, np.asarray(cam_to_world, float), cfg)
    f = features_3d(j)
    raw = posture_3d(f, cfg)
    sm = pr.smooth(raw, max(1, int(round(cfg["smoothing_window_s"] * fps))) | 1)
    st = pr.runs(sm, t, cfg["min_state_duration_s"])
    fall, fall_t = detect_floor_fall(t, f, cfg)
    sit_up_t, stand_up_t = detect_transitions_3d(t, f, st, cfg)
    staff, staff_t = pr.detect_staff(t, n_people, cfg)
    share = {p: float(np.mean(sm == p)) for p in (LYING, SITTING, STANDING, UPRIGHT, UNKNOWN)}
    return {"pred_fall": int(fall), "pred_fall_t": fall_t, "fall_path": "floor" if fall else "",
            "pred_sit_up": int(sit_up_t is not None), "pred_sit_up_t": sit_up_t,
            "pred_stand_up": int(stand_up_t is not None), "pred_stand_up_t": stand_up_t,
            "pred_staff": int(staff), "pred_staff_t": staff_t,
            "person_found_share": float(np.mean(n_people > 0)),
            "depth_found_share": float(np.mean(np.isfinite(f["trunk_deg"]))),
            "states": " > ".join(f"{a}@{t[s]:.1f}" for a, s, _ in st),
            **{f"share_{k}": v for k, v in share.items()}}, f
