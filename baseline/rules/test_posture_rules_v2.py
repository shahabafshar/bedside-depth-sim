"""
Made-up movement tests for posture_rules_v2.py
==============================================
Purpose: check the one v2 change on synthetic sequences: a forward bend to pick something up
(which v1 calls a fall) must not alert; a real fall must still alert, 3 s after the movement;
a fall followed by getting up after the wait still alerts; a fall in the last half second of a
clip cannot be confirmed. No dataset clip is used.
Date: 2026-10-19

Usage (from the project root; needs numpy):
  python evaluation/01_zero_shot_pose/test_posture_rules_v2.py
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import posture_rules_v2 as v2  # noqa: E402
import test_posture_rules as t1  # noqa: E402

CFG = json.loads((HERE / "rules_v2.json").read_text())
V1_FRAME = t1.frame


def frame(name, cx=t1.CX):
    """v1's test poses plus a forward bend: legs straight, trunk horizontal, head forward."""
    if name != "bend":
        return V1_FRAME(name, cx)
    k = np.full((17, 2), np.nan)
    for i, (x, y) in {0: (110, 232), 5: (80, 212), 6: (80, 218), 11: (-5, 220), 12: (5, 220),
                      13: (-5, 310), 14: (5, 310), 15: (-5, 395), 16: (5, 395)}.items():
        k[i] = (cx + x, y)
    return k, np.array((cx - 40, 195, cx + 130, 400), float)


def sequence(steps):
    t1.frame, original = frame, t1.frame  # reuse v1's sequence builder with the extra pose
    try:
        return t1.sequence(steps)
    finally:
        t1.frame = original


CASES = [
    ("stand, bend to pick up (0.3 s), hold 1.2 s, stand up", [("stand", 2), ("->", 0.3), ("bend", 1.2), ("->", 0.5), ("stand", 3)],
     dict(v1_pred_fall=1, pred_fall=0)),
    ("stand, fall to the floor, lie 4 s", [("stand", 2), ("->", 0.6), ("lie_floor", 4)],
     dict(v1_pred_fall=1, pred_fall=1)),
    ("stand, fall onto the bed, lie 4 s", [("stand", 2), ("->", 0.4), ("lie_bed", 4)],
     dict(pred_fall=1)),
    ("fall to the floor, get up after 4 s", [("stand", 2), ("->", 0.6), ("lie_floor", 4), ("->", 1.0), ("stand", 2)],
     dict(pred_fall=1)),
    ("fall to the floor in the last 0.5 s of the clip", [("stand", 3), ("->", 0.6), ("lie_floor", 0.5)],
     dict(pred_fall=0)),
    ("sit on bed, lie down slowly", [("sit_bed", 2), ("->", 2.0), ("lie_bed", 3)],
     dict(pred_fall=0)),
]


def main():
    failures = 0
    for name, steps, expect in CASES:
        out = v2.evaluate_clip(*sequence(steps), CFG)
        bad = {k: (out[k], v) for k, v in expect.items() if out[k] != v}
        if "lie 4 s" in name and out["pred_fall"] and out["v1_pred_fall_t"] is not None \
                and not out["pred_fall_t"] >= out["v1_pred_fall_t"] + 0.9 * CFG["fall_confirm_hold_s"] - 1.0:
            bad["alert time"] = (out["pred_fall_t"], "about 3 s after the movement")
        failures += bool(bad)
        print(f"[{'PASS' if not bad else 'FAIL'}] {name}: v1 fall={out['v1_pred_fall']} at {out['v1_pred_fall_t']}, "
              f"v2 fall={out['pred_fall']} at {out['pred_fall_t']} ({out['fall_path']}, {out['fall_candidates']} candidates) | {out['states']}"
              + (f" | expected {bad}" if bad else ""))
    print(f"{len(CASES) - failures} of {len(CASES)} cases behave as specified")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
