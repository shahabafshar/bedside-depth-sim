"""
Made-up movement tests for posture_rules.py
===========================================
Purpose: check that each rule does what rules_v1.md says on simple synthetic body-point
sequences (a person seen from the front by a camera at chest height, 15 frames per second).
No dataset clip is used, so running this does not reveal any test result.
Date: 2026-10-19

Usage (from the project root; needs numpy):
  python evaluation/01_zero_shot_pose/test_posture_rules.py
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import posture_rules as pr  # noqa: E402

CFG = json.loads((HERE / "rules_v1.json").read_text())
FPS, CX = 15, 320

# Key poses in pixels: (y of nose, shoulders, hips, knees, ankles), x offsets, box
POSES = {
    "stand": dict(y=(80, 120, 220, 310, 395), box=(70, 400)),
    "sit_chair": dict(y=(160, 200, 300, 305, 395), box=(150, 400)),
    "sit_bed": dict(y=(160, 200, 300, 300, 305), box=(150, 320)),
}


def frame(name, cx=CX):
    """17 COCO points and a box for a key pose."""
    k = np.full((17, 2), np.nan)
    if name.startswith("lie"):
        base = 385 if name == "lie_floor" else 295
        xs = {0: -140, 5: -100, 6: -100, 11: 0, 12: 0, 13: 90, 14: 90, 15: 180, 16: 180}
        for i, dx in xs.items():
            k[i] = (cx + dx, base - (5 if i in (5, 6) else 0) - (10 if i == 0 else 0))
        box = (cx - 160, base - 25, cx + 200, base + 15)
    else:
        p = POSES[name]
        ny, sy, hy, ky, ay = p["y"]
        for i, (dx, y) in {0: (0, ny), 5: (-20, sy), 6: (20, sy), 11: (-12, hy), 12: (12, hy),
                           13: (-12, ky), 14: (12, ky), 15: (-12, ay), 16: (12, ay)}.items():
            k[i] = (cx + dx, y)
        box = (cx - 40, p["box"][0], cx + 40, p["box"][1])
    return k, np.array(box, float)


def sequence(steps, people=1, enter_s=0.0, seed=0):
    """steps: [(pose, seconds held), ('->', seconds of transition), ...]. Returns rule inputs."""
    rng = np.random.default_rng(seed)
    K, B = [], []
    for i, (what, secs) in enumerate(steps):
        n = int(round(secs * FPS))
        if what == "->":
            (k0, b0), (k1, b1) = frame(steps[i - 1][0]), frame(steps[i + 1][0])
            for j in range(n):
                a = (j + 1) / (n + 1)
                K.append(k0 * (1 - a) + k1 * a)
                B.append(b0 * (1 - a) + b1 * a)
        else:
            k, b = frame(what)
            K += [k] * n
            B += [b] * n
    T = len(K)
    kp = np.full((T, 3, 17, 2), np.nan)
    sc = np.zeros((T, 3, 17))
    bx = np.full((T, 3, 4), np.nan)
    kp[:, 0] = np.array(K) + rng.normal(0, 1.5, (T, 17, 2))  # a little point noise
    sc[:, 0] = np.where(np.isnan(np.array(K)[..., 0]), 0, 0.9)
    bx[:, 0] = np.array(B)
    for p in range(1, people):  # extra standing people to the side, from enter_s seconds on
        k, b = frame("stand", cx=CX + 200 * p)
        start = int(round(enter_s * FPS))
        kp[start:, p], sc[start:, p], bx[start:, p] = k, 0.9, b
    return np.arange(T) / FPS, kp, sc, bx, np.array([640, 480])


CASES = [
    ("stand, fall to the floor in 0.6 s, lie", [("stand", 2), ("->", 0.6), ("lie_floor", 3)], 1,
     dict(pred_fall=1, pred_sit_up=0, pred_stand_up=0, pred_staff=0)),
    ("stand, fall onto the bed in 0.4 s, lie", [("stand", 2), ("->", 0.4), ("lie_bed", 3)], 1,
     dict(pred_fall=1, pred_staff=0)),
    ("sit on bed, fall to the floor in 0.6 s", [("sit_bed", 2), ("->", 0.6), ("lie_floor", 3)], 1,
     dict(pred_fall=1)),
    ("sit on bed, lie down slowly (2 s)", [("sit_bed", 2), ("->", 2.0), ("lie_bed", 3)], 1,
     dict(pred_fall=0, pred_sit_up=0, pred_stand_up=0)),
    ("sit on bed, lie down at a normal pace (1.2 s)", [("sit_bed", 2), ("->", 1.2), ("lie_bed", 3)], 1,
     dict(pred_fall=0)),
    ("lie on bed, sit up (1.5 s)", [("lie_bed", 2), ("->", 1.5), ("sit_bed", 3)], 1,
     dict(pred_fall=0, pred_sit_up=1, pred_stand_up=0)),
    ("sit on chair, stand up (1 s)", [("sit_chair", 2), ("->", 1.0), ("stand", 3)], 1,
     dict(pred_fall=0, pred_sit_up=0, pred_stand_up=1)),
    ("stand, sit down on a chair quickly (0.7 s)", [("stand", 2), ("->", 0.7), ("sit_chair", 3)], 1,
     dict(pred_fall=0, pred_stand_up=0)),
    ("patient lying with a nurse standing beside", [("lie_bed", 4)], 2,
     dict(pred_fall=0, pred_staff=1)),
    ("patient lying, a nurse walks in at 2 s", [("lie_bed", 5)], 2,
     dict(pred_fall=0, pred_sit_up=0, pred_stand_up=0, pred_staff=1), 2.0),
    ("standing still", [("stand", 4)], 1,
     dict(pred_fall=0, pred_sit_up=0, pred_stand_up=0, pred_staff=0)),
]


def main():
    failures = 0
    for name, steps, people, expect, *enter in CASES:
        out = pr.evaluate_clip(*sequence(steps, people, *enter), CFG)
        if "nurse walks in" in name and "standing" in out["states"]:
            expect = {**expect, "states": "patient followed"}  # the main person must stay the patient
            out = {**out, "states": "nurse followed"}
        bad = {k: (out[k], v) for k, v in expect.items() if out[k] != v}
        failures += bool(bad)
        print(f"[{'PASS' if not bad else 'FAIL'}] {name}: fall={out['pred_fall']}({out['fall_path']}) "
              f"sit_up={out['pred_sit_up']} stand_up={out['pred_stand_up']} staff={out['pred_staff']} | {out['states']}"
              + (f" | expected {bad}" if bad else ""))
    print(f"{len(CASES) - failures} of {len(CASES)} cases behave as specified")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
