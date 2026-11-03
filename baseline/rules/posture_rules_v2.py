"""
Posture and event rules, version 2 (one change from v1, frozen before scoring on unseen data)
==============================================================================================
Purpose: v1 raised a fall alert at the first fall-like movement. Most of its false fall alerts
on GMDCSA-24 were bends, pick-ups, push-ups and sitting on the floor, after which the person
got up again within seconds. v2 keeps every v1 rule and threshold and adds one: a fall
candidate becomes an alert only if, in the fall_confirm_hold_s seconds after it, the person
does not reach a sitting, upright or standing state; otherwise the next candidate is tried.
The alert time is the candidate time plus the wait actually used, because that is when the
sitter would see it. All other outputs (sit-up, stand-up, staff) are v1's, unchanged.
Date: 2026-10-19

Designed from v1's GMDCSA-24 results only; first scored on CAUCAFall, which neither version
was designed on (rules_v2.md).
"""

import numpy as np

import posture_rules as v1
from posture_rules import LYING, SITTING, STANDING, UPRIGHT

RECOVERED = (SITTING, UPRIGHT, STANDING)


def fall_candidates(t, f, sm, cfg):
    """Every frame where v1's fall rule would fire, in time order (v1's detect_fall returns only
    the first). Same two paths and thresholds as v1."""
    fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 15.0
    hip = v1._median_filter(f["hip_y"], cfg["hip_median_frames"])
    ref = v1._median_filter(f["ref_h"], int(round(fps)))
    w_drop, w_hold = int(round(cfg["fall_drop_window_s"] * fps)), int(round(cfg["fall_low_hold_s"] * fps))
    w_after = int(round(cfg["fall_confirm_within_s"] * fps))
    found = []
    for i in range(1, len(t)):
        lo = max(0, i - w_drop)
        prev = hip[lo:i]
        if np.all(np.isnan(prev)) or np.isnan(hip[i]) or np.isnan(ref[lo]):
            continue
        top = np.nanmin(prev)
        if hip[i] - top < cfg["fall_hip_drop_min"] * ref[lo]:
            continue
        after = hip[i:i + w_hold]
        stays_low = np.sum(~np.isnan(after)) >= w_hold // 2 and \
            np.nanmedian(after) - top >= cfg["fall_low_hold_fraction"] * ref[lo]
        ends_lying = np.sum(sm[i:i + w_after] == LYING) >= w_hold
        if stays_low or ends_lying:
            found.append((i, "hip_drop"))
    ang = v1._median_filter(f["angle"], cfg["angle_median_frames"])
    for i in range(len(t)):
        if not ang[i] >= cfg["trunk_lying_min_deg"]:
            continue
        back = (t >= t[i] - cfg["fall_fast_rotation_s"] - 1e-9) & (t < t[i])
        if not np.any(ang[back] <= cfg["trunk_upright_max_deg"]):
            continue
        if np.sum(sm[i:i + w_hold] == LYING) >= 0.7 * w_hold:
            found.append((i, "fast_rotation"))
    return sorted(found)


def confirm(t, st, i, cfg):
    """True if no sitting, upright or standing state starts within the hold after frame i, and at
    least fall_confirm_min_s of the clip remains to look at. Returns (confirmed, wait used in s)."""
    end = t[-1]
    wait = min(cfg["fall_confirm_hold_s"], end - t[i])
    if wait < cfg["fall_confirm_min_s"]:
        return False, wait
    for label, s, _ in st:
        if label in RECOVERED and t[i] < t[s] <= t[i] + wait:
            return False, wait
    return True, wait


def evaluate_clip(t, kpts, scores, boxes, size, cfg):
    out = v1.evaluate_clip(t, kpts, scores, boxes, size, cfg)
    fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 15.0
    K, S, B, _ = v1.people(kpts, scores, boxes, size, cfg)
    f = v1.features(K, S, B, cfg)
    sm = v1.smooth(v1.posture(f, cfg), max(1, int(round(cfg["smoothing_window_s"] * fps))) | 1)
    st = v1.runs(sm, t, cfg["min_state_duration_s"])
    cands = fall_candidates(t, f, sm, cfg)
    fall, fall_t, path = 0, None, ""
    for i, p in cands:
        ok, wait = confirm(t, st, i, cfg)
        if ok:
            fall, fall_t, path = 1, float(t[i] + wait), p
            break
    out.update(v1_pred_fall=out["pred_fall"], v1_pred_fall_t=out["pred_fall_t"],
               pred_fall=fall, pred_fall_t=fall_t, fall_path=path, fall_candidates=len(cands))
    return out
