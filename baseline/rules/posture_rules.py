"""
Posture and event rules for the first test (version 1, frozen before any test result)
=====================================================================================
Purpose: from body points per video frame, decide posture (lying, sitting, standing)
and the events the first test scores: fall, sit_up, stand_up, staff. Simple fixed
rules, nothing learned. The thresholds live in rules_v1.json; rules_v1.md explains them.
Date: 2026-10-19

Input per clip (what the pose step saves):
  t       (T,)           frame times in seconds
  kpts    (T, P, 17, 2)  body points in pixels, COCO-17 order, NaN where no person
  scores  (T, P, 17)     point confidences 0..1
  boxes   (T, P, 4)      person boxes x1, y1, x2, y2 in pixels, NaN where no person
  size    (2,)           frame width, height

Pure numpy, so the same file runs in Colab and here.
"""

import numpy as np

# COCO-17 indices
NOSE, LSHO, RSHO, LHIP, RHIP, LKNEE, RKNEE, LANK, RANK = 0, 5, 6, 11, 12, 13, 14, 15, 16
TORSO = [LSHO, RSHO, LHIP, RHIP]

LYING, SITTING, STANDING, UPRIGHT, UNKNOWN = "lying", "sitting", "standing", "upright", "unknown"


def _mid(k, s, a, b, kmin):
    """Midpoint of two points, or the one visible point, or NaN."""
    va, vb = s[..., a] >= kmin, s[..., b] >= kmin
    pa, pb = k[..., a, :], k[..., b, :]
    both = (pa + pb) / 2
    out = np.where((va & vb)[..., None], both, np.where(va[..., None], pa, np.where(vb[..., None], pb, np.nan)))
    return out


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def people(kpts, scores, boxes, size, cfg):
    """Per frame: the main person's points and box, and how many valid people are in view.

    A person is valid when the mean confidence of shoulders and hips reaches keypoint_score_min
    and the box covers at least person_min_area of the frame. The main person is followed from frame
    to frame: the valid box overlapping the previous main box most (IoU at least track_iou_min);
    when there is none, the largest valid box. So a nurse who walks in does not replace the patient.
    """
    kmin = cfg["keypoint_score_min"]
    T, P = scores.shape[:2]
    area = (boxes[..., 2] - boxes[..., 0]) * (boxes[..., 3] - boxes[..., 1])
    frame_area = float(size[0] * size[1])
    torso_conf = np.nanmean(np.where(np.isnan(scores[..., TORSO]), 0, scores[..., TORSO]), axis=-1)
    valid = (torso_conf >= kmin) & np.nan_to_num(area / frame_area >= cfg["person_min_area"], nan=False)
    n_people = valid.sum(axis=1)
    pick = np.zeros(T, dtype=int)
    prev = None
    for i in range(T):
        cand = np.flatnonzero(valid[i])
        if len(cand) == 0:
            continue
        choice = cand[np.argmax(np.nan_to_num(area[i, cand], nan=-1))]
        if prev is not None:
            ious = [_iou(boxes[i, c], prev) for c in cand]
            if max(ious) >= cfg["track_iou_min"]:
                choice = cand[int(np.argmax(ious))]
        pick[i], prev = choice, boxes[i, choice]
    rows = np.arange(T)
    K, S, B = kpts[rows, pick].copy(), scores[rows, pick].copy(), boxes[rows, pick].copy()
    none = n_people == 0
    K[none], S[none], B[none] = np.nan, 0, np.nan
    return K, S, B, n_people


def features(K, S, B, cfg):
    kmin = cfg["keypoint_score_min"]
    sho, hip = _mid(K, S, LSHO, RSHO, kmin), _mid(K, S, LHIP, RHIP, kmin)
    knee, ank = _mid(K, S, LKNEE, RKNEE, kmin), _mid(K, S, LANK, RANK, kmin)
    trunk = sho - hip
    trunk_len = np.hypot(trunk[:, 0], trunk[:, 1])
    with np.errstate(invalid="ignore", divide="ignore"):
        # 0 degrees: shoulders straight above hips; 90: trunk horizontal; above 90: head below hips
        angle = np.degrees(np.arctan2(np.abs(trunk[:, 0]), -trunk[:, 1]))
        leg_ratio = (ank[:, 1] - hip[:, 1]) / trunk_len
        knee_ratio = (knee[:, 1] - hip[:, 1]) / trunk_len
    return {"angle": angle, "leg_ratio": leg_ratio, "knee_ratio": knee_ratio, "hip_y": hip[:, 1],
            "ref_h": B[:, 3] - B[:, 1], "trunk_len": trunk_len}


def posture(f, cfg):
    a, leg, knee = f["angle"], f["leg_ratio"], f["knee_ratio"]
    out = np.full(a.shape, UNKNOWN, dtype=object)
    lying = a >= cfg["trunk_lying_min_deg"]
    up = a <= cfg["trunk_upright_max_deg"]
    standing = up & (leg >= cfg["standing_leg_ratio_min"])
    sitting = up & ~standing & ((leg <= cfg["sitting_leg_ratio_max"]) |
                                (np.isnan(leg) & (knee <= cfg["sitting_knee_ratio_max"])))
    out[up] = UPRIGHT
    out[sitting] = SITTING
    out[standing] = STANDING
    out[lying] = LYING
    return out


def smooth(labels, win):
    """Majority vote in a centred window; unknown only wins when nothing else is present."""
    n, h = len(labels), win // 2
    out = labels.copy()
    for i in range(n):
        w = [x for x in labels[max(0, i - h):i + h + 1] if x != UNKNOWN]
        if w:
            vals, counts = np.unique(np.array(w, dtype=object), return_counts=True)
            out[i] = vals[np.argmax(counts)]
        else:
            out[i] = UNKNOWN
    return out


