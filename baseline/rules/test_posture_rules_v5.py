"""
Made-up scenes for rules v5's floor check: a depth picture ray-traced from simple shapes (floor,
walls, a bed, a patient made of spheres, a blanket, a bag, a chair, a kneeling nurse), seen by a
camera on the wall in front of the bed (2.2 m, aimed at the mattress centre, 127 degree wide pinhole
like the pilot's renders). No pose: the floor check must work without it.
Run: python test_posture_rules_v5.py
"""
import json
from pathlib import Path
import numpy as np
import posture_rules_v5 as p5
from test_posture_rules_v3 import camera, K, W, H, FPS

HERE = Path(__file__).parent
CFG = json.loads((HERE / "rules_v5.json").read_text(encoding="utf-8"))
C2W = camera()
BED = (-0.5, 0.5, 1.6, 3.75)  # bed footprint as marked at installation
STEP = CFG["depth_step_px"]

ROOM = [("box", (-2.1, 3.75, 0.0, 3.95, -0.05, 0.0)),        # floor slab
        ("box", (-2.1, 3.75, 3.95, 4.05, 0.0, 3.0)),         # back wall
        ("box", (-2.2, -2.1, 0.0, 3.95, 0.0, 3.0)), ("box", (3.75, 3.85, 0.0, 3.95, 0.0, 3.0)),
        ("box", (-0.45, 0.45, 1.65, 3.65, 0.0, 0.58))]       # bed with mattress top at 0.58 m


def cast(shapes):
    """Planar depth (mm) on every STEP-th pixel; other pixels 0."""
    v, u = np.mgrid[0:H:STEP, 0:W:STEP]
    dirc = np.stack([(u - K[2]) / K[0], (v - K[3]) / K[1], np.ones_like(u, float)], -1).reshape(-1, 3)
    d = dirc @ C2W[:3, :3].T
    o = C2W[:3, 3]
    best = np.full(len(d), np.inf)
    with np.errstate(divide="ignore", invalid="ignore"):
        for kind, p in shapes:
            if kind == "box":
                lo, hi = np.array(p[0::2]), np.array(p[1::2])
                t1, t2 = (lo - o) / d, (hi - o) / d
                tn, tf = np.nanmax(np.minimum(t1, t2), 1), np.nanmin(np.maximum(t1, t2), 1)
                hit = (tf >= tn) & (tf > 0)
                s = np.where(tn > 0, tn, tf)
            else:  # sphere (cx, cy, cz, r)
                c, r = np.array(p[:3]), p[3]
                oc = o - c
                b = d @ oc
                a = np.sum(d * d, 1)
                disc = b * b - a * (oc @ oc - r * r)
                hit = disc >= 0
                s = (-b - np.sqrt(np.where(hit, disc, 0))) / a
                hit &= s > 0
            best = np.where(hit & (s < best), s, best)
    out = np.zeros((H, W), np.uint16)
    out[::STEP, ::STEP] = np.where(np.isfinite(best), np.round(best * 1000), 0).reshape(u.shape).astype(np.uint16)
    return out


def body_line(x, y0, y1, z, r=0.12, n=8):
    return [("sphere", (x, y, z, r)) for y in np.linspace(y0, y1, n)]


IN_BED = body_line(0.0, 2.1, 3.4, 0.58 + 0.12)
ON_FLOOR = body_line(0.85, 2.0, 3.4, 0.12)
NEAR_BED_FLOOR = body_line(0.62, 2.0, 3.4, 0.12)
SITTING_FLOOR = [("sphere", (0.9, 2.6, 0.15, 0.14)), ("sphere", (0.9, 2.6, 0.45, 0.15)), ("sphere", (0.9, 2.6, 0.75, 0.13))] + \
                body_line(0.9, 2.0, 2.45, 0.08, r=0.08, n=5)                     # hips and trunk up, legs (16 cm thick) forward on the floor
