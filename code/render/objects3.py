"""Third batch: per-clip scene set-up and the animation of extra objects (blanket, bag, slippers, chair).

All object motion is computed from the already solved people (animate.bake) and keyed on every frame,
so the render, the ground truth and the background depth all see the same positions.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

import config as C

G = 9.81


def set_visible(collection, visible):
    col = bpy.data.collections.get(collection)
    if col is not None:
        col.hide_render = not visible


def setup_scene(motion_id, people):
    """Collections shown for this motion, and the F3 changes (rails lowered on -X, table moved). Returns a record."""
    changes = {}
    set_visible("PERSON", "A" in people)
    set_visible("PERSON_B", "B" in people)
    set_visible("CHAIR", motion_id == "L12")
    set_visible("BLANKET", motion_id == "L10")
    set_visible("BAG", motion_id == "L11")
    set_visible("SLIPPERS", motion_id == "L14")
    if motion_id == "F3":
        for name in ("rail_up_0", "rail_up_1"):
            ob = bpy.data.objects[name]
            h = C.RAIL_UP_Z[1] - C.RAIL_UP_Z[0]
            ob.location.z = C.RAIL_DOWN_Z[1] - h / 2.0      # top at the lowered height (0.42 m)
        for name in ("bedside_table", "cup"):
            bpy.data.objects[name].location.x += C.TABLE_SHIFT_F3
        changes = {"non_exit_side_rails": "lowered (top 0.42 m), like the exit-side rails",
                   "bedside_table_moved_x_m": C.TABLE_SHIFT_F3,
                   "bedside_table_centre_m": [C.BEDSIDE_TABLE["x"] + C.TABLE_SHIFT_F3, C.BEDSIDE_TABLE["y"]]}
    if motion_id == "L12":
        changes = {"chair": "starts near the head end beside the bed and is pulled towards the foot end"}
    bpy.context.view_layer.update()
    return changes


def _ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


# ------------------------------------------------------------------ blanket

def _blur(a, sigma):
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    a = np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, mode="valid"), 0, a)
    a = np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, mode="valid"), 1, a)
    return a


def _heightfield(verts, cell=0.025):
    xs = np.arange(-C.MATTRESS_W / 2, C.MATTRESS_W / 2 + 1e-6, cell)
    ys = np.arange(C.MATTRESS_Y0, C.MATTRESS_Y1 + 1e-6, cell)
    H = np.full((len(xs), len(ys)), C.MATTRESS_TOP)
    ix = np.floor((verts[:, 0] - xs[0]) / cell).astype(int)
    iy = np.floor((verts[:, 1] - ys[0]) / cell).astype(int)
    ok = (ix >= 0) & (ix < len(xs)) & (iy >= 0) & (iy < len(ys)) & (verts[:, 2] > C.MATTRESS_TOP - 0.1)
    np.maximum.at(H, (ix[ok], iy[ok]), verts[ok, 2])
    # spread the bumps a little (a blanket bridges between body parts), then smooth
    from numpy.lib.stride_tricks import sliding_window_view
    Hp = np.pad(H, 2, mode="edge")
    H = sliding_window_view(Hp, (5, 5)).max(axis=(2, 3))
    H = _blur(H, 1.5)
    return xs, ys, H


def _sample_h(xs, ys, H, x, y):
    fx = np.clip((x - xs[0]) / (xs[1] - xs[0]), 0, len(xs) - 1.001)
    fy = np.clip((y - ys[0]) / (ys[1] - ys[0]), 0, len(ys) - 1.001)
    i, j = fx.astype(int), fy.astype(int)
    a, b = fx - i, fy - j
    return (H[i, j] * (1 - a) * (1 - b) + H[i + 1, j] * a * (1 - b) + H[i, j + 1] * (1 - a) * b
            + H[i + 1, j + 1] * a * b)


def _drape(u, v, d, hf):
    """Blanket vertex positions for material coordinates u (across) and v (along), slid by d towards +X."""
    xs, ys, H = hf
    thk = C.BLANKET["thickness"]
    edge = C.MATTRESS_W / 2
    p = u + d
    y = C.BLANKET["y0"] + v
    x = np.empty_like(p)
    z = np.empty_like(p)
    top = (p >= -edge) & (p <= edge)
    x[top] = p[top]
    z[top] = _sample_h(xs, ys, H, p[top], y[top]) + thk
    left = p < -edge
    s = -edge - p[left]
    x[left] = -edge - 0.015
    z[left] = np.maximum(C.MATTRESS_TOP + thk - s, C.MATTRESS_TOP - C.MATTRESS_T + 0.01)
    right = p > edge
    s = p[right] - edge
    rail_x = C.BED_FRAME_X + 0.045                      # just outside the lowered rail
    rail_top = C.RAIL_DOWN_Z[1] + thk
    la = math.hypot(rail_x - edge, C.MATTRESS_TOP + thk - rail_top)
    xa = np.where(s < la, edge + (rail_x - edge) * s / la, rail_x)
    za = np.where(s < la, C.MATTRESS_TOP + thk - (C.MATTRESS_TOP + thk - rail_top) * s / la, rail_top - (s - la))
    floor = s > la + rail_top - thk
    s2 = s - la - (rail_top - thk)
    xa = np.where(floor, rail_x + 0.02 + 0.55 * s2, xa)
    za = np.where(floor, thk + 0.028 * np.abs(np.sin(s2 * 9.0 + y[right] * 3.0)), za)
    x[right] = xa
    z[right] = za
    return np.stack([x, y, z], axis=1)


def bake_blanket(patient, n_frames, t0, t1, d_end=1.95):
    """Shape key per frame: the blanket drapes over the patient and slides off the exit side to the floor."""
    ob = bpy.data.objects["BLANKET"]
    me = ob.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    uv = co.reshape(-1, 3)[:, :2].copy()                # basis mesh stores (u, v) in x, y
    if me.shape_keys:
        ob.shape_key_clear()
    basis = ob.shape_key_add(name="Basis", from_mix=False)
    sc = bpy.context.scene
    states = []
    for f in range(n_frames):
        t = f / C.FPS
        sc.frame_set(f)
        vb = np.vstack([patient.eval_vertices(patient.body), patient.eval_vertices(patient.clothes)])
        hf = _heightfield(vb)
        d = 0.0 if t <= t0 else d_end * _ease((t - t0) / (t1 - t0)) ** 1.3
        states.append(_drape(uv[:, 0], uv[:, 1], d, hf))
    basis.data.foreach_set("co", states[0].ravel())
    me.vertices.foreach_set("co", states[0].ravel())
    prev = states[0]
    keys = []
    for f in range(1, n_frames):
        if np.abs(states[f] - prev).max() < 5e-4 and keys:
            states[f] = prev
            keys.append(keys[-1])
            continue
        kb = ob.shape_key_add(name=f"f{f:03d}", from_mix=False)
        kb.data.foreach_set("co", states[f].ravel())
        keys.append(kb)
        prev = states[f]
    # key values: exactly one shape (or the basis) active on every frame
    blocks = {k.name: k for k in me.shape_keys.key_blocks if k.name != "Basis"}
    active = [None] + [k.name for k in keys]
    for name, kb in blocks.items():
        for f in range(n_frames):
            kb.value = 1.0 if active[f] == name else 0.0
            kb.keyframe_insert("value", frame=f)
    return {"slide_starts_s": t0, "on_floor_s": t1, "slide_m": d_end, "vertices": len(me.vertices)}


# ------------------------------------------------------------------ attached rigid objects

def _bone_world(body, name):
    dg = bpy.context.evaluated_depsgraph_get()
    re = body.rig.evaluated_get(dg)
    pb = re.pose.bones[name]
    return re.matrix_world @ pb.matrix


def bake_bag(visitor, n_frames, carry_until):
    """The bag hangs from the visitor's right hand until carry_until, then drops (if needed) and stays on the floor."""
    ob = bpy.data.objects["BAG"]
    ob.rotation_mode = "XYZ"
    sc = bpy.context.scene
    placed, z, v = None, None, 0.0
    on_floor_f = None
    for f in range(n_frames):
        t = f / C.FPS
        sc.frame_set(f)
        if placed is None:
            m = _bone_world(visitor, "hand_r")
            grip = m.translation + m.col[1].xyz.normalized() * 0.07      # palm
            yaw = math.atan2(-(visitor.rig.matrix_world.to_3x3() @ Vector((0, -1, 0))).x,
                             (visitor.rig.matrix_world.to_3x3() @ Vector((0, -1, 0))).y)
            loc = Vector((grip.x, grip.y, max(0.0, grip.z - 0.04 - C.BAG["h"])))
            if t >= carry_until:
                placed = Vector(loc)
                z = loc.z
                rot_z = yaw
        if placed is not None:
            if z > 0.0:
                v -= G / C.FPS
                z = max(0.0, z + v / C.FPS)
            loc = Vector((placed.x, placed.y, z))
            yaw = rot_z
        if on_floor_f is None and placed is not None and z <= 0.0:
            on_floor_f = f
        ob.location = loc
        ob.rotation_euler = (0.0, 0.0, yaw)
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
    return {"released_s": carry_until, "on_floor_frame": on_floor_f,
            "on_floor_s": None if on_floor_f is None else round(on_floor_f / C.FPS, 4),
            "floor_position_m": [round(placed.x, 3), round(placed.y, 3)] if placed is not None else None}