def runs(labels, t, min_dur):
    """Stable runs: (label, start_index, end_index) lasting at least min_dur seconds, unknown dropped."""
    out, i, n = [], 0, len(labels)
    while i < n:
        j = i
        while j + 1 < n and labels[j + 1] == labels[i]:
            j += 1
        if labels[i] != UNKNOWN and t[j] - t[i] + (t[1] - t[0] if n > 1 else 0) >= min_dur:
            out.append((labels[i], i, j))
        i = j + 1
    return out


def _median_filter(x, k):
    h, out = k // 2, np.full_like(x, np.nan)
    for i in range(len(x)):
        w = x[max(0, i - h):i + h + 1]
        w = w[~np.isnan(w)]
        if len(w):
            out[i] = np.median(w)
    return out


def detect_fall(t, f, raw, sm, st, cfg):
    """Path A: the hips drop fast and stay low (or the person ends lying).
    Path B (falls onto a bed, where the hips barely drop): the smoothed trunk angle goes from
    upright to lying within fall_fast_rotation_s and the person then stays lying."""
    fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 15.0
    hip = _median_filter(f["hip_y"], cfg["hip_median_frames"])
    ref = _median_filter(f["ref_h"], int(round(fps)))
    w_drop, w_hold = int(round(cfg["fall_drop_window_s"] * fps)), int(round(cfg["fall_low_hold_s"] * fps))
    w_after = int(round(cfg["fall_confirm_within_s"] * fps))
    for i in range(1, len(t)):
        lo = max(0, i - w_drop)
        prev = hip[lo:i]
        if np.all(np.isnan(prev)) or np.isnan(hip[i]) or np.isnan(ref[lo]):
            continue
        top = np.nanmin(prev)  # highest hip position (smallest y) in the window before
        if hip[i] - top < cfg["fall_hip_drop_min"] * ref[lo]:
            continue
        after = hip[i:i + w_hold]
        stays_low = np.sum(~np.isnan(after)) >= w_hold // 2 and \
            np.nanmedian(after) - top >= cfg["fall_low_hold_fraction"] * ref[lo]
        ends_lying = np.sum(sm[i:i + w_after] == LYING) >= w_hold
        if stays_low or ends_lying:
            return True, float(t[i]), "hip_drop"
    ang = _median_filter(f["angle"], cfg["angle_median_frames"])
    w_back = cfg["fall_fast_rotation_s"]
    for i in range(len(t)):
        if not ang[i] >= cfg["trunk_lying_min_deg"]:
            continue
        back = (t >= t[i] - w_back - 1e-9) & (t < t[i])
        if not np.any(ang[back] <= cfg["trunk_upright_max_deg"]):
            continue
        if np.sum(sm[i:i + w_hold] == LYING) >= 0.7 * w_hold:
            return True, float(t[i]), "fast_rotation"
    return False, None, ""


def detect_transitions(t, f, st, cfg):
    """sit_up: a lying run followed by a sitting or upright run.
    stand_up: a sitting or lying run followed by a standing run, or by an upright run with the hips
    risen by stand_hip_rise of the person's height."""
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
                    h0, h1 = np.nanmedian(f["hip_y"][sa:ea + 1]), np.nanmedian(f["hip_y"][sb:eb + 1])
                    ref = np.nanmedian(f["ref_h"][sa:eb + 1])
                    if not np.isnan(h0 + h1 + ref) and h0 - h1 >= cfg["stand_hip_rise"] * ref:
                        stand_up = float(t[sb])
            break  # only the next stable run counts as the transition from run k
    return sit_up, stand_up


def detect_staff(t, n_people, cfg):
    fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 15.0
    w = max(1, int(round(cfg["staff_min_duration_s"] * fps)))
    many = (n_people >= cfg["staff_min_people"]).astype(float)
    for i in range(0, max(1, len(t) - w + 1)):
        if many[i:i + w].mean() >= cfg["staff_min_fraction"]:
            return True, float(t[i])
    return False, None


def evaluate_clip(t, kpts, scores, boxes, size, cfg):
    """All rule outputs for one clip."""
    fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 15.0
    K, S, B, n_people = people(kpts, scores, boxes, size, cfg)
    f = features(K, S, B, cfg)
    raw = posture(f, cfg)
    sm = smooth(raw, max(1, int(round(cfg["smoothing_window_s"] * fps))) | 1)
    st = runs(sm, t, cfg["min_state_duration_s"])
    fall, fall_t, fall_path = detect_fall(t, f, raw, sm, st, cfg)
    sit_up_t, stand_up_t = detect_transitions(t, f, st, cfg)
    staff, staff_t = detect_staff(t, n_people, cfg)
    share = {p: float(np.mean(sm == p)) for p in (LYING, SITTING, STANDING, UPRIGHT, UNKNOWN)}
    return {"pred_fall": int(fall), "pred_fall_t": fall_t, "fall_path": fall_path,
            "pred_sit_up": int(sit_up_t is not None), "pred_sit_up_t": sit_up_t,
            "pred_stand_up": int(stand_up_t is not None), "pred_stand_up_t": stand_up_t,
            "pred_staff": int(staff), "pred_staff_t": staff_t,
            "person_found_share": float(np.mean(n_people > 0)),
            "states": " > ".join(f"{a}@{t[s]:.1f}" for a, s, _ in st),
            **{f"share_{k}": v for k, v in share.items()}}