STANDING = [("sphere", (0.9, 2.5, z, 0.13)) for z in (0.1, 0.35, 0.6, 0.85, 1.1, 1.35, 1.6)]
NURSE = [("sphere", (0.85, 2.6, 0.06, 0.07)), ("sphere", (0.85, 2.45, 0.06, 0.07)), ("sphere", (0.85, 2.75, 0.3, 0.12)),
         ("sphere", (0.85, 2.75, 0.55, 0.14)), ("sphere", (0.85, 2.75, 0.85, 0.15)), ("sphere", (0.85, 2.75, 1.15, 0.12))]
BLANKET = [("box", (0.6, 1.4, 2.0, 2.9, 0.0, 0.03))]
BAG = [("box", (0.7, 1.05, 2.4, 2.65, 0.0, 0.30))]
CHAIR = [("box", (0.8, 1.25, 2.3, 2.75, 0.42, 0.46))] + [("box", (x, x + 0.03, y, y + 0.03, 0.0, 0.42))
                                                         for x in (0.8, 1.22) for y in (2.3, 2.72)]


def clip(segments):
    """segments: list of (seconds, shapes besides the room). Returns t, depth, background (empty room), no pose."""
    frames = []
    for secs, extra in segments:
        img = cast(ROOM + extra)
        frames += [img] * int(round(secs * FPS))
    T = len(frames)
    return (np.arange(T) / FPS, np.stack(frames), cast(ROOM), np.full((T, 1, 17, 2), np.nan), np.zeros((T, 1, 17)),
            np.full((T, 1, 4), np.nan))


def run(segments):
    t, dp, bg, kp, sc, bx = clip(segments)
    out, _, area, occ = p5.evaluate_clip(t, kp, sc, bx, np.array([W, H]), dp, K, C2W, bg, BED, CFG)
    return out, area, occ


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({extra})" if extra else ""))
    return cond


def main():
    ok = True
    out, area, occ = run([(2.0, IN_BED), (4.0, ON_FLOOR)])
    ok &= check("in bed, then lying on the floor beside it: alert 1.5 to 2 s after landing (80% of a 2 s window)",
                out["pred_fall"] == 1 and "floor" in out["fall_path"] and 3.4 <= out["floor_alert_t"] <= 4.1,
                f"area {area.max():.2f} m2, bed occupied {occ[:5].mean():.2f} m2 at first, alert {out['floor_alert_t']}")
    out, _, _ = run([(2.0, IN_BED), (4.0, NEAR_BED_FLOOR)])
    ok &= check("on the floor right against the bed: alert", out["pred_fall"] == 1)
    out, _, _ = run([(2.0, IN_BED), (4.0, SITTING_FLOOR)])
    ok &= check("sitting on the floor beside an empty bed: alert (a patient on the floor)", out["pred_fall"] == 1)
    out, _, _ = run([(6.0, IN_BED)])
    ok &= check("in bed the whole time: no alert", out["pred_fall"] == 0)
    out, area, _ = run([(2.0, IN_BED), (4.0, IN_BED + BLANKET)])
    ok &= check("blanket dropped beside the bed, patient in bed: no alert", out["pred_fall"] == 0, f"area {area.max():.2f}")
    out, area, _ = run([(2.0, []), (4.0, BLANKET)])
    ok &= check("blanket on the floor beside an empty bed: no alert (too flat)", out["pred_fall"] == 0, f"area {area.max():.2f}")
    out, area, _ = run([(2.0, []), (4.0, BAG)])
    ok &= check("bag beside an empty bed: no alert (too small)", out["pred_fall"] == 0, f"area {area.max():.2f}")
    out, area, _ = run([(2.0, []), (4.0, CHAIR)])
    ok &= check("chair moved beside an empty bed: no alert (seat too high, legs thin)", out["pred_fall"] == 0, f"area {area.max():.2f}")
    out, area, occ = run([(2.0, IN_BED), (4.0, IN_BED + NURSE)])
    ok &= check("nurse kneeling beside the bed, patient in bed: no alert (bed occupied)", out["pred_fall"] == 0,
                f"area {area.max():.2f}, bed occupied {occ.min():.2f}")
    out, area, _ = run([(2.0, []), (4.0, STANDING)])
    ok &= check("someone standing beside an empty bed: no alert", out["pred_fall"] == 0, f"area {area.max():.2f}")
    print("all passed" if ok else "SOME FAILED")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
