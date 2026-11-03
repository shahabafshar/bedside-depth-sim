"""Quick look at poses or motions: renders chosen frames from chosen cameras at low quality.

    blender -b scene_base.blend -P tests/preview.py -- --out DIR --cams foot_centre_2.2,side_1.0 --poses lying,standing
    blender -b scene_base.blend -P tests/preview.py -- --out DIR --cams foot_centre_2.2 --motion E4 --frames 0,30,60
Writes one PNG per (pose or frame, camera) and prints solver diagnostics.
"""
import argparse
import os
import sys

import bpy

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import config as C      # noqa: E402
import scene_room       # noqa: E402
import animate          # noqa: E402
import motions          # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--cams", default="foot_centre_2.2")
ap.add_argument("--poses", default="")
ap.add_argument("--motion", default="")
ap.add_argument("--frames", default="")
ap.add_argument("--samples", type=int, default=4)
ap.add_argument("--body", default="A", choices=["A", "B"])
a = ap.parse_args(argv)
os.makedirs(a.out, exist_ok=True)

sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.eevee.taa_render_samples = a.samples
sc.eevee.shadow_resolution_scale = 0.5
sc.eevee.use_fast_gi = False
sc.camera = bpy.data.objects["CAM_COLOUR"]
sc.render.resolution_x, sc.render.resolution_y = C.COLOUR_RES
bpy.data.collections["LIGHTS_IR"].hide_render = True
sc.view_settings.view_transform = "AgX"
spec = C.BODIES[a.body]
for name, b in C.BODIES.items():
    col = bpy.data.collections.get(b["collection"])
    if col is not None:
        col.hide_render = (name != a.body)
body = animate.Body(spec["prefix"], spec["eyes"])
chair_col = bpy.data.collections.get("CHAIR")
if chair_col is not None:
    chair_col.hide_render = True

jobs = []
if a.poses:
    for name in a.poses.split(","):
        p = motions.POSES[name]
        if "hip" not in p:
            p = motions.mix(p, hip=(0.9, 2.4))
        jobs.append((name, [(0.0, p, {}), (1.0, p, {})], [0]))
extras = {}
if a.motion:
    if a.motion in motions.MOTIONS:
        keys, dur, _ = motions.MOTIONS[a.motion]()
    else:
        keys, dur, _, extras = motions.MOTIONS2[a.motion](body.dims)
        if extras.get("chair") and chair_col is not None:
            chair_col.hide_render = False
    frames = [int(x) for x in a.frames.split(",")] if a.frames else list(range(0, int(dur * C.FPS) + 1, 15))
    jobs.append((a.motion, keys, frames))

for name, keys, frames in jobs:
    dur = keys[-1][0]
    rec = animate.bake(body, keys, dur, chair=bool(extras.get("chair")))
    for f in frames:
        r = rec[f]
        print(f"{name} f{f:03d} t={r['t']:.2f} loc=({r['loc'][0]:.3f},{r['loc'][1]:.3f},{r['loc'][2]:.3f}) "
              f"xy={r['xy']} z={r['zmode']} gap={r['contact_gap']:.3f} beside={r['n_beside']} "
              f"beside_depth={r['beside_mattress_depth']:.3f}")
    worst = max(rec, key=lambda r: r["beside_mattress_depth"])
    print(f"{name}: worst beside-mattress depth {worst['beside_mattress_depth']:.3f} m at frame {worst['frame']}")
    for camkey in a.cams.split(","):
        scene_room.place_cameras(C.CAMERAS[camkey])
        for f in frames:
            sc.frame_set(f)
            sc.render.filepath = os.path.join(a.out, f"{name}_{camkey}_f{f:03d}.png")
            bpy.ops.render.render(write_still=True)
