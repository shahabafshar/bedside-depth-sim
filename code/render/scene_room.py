"""Builds the hospital room, the bed, the lights and the two cameras from Blender primitives.

Imported by build_scene.py (inside Blender). No external assets.
"""
import math
import bpy
from mathutils import Vector, Euler

import config as C


def _material(name, rgb, roughness=0.6, metallic=0.0, noise=0.0, noise_scale=40.0):
    """A plain Principled material; optional low-contrast noise so flat surfaces are not perfectly uniform."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if noise > 0:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = noise_scale
        tex.inputs["Detail"].default_value = 4.0
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*[c * (1 - noise) for c in rgb], 1.0)
        ramp.color_ramp.elements[1].color = (*[min(1.0, c * (1 + noise)) for c in rgb], 1.0)
        nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def _box(name, x, y, z, mat, collection, bevel=0.0):
    """Axis-aligned box from (min, max) ranges."""
    cx, cy, cz = (x[0] + x[1]) / 2, (y[0] + y[1]) / 2, (z[0] + z[1]) / 2
    sx, sy, sz = x[1] - x[0], y[1] - y[0], z[1] - z[0]
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = "ANGLE"
        bpy.ops.object.shade_smooth()
        try:
            bpy.ops.object.shade_auto_smooth()
        except Exception:
            pass
    ob.data.materials.append(mat)
    _move_to(ob, collection)
    return ob


def _cyl(name, x, y, z0, z1, r, mat, collection):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=z1 - z0, location=(x, y, (z0 + z1) / 2), vertices=16)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    _move_to(ob, collection)
    return ob


def _move_to(ob, collection):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    collection.objects.link(ob)


def _collection(name):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


def build_room():
    room = _collection("ROOM")
    m_floor = _material("floor_vinyl", (0.30, 0.28, 0.25), roughness=0.45, noise=0.05, noise_scale=6)
    m_wall = _material("wall_paint", (0.60, 0.61, 0.57), roughness=0.85, noise=0.03)
    m_wall_accent = _material("wall_accent", (0.45, 0.55, 0.58), roughness=0.85)
    m_ceiling = _material("ceiling", (0.80, 0.80, 0.78), roughness=0.9)
    m_frame = _material("bed_frame", (0.62, 0.64, 0.66), roughness=0.35, metallic=0.4)
    m_plastic = _material("bed_plastic", (0.78, 0.78, 0.75), roughness=0.5)
    m_mattress = _material("mattress_sheet", (0.80, 0.82, 0.84), roughness=0.8, noise=0.04, noise_scale=120)
    m_pillow = _material("pillow", (0.86, 0.87, 0.88), roughness=0.85)
    m_rail = _material("bed_rail", (0.70, 0.72, 0.74), roughness=0.4, metallic=0.3)
    m_wood = _material("wood_table", (0.45, 0.32, 0.20), roughness=0.55, noise=0.15, noise_scale=8)
    m_door = _material("door", (0.55, 0.42, 0.28), roughness=0.5, noise=0.08, noise_scale=6)
    m_dark = _material("wheel_rubber", (0.05, 0.05, 0.05), roughness=0.7)

    x0, x1, y0, y1, zt = C.ROOM_X_MIN, C.ROOM_X_MAX, C.ROOM_Y_MIN, C.ROOM_Y_MAX, C.ROOM_Z_MAX
    t = 0.10
    _box("floor", (x0 - t, x1 + t), (y0 - t, y1 + t), (-t, 0.0), m_floor, room)
    _box("ceiling", (x0 - t, x1 + t), (y0 - t, y1 + t), (zt, zt + t), m_ceiling, room)
    _box("wall_back", (x0 - t, x1 + t), (y1, y1 + t), (0.0, zt), m_wall, room)
    _box("wall_camera", (x0 - t, x1 + t), (y0 - t, y0), (0.0, zt), m_wall, room)
    _box("wall_left", (x0 - t, x0), (y0, y1), (0.0, zt), m_wall, room)
    _box("wall_right", (x1, x1 + t), (y0, y1), (0.0, zt), m_wall, room)
    # a coloured band behind the bed head (typical headwall panel) and skirting
    _box("headwall_panel", (-1.0, 1.0), (y1 - 0.02, y1), (0.9, 1.6), m_wall_accent, room)
    _box("door", (x1 - 0.03, x1), C.DOOR["y"], (0.0, C.DOOR["h"]), m_door, room)

    bed = _collection("BED")
    fx = C.BED_FRAME_X
    deck_top = C.MATTRESS_TOP - C.MATTRESS_T
    # frame under the mattress
    _box("bed_frame", (-fx + 0.02, fx - 0.02), (C.BED_FOOTBOARD_Y[1], C.BED_HEADBOARD_Y[0]),
         (deck_top - 0.10, deck_top), m_frame, bed, bevel=0.01)
    _box("bed_base", (-0.35, 0.35), (2.0, 3.4), (0.12, 0.22), m_frame, bed)
    for (xx, yy) in [(-0.40, 1.85), (0.40, 1.85), (-0.40, 3.55), (0.40, 3.55)]:
        _cyl("bed_leg", xx, yy, 0.08, deck_top - 0.10, 0.025, m_frame, bed)
        _cyl("bed_wheel", xx, yy, 0.0, 0.08, 0.05, m_dark, bed)
    mat = _box("mattress", (-C.MATTRESS_W / 2, C.MATTRESS_W / 2), (C.MATTRESS_Y0, C.MATTRESS_Y1),
               (deck_top, C.MATTRESS_TOP), m_mattress, bed, bevel=0.04)
    _box("footboard", (-fx, fx), C.BED_FOOTBOARD_Y, (deck_top - 0.12, C.FOOTBOARD_TOP), m_plastic, bed, bevel=0.02)
    _box("headboard", (-fx, fx), C.BED_HEADBOARD_Y, (deck_top - 0.12, C.HEADBOARD_TOP), m_plastic, bed, bevel=0.02)
    pil = _box("pillow", C.PILLOW["x"], C.PILLOW["y"], (C.MATTRESS_TOP, C.PILLOW["top"]), m_pillow, bed, bevel=0.05)
    # side rails: up on -X, down on the exit side (+X)
    for i, (ry0, ry1) in enumerate(C.RAIL_SEGMENTS_Y):
        _box(f"rail_up_{i}", (-fx - 0.03, -fx), (ry0, ry1), C.RAIL_UP_Z, m_rail, bed, bevel=0.01)
        _box(f"rail_down_{i}", (fx, fx + 0.03), (ry0, ry1), C.RAIL_DOWN_Z, m_rail, bed, bevel=0.01)
    bt = C.BEDSIDE_TABLE
    _box("bedside_table", (bt["x"] - bt["w"] / 2, bt["x"] + bt["w"] / 2), (bt["y"] - bt["d"] / 2, bt["y"] + bt["d"] / 2),
         (0.0, bt["h"]), m_wood, bed, bevel=0.01)
    # a cup on the table so the table reads as a table
    _cyl("cup", bt["x"] + 0.08, bt["y"] - 0.05, bt["h"], bt["h"] + 0.10, 0.035, m_plastic, bed)
    return room, bed


def build_chair():
    """A plain chair (seat, backrest, four legs) beside the bed on the exit side; collection CHAIR."""
    ch = C.CHAIR
    col = _collection("CHAIR")
    m_seat = _material("chair_seat", (0.25, 0.32, 0.40), roughness=0.6)
    m_leg = _material("chair_frame", (0.55, 0.56, 0.58), roughness=0.35, metallic=0.5)
    x0, x1 = ch["x"] - ch["w"] / 2, ch["x"] + ch["w"] / 2
    y0, y1 = ch["y"] - ch["d"] / 2, ch["y"] + ch["d"] / 2
    _box("chair_seat", (x0, x1), (y0, y1), (ch["seat_top"] - 0.06, ch["seat_top"]), m_seat, col, bevel=0.015)
    _box("chair_back", (x0, x1), (y1 - 0.04, y1), (ch["seat_top"] + 0.05, ch["back_top"]), m_seat, col, bevel=0.015)
    for (xx, yy) in [(x0 + 0.03, y0 + 0.03), (x1 - 0.03, y0 + 0.03), (x0 + 0.03, y1 - 0.03), (x1 - 0.03, y1 - 0.03)]:
        _cyl("chair_leg", xx, yy, 0.0, ch["seat_top"] - 0.06, 0.015, m_leg, col)
    for (xx) in (x0 + 0.03, x1 - 0.03):
        _cyl("chair_back_post", xx, y1 - 0.02, ch["seat_top"], ch["back_top"], 0.012, m_leg, col)
    return col


def build_lights():
    """Room lights (colour pass) and the infrared flood light at the camera (grey pass)."""
    lights = _collection("LIGHTS_ROOM")
    for name, loc, size, power in [("ceiling_bed", (0.0, 2.6, C.ROOM_Z_MAX - 0.02), (1.2, 0.6), 110.0),
                                   ("ceiling_entry", (0.9, 0.9, C.ROOM_Z_MAX - 0.02), (0.6, 0.6), 45.0)]:
        ld = bpy.data.lights.new(name, "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size
        ld.energy = power
        ld.color = (1.0, 0.97, 0.92)
        ld.use_shadow_jitter = True     # soft shadows that converge over samples instead of grain
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        lights.objects.link(ob)
    ir = _collection("LIGHTS_IR")
    ld = bpy.data.lights.new("ir_flood", "SPOT")
    ld.energy = C.IR_LIGHT_POWER_W
    ld.spot_size = math.radians(C.IR_SPOT_DEG)
    ld.spot_blend = 0.4
    ld.shadow_soft_size = 0.02
    # The light sits at the lens, so its shadows fall behind objects as seen from the camera;
    # switching them off changes almost nothing in the image and halves the render time.
    ld.use_shadow = False
    ld.color = (1.0, 1.0, 1.0)
    ob = bpy.data.objects.new("ir_flood", ld)
    ir.objects.link(ob)
    return lights, ir


def build_cameras():
    cams = _collection("CAMERAS")
    out = {}
    for name, hfov, res in [("CAM_COLOUR", C.COLOUR_HFOV_PUBLISHED, C.COLOUR_RES),
                            ("CAM_MONO", C.MONO_HFOV_PUBLISHED, C.MONO_RES)]:
        cd = bpy.data.cameras.new(name)
        cd.type = "PERSP"
        cd.sensor_fit = "HORIZONTAL"
        cd.sensor_width = 36.0
        cd.angle = math.radians(hfov)
        cd.clip_start = 0.05
        cd.clip_end = 30.0
        ob = bpy.data.objects.new(name, cd)
        cams.objects.link(ob)
        out[name] = ob
    return out


def look_at_angles(position, aim):
    """Yaw (degrees, 0 = looking along +Y, positive towards +X) and pitch (degrees below horizontal)."""
    d = Vector(aim) - Vector(position)
    yaw = math.degrees(math.atan2(d.x, d.y))
    pitch = math.degrees(math.atan2(-d.z, math.hypot(d.x, d.y)))
    return yaw, pitch


def place_cameras(cam):
    """Put both cameras and the infrared light at cam['position'], looking at cam['aim'], with zero roll."""
    yaw, pitch = look_at_angles(cam["position"], cam["aim"])
    # Blender cameras look along their local -Z with +Y up. X rotation (90 - pitch) turns the view to +Y and
    # tilts it down by `pitch`; Z rotation (-yaw) then turns it towards +X. Roll stays zero.
    rot = Euler((math.radians(90.0 - pitch), 0.0, math.radians(-yaw)), "XYZ")
    for name in ("CAM_COLOUR", "CAM_MONO", "ir_flood"):
        ob = bpy.data.objects[name]
        ob.location = cam["position"]
        ob.rotation_mode = "XYZ"
        ob.rotation_euler = rot
    bpy.context.view_layer.update()
    return yaw, pitch


def setup_world():
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.75, 0.77, 0.80, 1.0)
    bg.inputs["Strength"].default_value = 0.35
    return w