def _foot_frame(body, side):
    m = _bone_world(body, "foot_" + side)
    ball = _bone_world(body, "ball_" + side)
    ankle = m.translation
    toe = ball.translation + ball.col[1].xyz.normalized() * 0.06
    fwd = (toe - ankle).normalized()
    lat = m.col[0].xyz.normalized()
    up = lat.cross(fwd).normalized()
    if up.z < 0:
        up = -up
    lat = fwd.cross(up).normalized()
    centre = ankle + (toe - ankle) * 0.45 - up * 0.065
    rot = Matrix((lat, fwd, up)).transposed()
    return centre, rot


def bake_slippers(body, n_frames, times):
    """Each slipper lies on the floor under the foot until it is put on (times[side] = (start, end) in s);
    it then moves onto the foot and follows it."""
    sc = bpy.context.scene
    frames = {}
    for f in range(n_frames):
        sc.frame_set(f)
        frames[f] = {s: _foot_frame(body, s) for s in ("l", "r")}
    out = {}
    for side in ("l", "r"):
        ob = bpy.data.objects["SLIPPER_" + side.upper()]
        ob.rotation_mode = "QUATERNION"
        t0, t1 = times[side]
        f0 = int(round(t0 * C.FPS))
        c0, r0 = frames[f0][side]
        yaw = math.atan2(r0.col[1].x, r0.col[1].y)
        floor_loc = Vector((c0.x, c0.y, 0.0))
        floor_rot = Matrix.Rotation(-yaw, 3, "Z")
        for f in range(n_frames):
            t = f / C.FPS
            c, r = frames[f][side]
            if t <= t0:
                loc, q = floor_loc, floor_rot.to_quaternion()
            elif t >= t1:
                loc, q = c, r.to_quaternion()
            else:
                u = _ease((t - t0) / (t1 - t0))
                loc = floor_loc.lerp(c, u)
                q = floor_rot.to_quaternion().slerp(r.to_quaternion(), u)
            ob.location = loc
            ob.rotation_quaternion = q
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("rotation_quaternion", frame=f)
        out[side] = {"on_floor_at_m": [round(floor_loc.x, 3), round(floor_loc.y, 3)], "put_on_s": [t0, t1]}
    return out


