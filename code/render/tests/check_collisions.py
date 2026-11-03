"""Does the person pass through the bed, rails, boards, table, chair, walls or floor in any frame?

    blender -b scene_base.blend -P tests/check_collisions.py -- E1 E4 E6 L1
    blender -b scene_v2.blend  -P tests/check_collisions.py -- A:E5 A:E7 A:L7 A:L9 B:E5 B:E7 B:E6b B:L7 B:L9

For every frame of each motion, tests all body and clothes vertices against the
boxes of the room and bed (axis-aligned bounds of each box object), and the
chair when the motion uses it. The mattress, pillow and chair seat are soft in
the motion solver, so only vertices deeper than the allowed press (mattress
5 cm, pillow 8 cm, seat 4 cm) count there. Prints the worst depth per object.
"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import config as C      # noqa: E402
import animate          # noqa: E402
import motions          # noqa: E402

ALLOW = {"mattress": 0.05, "pillow": 0.08, "chair_seat": 0.04}
TOL = 0.01


def boxes(with_chair):
    out = []
    cols = ["BED", "ROOM"] + (["CHAIR"] if with_chair else [])
    for col in cols:
        for ob in bpy.data.collections[col].objects:
            if ob.type != "MESH" or ob.name.startswith(("bed_leg", "bed_wheel", "cup", "floor", "ceiling", "wall",
                                                        "headwall", "door", "chair_leg", "chair_back_post")):
                continue
            co = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
            out.append((ob.name, co.min(axis=0), co.max(axis=0)))
    return out


for token in sys.argv[sys.argv.index("--") + 1:]:
    body_id, s = token.split(":") if ":" in token else ("A", token)
    spec = C.BODIES[body_id]
    body = animate.Body(spec["prefix"], spec["eyes"])
    if s in motions.MOTIONS:
        keys, dur, _ = motions.MOTIONS[s]()
        extras = {}
    else:
        keys, dur, _, extras = motions.MOTIONS2[s](body.dims)
    chair = bool(extras.get("chair"))
    rec = animate.bake(body, keys, dur, chair=chair)
    bx = boxes(chair)
    worst = {}
    for f in range(len(rec)):
        bpy.context.scene.frame_set(f)
        v = np.vstack([body.eval_vertices(body.body), body.eval_vertices(body.clothes)])
        for name, lo, hi in bx:
            inside = np.all((v > lo) & (v < hi), axis=1)
            if not inside.any():
                continue
            vi = v[inside]
            depth = np.min(np.stack([vi - lo, hi - vi], axis=2).min(axis=2), axis=1)   # distance to nearest face
            key = name.split(".")[0]
            allow = next((a for k, a in ALLOW.items() if key.startswith(k)), 0.0)
            d = float(depth.max())
            if d > allow + TOL and d > worst.get(key, (0, 0))[0]:
                worst[key] = (d, f)
        walls = max(C.ROOM_X_MIN - v[:, 0].min(), v[:, 0].max() - C.ROOM_X_MAX, C.ROOM_Y_MIN - v[:, 1].min(),
                    v[:, 1].max() - C.ROOM_Y_MAX, -v[:, 2].min())
        if walls > TOL and walls > worst.get("walls_or_floor", (0, 0))[0]:
            worst["walls_or_floor"] = (float(walls), f)
    print(f"COLLISIONS {body_id}:{s}: " + (", ".join(f"{k} {d * 100:.1f} cm (frame {f})" for k, (d, f) in sorted(worst.items()))
                                          or "none beyond the allowed press"))
