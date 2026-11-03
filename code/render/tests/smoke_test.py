"""Smoke test: can this Blender render with Eevee and Cycles in background mode?

Run: blender -b --factory-startup -P smoke_test.py -- <out_dir>
"""
import sys, time, os
import bpy

out = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out, exist_ok=True)
print("BLENDER", bpy.app.version_string)
try:
    import OpenImageIO
    print("OIIO", OpenImageIO.VERSION_STRING)
except Exception as e:
    print("OIIO missing", e)
import numpy
print("NUMPY", numpy.__version__)

sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = 640, 480
sc.render.resolution_percentage = 100
for engine in ["BLENDER_EEVEE_NEXT", "CYCLES"]:
    try:
        sc.render.engine = engine
    except Exception as e:
        print("engine fail", engine, e)
        continue
    if engine == "CYCLES":
        sc.cycles.samples = 16
        sc.cycles.device = "CPU"
    else:
        sc.eevee.taa_render_samples = 16
    sc.render.filepath = os.path.join(out, f"smoke_{engine}.png")
    for i in range(2):
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print("RENDER", engine, i, round(time.time() - t, 2), "s")
