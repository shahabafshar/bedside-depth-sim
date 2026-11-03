"""
Made-up movements for rules v4, with the depth on the body's surface: each point's depth is taken
0.12 m in front of the joint along the camera's line of sight (the renders showed the camera sees
the surface, not the joint). Same camera and bodies as test_posture_rules_v3.py.
Run: python test_posture_rules_v4.py
"""
import json
from pathlib import Path
import numpy as np
import test_posture_rules_v3 as t3
import posture_rules_v4 as p4

HERE = Path(__file__).parent
CFG = json.loads((HERE / "rules_v4.json").read_text(encoding="utf-8"))
SURFACE = 0.12
ORIGINAL_FRAME = t3.frame  # kept before run() swaps t3.frame for the surface version


def frame(P):
    k, s, box, _ = ORIGINAL_FRAME(P)
    depth = np.full((t3.H, t3.W), 4500, np.uint16)
    for j, p in enumerate(P):
        if not np.all(np.isfinite(p)):
            continue
        c = (t3.W2C @ np.append(p, 1))[:3]
        z = c[2] * (1 - SURFACE / np.linalg.norm(c))  # the surface in front of the joint, on the same ray
        x, y = int(round(k[j, 0])), int(round(k[j, 1]))
        depth[max(0, y - 4):y + 5, max(0, x - 4):x + 5] = int(round(z * 1000))
    return k, s, box, depth


def run(poses):
    t3.frame = frame  # the v3 helpers build clips through t3.frame
    t, kp, sc, bx, dp = t3.clip(poses)
    out, f = p4.evaluate_clip(t, kp, sc, bx, np.array([t3.W, t3.H]), dp, t3.K, t3.C2W, CFG)
    return out, f


CHAIR = lambda a: t3.body((1.0, 2.2, 0.48), (0, 0, 1), (0, -1, 0))  # sitting on a chair beside the bed


def main():
    ok, chk = True, t3.check
    out, f = run([(2.0, t3.LYING_BED), (3.0, t3.FLOOR)])
    ok &= chk("surface depth: lying in bed measures above 0.5 m, on the floor below it", np.nanmedian(f["hip_h"][:20]) > 0.6 and np.nanmedian(f["hip_h"][-20:]) < 0.5)
    ok &= chk("sliding out of bed onto the floor: fall", out["pred_fall"] == 1)
    out, _ = run([(1.5, t3.STANDING), (3.0, t3.FLOOR)])
    ok &= chk("standing then on the floor: fall", out["pred_fall"] == 1 and abs(out["pred_fall_t"] - 1.5) < 0.3)
    out, _ = run([(1.5, t3.STANDING), (3.0, CHAIR)])
    ok &= chk("standing then sitting down quickly on a chair: not a fall", out["pred_fall"] == 0)
    out, _ = run([(5.0, t3.LYING_BED)])
    ok &= chk("lying in bed the whole time: no fall", out["pred_fall"] == 0)
    slow = lambda a: t3.body((0.85, 2.5, 0.92 - 0.77 * a), (0, 0, 1), (0, 0, -1))
    out, _ = run([(1.0, t3.STANDING), (6.0, slow), (3.0, lambda a: t3.body((0.85, 2.5, 0.15), (0, 0, 1), (0, 0, -1)))])
    ok &= chk("lowering slowly to the floor over 6 s: not a fall", out["pred_fall"] == 0)
    out, _ = run([(1.5, t3.STANDING), (0.6, t3.FLOOR), (3.0, t3.STANDING)])
    ok &= chk("touching the floor for 0.6 s and up again: not a fall", out["pred_fall"] == 0)
    out, _ = run([(2.0, t3.LYING_BED), (2.5, t3.SITTING_BED)])
    ok &= chk("sit-up still found (posture is v3's)", out["pred_sit_up"] == 1 and out["pred_fall"] == 0)
    out, _ = run([(2.0, t3.EDGE), (2.0, t3.STANDING)])
    ok &= chk("stand-up still found", out["pred_stand_up"] == 1 and out["pred_fall"] == 0)
    t3.frame = ORIGINAL_FRAME
    print("all passed" if ok else "SOME FAILED")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
