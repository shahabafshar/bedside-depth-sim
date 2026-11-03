"""
Made-up movements for rules v3: bodies placed in 3D, seen by a camera on the wall in front of
the bed (2.2 m high, aimed at the mattress centre, 127 degree wide pinhole like the pilot's
renders), with a depth picture made to match. Run: python test_posture_rules_v3.py
"""
import json
from pathlib import Path
import numpy as np
import posture_rules as pr
import posture_rules_v3 as p3

HERE = Path(__file__).parent
CFG = json.loads((HERE / "rules_v3.json").read_text(encoding="utf-8"))
CFG1 = json.loads((HERE / "rules_v1.json").read_text(encoding="utf-8"))
W, H, FPS = 640, 400, 15
K = (159.546, 159.546, 319.5, 199.5)


def camera(pos=(0.0, 0.05, 2.2), aim=(0.0, 2.7, 0.58)):
    """cam_to_world 4x4 (OpenCV camera axes) for a camera at pos looking at aim, room z up."""
    pos, aim = np.array(pos, float), np.array(aim, float)
    z = aim - pos
    z /= np.linalg.norm(z)
    x = np.cross(z, [0, 0, 1.0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, pos
    return M


C2W = camera()
W2C = np.linalg.inv(C2W)


def body(hip, trunk, thigh, side=(1.0, 0, 0)):
    """COCO-17 points (room coordinates) for hips at `hip`, trunk and thigh along the given directions."""
    hip, trunk, thigh, side = (np.array(v, float) for v in (hip, trunk, thigh, side))
    trunk, thigh = trunk / np.linalg.norm(trunk), thigh / np.linalg.norm(thigh)
    P = np.full((17, 3), np.nan)
    sho = hip + 0.5 * trunk
    P[pr.LHIP], P[pr.RHIP] = hip + 0.13 * side, hip - 0.13 * side
    P[pr.LSHO], P[pr.RSHO] = sho + 0.2 * side, sho - 0.2 * side
    P[pr.NOSE] = sho + 0.25 * trunk
    knee = hip + 0.45 * thigh
    P[pr.LKNEE], P[pr.RKNEE] = knee + 0.1 * side, knee - 0.1 * side
    return P


def frame(P):
    """Project the points and make a depth picture: far wall at 4.5 m, a 9x9 patch per point."""
    pts = [p for p in P if np.all(np.isfinite(p))]
    depth = np.full((H, W), 4500, np.uint16)
    k = np.full((17, 2), np.nan)
    for j, p in enumerate(P):
        if not np.all(np.isfinite(p)):
            continue
        c = (W2C @ np.append(p, 1))[:3]
        u, v = K[0] * c[0] / c[2] + K[2], K[1] * c[1] / c[2] + K[3]
        k[j] = (u, v)
        x, y = int(round(u)), int(round(v))
        depth[max(0, y - 4):y + 5, max(0, x - 4):x + 5] = int(round(c[2] * 1000))
    s = np.where(np.isfinite(k[:, 0]), 0.9, 0.0)
    box = np.array([np.nanmin(k[:, 0]) - 20, np.nanmin(k[:, 1]) - 20, np.nanmax(k[:, 0]) + 20, np.nanmax(k[:, 1]) + 20])
    return k, s, box, depth


def clip(poses):
    """poses: list of (seconds, function of the time within the segment returning the points)."""
    frames = []
    for secs, make in poses:
        n = int(round(secs * FPS))
        frames += [frame(make(i / max(1, n - 1))) for i in range(n)]
    T = len(frames)
    t = np.arange(T) / FPS
    kp = np.stack([f[0] for f in frames])[:, None]
    sc = np.stack([f[1] for f in frames])[:, None]
    bx = np.stack([f[2] for f in frames])[:, None]
    dp = np.stack([f[3] for f in frames])
    return t, kp, sc, bx, dp


LYING_BED = lambda a: body((0, 2.6, 0.68), (0, 1, 0), (0, -1, 0))          # on the back, head away from the camera
SITTING_BED = lambda a: body((0, 2.9, 0.68), (0, 0, 1), (0, -1, 0))        # sitting up in bed, legs forward
EDGE = lambda a: body((0.45, 2.5, 0.62), (0, 0, 1), (1, 0, 0))             # sitting on the bed edge
STANDING = lambda a: body((0.85, 2.5, 0.92), (0, 0, 1), (0, 0, -1))
FLOOR = lambda a: body((1.0, 2.5, 0.12), (0, 1, 0), (0, -1, 0))            # lying on the floor beside the bed


def run(poses):
    t, kp, sc, bx, dp = clip(poses)
    out, f = p3.evaluate_clip(t, kp, sc, bx, np.array([W, H]), dp, K, C2W, CFG)
    return out, f, (t, kp, sc, bx)


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    return cond


def main():
    ok = True
    out, f, (t, kp, sc, bx) = run([(2.0, LYING_BED), (2.5, SITTING_BED)])
    ok &= check("lying in bed, seen from the foot: v3 says lying (3D trunk angle near 90)", out["share_lying"] > 0.3 and np.nanmedian(f["trunk_deg"][:20]) > 80)
    v1 = pr.evaluate_clip(t, kp, sc, bx, np.array([W, H]), CFG1)
    ok &= check("the same lying patient: v1's image angle calls it upright (no lying), the failure v3 fixes", v1["share_lying"] == 0)
    ok &= check("lying then sitting up in bed: sit-up detected", out["pred_sit_up"] == 1 and out["pred_fall"] == 0)
    out, _, _ = run([(2.0, EDGE), (2.0, STANDING)])
    ok &= check("sitting on the edge then standing: stand-up detected, no fall", out["pred_stand_up"] == 1 and out["pred_fall"] == 0)
    out, _, _ = run([(1.5, STANDING), (3.0, FLOOR)])
    ok &= check("standing then on the floor: fall", out["pred_fall"] == 1 and abs(out["pred_fall_t"] - 1.5) < 0.2)
    out, _, _ = run([(2.0, LYING_BED), (3.0, FLOOR)])
    ok &= check("rolling out of bed onto the floor: fall", out["pred_fall"] == 1)
    out, _, _ = run([(5.0, LYING_BED)])
    ok &= check("lying in bed the whole time: no fall, no sit-up", out["pred_fall"] == 0 and out["pred_sit_up"] == 0)
    slow = lambda a: body((0.85, 2.5, 0.92 - 0.77 * a), (0, 0, 1), (0, 0, -1))  # hips lowered over 6 s
    out, _, _ = run([(1.0, STANDING), (6.0, slow), (3.0, lambda a: body((0.85, 2.5, 0.15), (0, 0, 1), (0, 0, -1)))])
    ok &= check("lowering slowly to the floor over 6 s: not a fall", out["pred_fall"] == 0)
    out, _, _ = run([(1.5, STANDING), (0.6, FLOOR), (3.0, STANDING)])
    ok &= check("touching the floor for 0.6 s and up again: not a fall", out["pred_fall"] == 0)
    print("all passed" if ok else "SOME FAILED")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
