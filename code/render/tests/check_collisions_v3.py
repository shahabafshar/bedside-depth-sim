"""Third batch: does any person pass through the bed, rails, boards, table, chair, walls or floor, or through the
other person, in any frame?

    blender -b scene_v3.blend -P tests/check_collisions_v3.py -- A:F1 B:F1 B+A:L11 ...

Same box test as check_collisions.py (allowed press: mattress 5 cm, pillow 8 cm, chair seat 4 cm), with the
F3 set-up (rails lowered, table moved) and the chair at its position in every frame (L12). For two-person clips
it also reports the smallest distance between the two people's meshes.
"""
import os
import sys

import bpy
import numpy as np
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import config as C      # noqa: E402
import animate          # noqa: E402
import motions3 as M3   # noqa: E402
import objects3 as O3   # noqa: E402

ALLOW = {"mattress": 0.05, "pillow": 0.08, "chair_seat": 0.04}
TOL = 0.01


def boxes(names_skip, cols):
    out = []
    for col in cols:
        for ob in bpy.data.collections[col].objects:
            if ob.type != "MESH" or ob.name.startswith(names_skip):
                continue
            mw = ob.matrix_world
            co = np.array([mw @ v.co for v in ob.data.vertices])
            out.append((ob.name, co.min(axis=0), co.max(axis=0)))
    return out


SKIP = ("bed_leg", "bed_wheel", "cup", "floor", "ceiling", "wall", "headwall", "door", "chair_leg", "chair_back_post")
token = sys.argv[sys.argv.index("--") + 1]
people, motion = token.split(":")
O3.setup_scene(motion, people)
pid, sid = people[0], (people[2] if "+" in people else None)
bp = animate.Body(C.BODIES[pid]["prefix"], C.BODIES[pid]["eyes"])
bs = animate.Body(C.BODIES[sid]["prefix"], C.BODIES[sid]["eyes"]) if sid else None
fn = M3.MOTIONS3[motion]
md = fn(bp.dims, bs.dims) if bs else fn(bp.dims)
chair = "chair" in md["objects"]
if motion == "L12":
    animate.bake(bp, md["keys"], md["dur"], chair=chair, env=md["env"])
    md = fn(bp.dims, chair_final=O3.chair_final_from_hands(bp, md["objects"]["chair"]["release"]))
rec = animate.bake(bp, md["keys"], md["dur"], chair=chair, env=md["env"])
if bs:
    animate.bake(bs, md["keys2"], md["dur"])
n = len(rec)
if chair:
    c = md["objects"]["chair"]
    O3.bake_chair(bp, n, c["grab"], c["release"], c["final"])
worst = {}
min_gap = None
for body, label in ((bp, "person"), (bs, "second")):
    if body is None:
        continue
    for f in range(n):
        bpy.context.scene.frame_set(f)
        bx = boxes(SKIP, ["BED", "ROOM"] + (["CHAIR"] if chair else []))
        v = np.vstack([body.eval_vertices(body.body), body.eval_vertices(body.clothes)])
        for name, lo, hi in bx:
            inside = np.all((v > lo) & (v < hi), axis=1)
            if not inside.any():
                continue
            vi = v[inside]
            depth = np.min(np.stack([vi - lo, hi - vi], axis=2).min(axis=2), axis=1)
            key = name.split(".")[0]
            allow = next((a for k, a in ALLOW.items() if key.startswith(k)), 0.0)
            # the chair is pulled by the hands, and while being pulled the hands grip its front edge
            if key.startswith("chair") and label == "person" and f < int(round(md["objects"]["chair"]["release"] * C.FPS)):
                allow = max(allow, 0.03)
            d = float(depth.max())
            if d > allow + TOL and d > worst.get((label, key), (0, 0))[0]:
                worst[(label, key)] = (d, f)
        walls = max(C.ROOM_X_MIN - v[:, 0].min(), v[:, 0].max() - C.ROOM_X_MAX, C.ROOM_Y_MIN - v[:, 1].min(),
                    v[:, 1].max() - C.ROOM_Y_MAX, -v[:, 2].min())
        if walls > TOL and walls > worst.get((label, "walls_or_floor"), (0, 0))[0]:
            worst[(label, "walls_or_floor")] = (float(walls), f)
        if label == "second":
            bpy.context.scene.frame_set(f)
            vp = bp.eval_vertices(bp.body)
            kd = KDTree(len(vp))
            for i, p in enumerate(vp):
                kd.insert(p, i)
            kd.balance()
            vs = bs.eval_vertices(bs.body)[::7]
            g = min(kd.find(p)[2] for p in vs)
            min_gap = g if min_gap is None else min(min_gap, g)
msg = ", ".join(f"{l}/{k} {d * 100:.1f} cm (frame {f})" for (l, k), (d, f) in sorted(worst.items())) or "none beyond the allowed press"
print(f"COLLISIONS {token}: {msg}" + (f"; smallest distance between the two people {min_gap * 100:.1f} cm" if min_gap is not None else ""))