def hands_xy(body):
    a = _bone_world(body, "hand_l").translation
    b = _bone_world(body, "hand_r").translation
    return np.array([(a.x + b.x) / 2, (a.y + b.y) / 2])


def chair_final_from_hands(body, release_t):
    """Where the pulled chair ends: its front edge at the hands when they let go (centre half a seat depth beyond)."""
    bpy.context.scene.frame_set(int(round(release_t * C.FPS)))
    h = hands_xy(body)
    return (round(float(h[0]), 4), round(float(h[1] + C.CHAIR["d"] / 2 + 0.03), 4))


def bake_chair(body, n_frames, grab_t, release_t, final_xy):
    """The chair moves with the hands between grab and release and ends at final_xy (CHAIR_ROOT empty)."""
    root = bpy.data.objects["CHAIR_ROOT"]
    sc = bpy.context.scene
    fg, fr = int(round(grab_t * C.FPS)), int(round(release_t * C.FPS))
    sc.frame_set(fr)
    h_rel = hands_xy(body)
    offset = np.array(final_xy) - h_rel
    sc.frame_set(fg)
    start = hands_xy(body) + offset
    for f in range(n_frames):
        if f <= fg:
            xy = start
        elif f >= fr:
            xy = np.array(final_xy)
        else:
            sc.frame_set(f)
            xy = hands_xy(body) + offset
        root.location = (float(xy[0]), float(xy[1]), 0.0)
        root.keyframe_insert("location", frame=f)
    return {"start_m": [round(float(start[0]), 3), round(float(start[1]), 3)],
            "final_m": [round(final_xy[0], 3), round(final_xy[1], 3)], "grab_s": grab_t, "release_s": release_t}
