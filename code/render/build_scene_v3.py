"""Build scene_v3.blend for clips R41 to R62: scene_v2.blend unchanged, plus a blanket, a bag, slippers and a
movable chair root. No MPFB needed.

    blender -b scene_v2.blend -P build_scene_v3.py

All new objects are made from Blender primitives and are hidden in renders unless a clip uses them.
"""
import os
import sys

import bpy
import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C          # noqa: E402
import scene_room           # noqa: E402


def blanket():
    col = scene_room._collection("BLANKET")
    b = C.BLANKET
    nu, nv = 44, 40
    verts = [(-b["w"] / 2 + b["w"] * i / (nu - 1), b["l"] * j / (nv - 1), 0.0) for j in range(nv) for i in range(nu)]
    faces = [(j * nu + i, j * nu + i + 1, (j + 1) * nu + i + 1, (j + 1) * nu + i)
             for j in range(nv - 1) for i in range(nu - 1)]
    me = bpy.data.meshes.new("BLANKET")
    me.from_pydata(verts, [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("BLANKET", me)
    col.objects.link(ob)
    mat = scene_room._material("blanket_fabric", b["colour"], roughness=0.9, noise=0.06, noise_scale=30)
    mat.use_backface_culling = False
    me.materials.append(mat)
    col.hide_render = True
    return ob


def bag():
    col = scene_room._collection("BAG")
    g = C.BAG
    m = scene_room._material("bag_leather", g["colour"], roughness=0.5)
    body = scene_room._box("BAG", (-g["lx"] / 2, g["lx"] / 2), (-g["ly"] / 2, g["ly"] / 2), (0.0, g["h"]), m, col, bevel=0.02)
    # origin at the bottom centre so the bag stands on the floor at z = 0
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.ops.mesh.primitive_torus_add(major_radius=0.07, minor_radius=0.01, location=(0, 0, g["h"]), rotation=(1.5708, 0, 0))
    handle = bpy.context.active_object
    handle.name = "BAG_handle"
    handle.data.materials.append(m)
    scene_room._move_to(handle, col)
    handle.parent = body
    col.hide_render = True
    return body


def slippers():
    col = scene_room._collection("SLIPPERS")
    s = C.SLIPPER
    m = scene_room._material("slipper_felt", s["colour"], roughness=0.8)
    for side in ("L", "R"):
        ob = scene_room._box("SLIPPER_" + side, (-s["w"] / 2, s["w"] / 2), (-s["l"] / 2, s["l"] / 2), (0.0, s["h"]), m, col,
                             bevel=0.02)
        ob.location = (0.0, 0.0, 0.0)
    col.hide_render = True


def chair_root():
    root = bpy.data.objects.new("CHAIR_ROOT", None)
    bpy.data.collections["CHAIR"].objects.link(root)
    root.location = (C.CHAIR["x"], C.CHAIR["y"], 0.0)
    bpy.context.view_layer.update()
    for ob in list(bpy.data.collections["CHAIR"].objects):
        if ob is root:
            continue
        mw = ob.matrix_world.copy()
        ob.parent = root
        ob.matrix_world = mw
    return root


def main():
    out = os.path.join(HERE, "scene_v3.blend")
    for protected in ("scene_base.blend", "scene_v2.blend"):
        if os.path.abspath(out) == os.path.abspath(os.path.join(HERE, protected)):
            raise SystemExit("refusing to overwrite " + protected)
    blanket()
    bag()
    slippers()
    chair_root()
    bpy.data.collections["CHAIR"].hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


if __name__ == "__main__":
    main()
