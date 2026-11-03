"""Keyframed motion for the MPFB person: joint angles, contact with bed and floor, per-frame bake, ground truth.

How a motion is described (motions.py):
  a list of keys (time in s, pose, segment options). A pose gives
    root = (yaw, back, turn) in degrees: yaw turns the body about the vertical
           (0 = facing the camera, -Y; +90 = facing the exit side, +X), back
           tilts it backwards (90 = lying on the back), turn rolls it about its
           own long axis (+90 = lying on the left side, facing +X);
    hip  = (x, y) target of the hip centre (used while the segment's xy mode is "hip");
    joints = {bone: {dof: degrees}}: anatomical angles relative to MPFB's rest
           pose (see DOFS below). Missing values are 0 (rest).
  Values are interpolated between keys in angle space with an S-shaped
  (smoothstep) easing unless the segment says "linear".

Every frame is then solved and baked:
  xy mode "hip": the hip centre follows the given path;
  xy mode "feet": both ankles stay where they were (standing up, standing);
  xy mode "stance_l"/"stance_r": that ankle stays fixed (walking, no foot sliding);
  z mode "contact": the body is lowered until it rests on what is under it
           (mattress, pillow, bed edge or floor), never through it;
  z mode "fall": free fall (9.81 m/s^2) from the last resting height, stopped
           by the same contact rule.
Keys are written for every frame, so Blender plays back exactly the solved values.
"""
import json
import math
import hashlib

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

import config as C

G = 9.81
MATTRESS_SINK = 0.015      # the body presses 1.5 cm into the mattress ...
PELVIS_SINK = 0.040        # ... and 4 cm under the pelvis, which carries most of the weight
PELVIS_RADIUS = 0.22       # vertices this close to the hip centre count as "pelvis"
HAND_SINK = 0.035          # resting hands press a little into the soft mattress and carry no weight
HAND_RADIUS = 0.15         # vertices this close to a wrist count as "hand"
MATTRESS_BAND = 0.12       # vertices deeper than this below the mattress top are "beside", not "on", the mattress

# Degrees of freedom: name -> (axis kind, expected motion of a probe for a positive angle)
#   axis kind "wx"/"wy"/"wz": rest-pose world axis; "lx": the bone's own X axis (hinge); "ly": its long axis (twist)
#   probe: ("tip", direction) = bone tip moves that way; ("front", direction) = the bone's front (-Y in rest) turns that way
LAT = {"l": +1.0, "r": -1.0}   # lateral direction (+X for the left side of the body)


def _dofs():
    d = {}
    for b in ("spine_01", "spine_02", "spine_03", "neck_01", "head"):
        d[b] = {"flex": ("wx", ("tip", (0, -1, 0))), "side": ("wy", ("tip", (1, 0, 0))),
                "twist": ("ly", ("front", (1, 0, 0)))}
    for s, lat in LAT.items():
        d[f"thigh_{s}"] = {"flex": ("wx", ("tip", (0, -1, 0))), "abd": ("wy", ("tip", (lat, 0, 0))),
                           "rot": ("ly", ("front", (-lat, 0, 0)))}
        d[f"calf_{s}"] = {"flex": ("lx", ("tip", (0, 1, 0)))}
        d[f"foot_{s}"] = {"flex": ("wx", ("tip", (0, 0, 1)))}
        d[f"clavicle_{s}"] = {"elev": ("wy", ("tip", (0, 0, 1))), "prot": ("wz", ("tip", (0, -1, 0)))}
        d[f"upperarm_{s}"] = {"flex": ("wx", ("tip", (0, -1, 0))), "abd": ("wy", ("tip", (lat, 0, 0))),
                              "rot": ("ly", ("front", (-lat, 0, 0)))}
        d[f"lowerarm_{s}"] = {"flex": ("lx", ("tip", (0, -1, 0)))}
        d[f"hand_{s}"] = {"flex": ("lx", ("tip", (0, -1, 0)))}
    return d


DOFS = _dofs()
ORDER = ("flex", "side", "abd", "elev", "prot", "twist", "rot")   # composition order, outermost first


class Body:
    """The MPFB person in the opened scene."""

    def __init__(self, prefix="PERSON", eyes="Human.low-poly"):
        self.rig = bpy.data.objects[prefix + "_RIG"]
        self.body = bpy.data.objects[prefix + "_BODY"]
        self.clothes = bpy.data.objects[prefix + "_CLOTHES"]
        self.eyes_name = eyes
        self.rig.animation_data_clear()
        self.rig.rotation_mode = "QUATERNION"
        for pb in self.rig.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
        bones = self.rig.data.bones
        self.hip_rest = (bones["thigh_l"].head_local + bones["thigh_r"].head_local) / 2.0
        head_c = (bones["head"].head_local + bones["head"].tail_local) / 2.0
        self.dims = {"hip_z": float(self.hip_rest.z), "hip_to_head_centre": float(head_c.z - self.hip_rest.z),
                     "thigh": float((bones["calf_l"].head_local - bones["thigh_l"].head_local).length),
                     "shin": float((bones["foot_l"].head_local - bones["calf_l"].head_local).length)}
        self.axes = {}
        for bname, dofs in DOFS.items():
            rest = bones[bname].matrix_local.to_3x3()
            inv = rest.transposed()
            for dof, (kind, (pkind, pdir)) in dofs.items():
                if kind[0] == "w":
                    a_world = Vector({"wx": (1, 0, 0), "wy": (0, 1, 0), "wz": (0, 0, 1)}[kind])
                elif kind == "lx":
                    a_world = rest.col[0].copy()
                else:
                    a_world = rest.col[1].copy()
                probe = rest.col[1].copy() if pkind == "tip" else Vector((0, -1, 0))
                moved = Quaternion(a_world, 0.05) @ probe - probe
                if moved.dot(Vector(pdir)) < 0:
                    a_world = -a_world
                self.axes[(bname, dof)] = (inv @ a_world).normalized()
        self.static_frame_mesh()

    def static_frame_mesh(self):
        """Indices of mesh vertices used as face points (nose, eyes, ears), found once in the rest pose."""
        self.rig.location = (0, 0, 0)
        self.rig.rotation_quaternion = (1, 0, 0, 0)
        bpy.context.view_layer.update()
        v = self.eval_vertices(self.body)
        head = (v[:, 2] > 1.50) & (v[:, 2] < 1.72)
        idx = np.where(head)[0]
        mid = idx[np.abs(v[idx, 0]) < 0.01]
        self.vid_nose = int(mid[np.argmin(v[mid, 1])])
        nose = v[self.vid_nose]
        # ears: most lateral head points within 4 cm of the nose height band, behind the nose
        band = idx[(np.abs(v[idx, 2] - (nose[2] + 0.02)) < 0.03) & (v[idx, 1] > nose[1] + 0.06)]
        self.vid_ear_l = int(band[np.argmax(v[band, 0])])
        self.vid_ear_r = int(band[np.argmin(v[band, 0])])
        eyes = bpy.data.objects.get(self.eyes_name)
        ev = self.eval_vertices(eyes)
        centres = {}
        for s, sign in (("l", 1), ("r", -1)):
            c = ev[(ev[:, 0] * sign) > 0].mean(axis=0)
            # front-most body vertex near the eye centre (eyelid surface) so it moves with the head
            d = np.linalg.norm(v[idx] - c, axis=1)
            centres[s] = int(idx[np.argmin(d)])
        self.vid_eye_l, self.vid_eye_r = centres["l"], centres["r"]

    @staticmethod
    def eval_vertices(ob):
        dg = bpy.context.evaluated_depsgraph_get()
        oe = ob.evaluated_get(dg)
        me = oe.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        oe.to_mesh_clear()
        co = co.reshape(n, 3)
        mw = np.array(oe.matrix_world)
        return co @ mw[:3, :3].T + mw[:3, 3]

    def apply_pose(self, root, joints):
        yaw, back, turn = root
        q = (Quaternion((0, 0, 1), math.radians(yaw)) @ Quaternion((1, 0, 0), math.radians(-back))
             @ Quaternion((0, 0, 1), math.radians(turn)))
        self.rig.rotation_quaternion = q
        for bname in DOFS:
            pb = self.rig.pose.bones[bname]
            vals = joints.get(bname, {})
            qb = Quaternion()
            for dof in ORDER:
                if dof in vals and abs(vals[dof]) > 1e-9:
                    qb = qb @ Quaternion(self.axes[(bname, dof)], math.radians(vals[dof]))
            pb.rotation_quaternion = qb
        return q


# ------------------------------------------------------------------ interpolation of keys

def _ease(u, kind):
    if kind == "linear":
        return u
    if kind == "in":          # accelerate
        return u * u
    if kind == "out":         # decelerate
        return 1 - (1 - u) * (1 - u)
    return u * u * (3 - 2 * u)   # smoothstep


def _flat(pose):
    out = {"root.yaw": pose["root"][0], "root.back": pose["root"][1], "root.turn": pose["root"][2]}
    if "hip" in pose:
        out["hip.x"], out["hip.y"] = pose["hip"]
    for b, dd in pose.get("joints", {}).items():
        for k, v in dd.items():
            out[f"{b}.{k}"] = v
    return out


def sample(keys, t):
    """Pose values and segment options at time t."""
    times = [k[0] for k in keys]
    if t <= times[0]:
        i, u = 0, 0.0
    elif t >= times[-1]:
        i, u = len(keys) - 2, 1.0
    else:
        i = max(j for j in range(len(keys) - 1) if times[j] <= t)
        u = (t - times[i]) / (times[i + 1] - times[i])
    a, b = _flat(keys[i][1]), _flat(keys[i + 1][1])
    opts = keys[i][2] if len(keys[i]) > 2 else {}
    e = _ease(u, opts.get("ease", "smooth"))
    names = set(a) | set(b)
    vals = {}
    for n in names:
        va, vb = a.get(n, 0.0), b.get(n, 0.0)
        if n.startswith("hip.") and (n not in a or n not in b):
            va = a.get(n, b.get(n, 0.0)); vb = b.get(n, a.get(n, 0.0))
        vals[n] = va + (vb - va) * e
    if t >= times[-1]:
        opts = keys[-1][2] if len(keys[-1]) > 2 else opts
    return vals, opts


def _unflat(vals):
    root = (vals.get("root.yaw", 0.0), vals.get("root.back", 0.0), vals.get("root.turn", 0.0))
    hip = (vals.get("hip.x"), vals.get("hip.y"))
    joints = {}
    for n, v in vals.items():
        if n.startswith("root.") or n.startswith("hip."):
            continue
        b, d = n.rsplit(".", 1)
        joints.setdefault(b, {})[d] = v
    return root, hip, joints


# ------------------------------------------------------------------ support surfaces

def support_height(x, y, z_prev, pelvis=None, hands=None, chair=False, env=None):
    """Height of what lies under each vertex. z_prev: vertex heights at the previous frame (to tell 'on' from 'beside').
    pelvis: boolean mask of vertices near the hip centre (they press deeper into the mattress)."""
    s = np.zeros_like(x)
    inside = (np.abs(x) <= C.MATTRESS_W / 2) & (y >= C.MATTRESS_Y0) & (y <= C.MATTRESS_Y1)
    on_top = inside & (z_prev > C.MATTRESS_TOP - MATTRESS_BAND)
    s[on_top] = C.MATTRESS_TOP - MATTRESS_SINK
    if pelvis is not None:
        s[on_top & pelvis] = C.MATTRESS_TOP - PELVIS_SINK
    if hands is not None:
        s[on_top & hands] = C.MATTRESS_TOP - HAND_SINK
    p = C.PILLOW
    pil = on_top & (x >= p["x"][0]) & (x <= p["x"][1]) & (y >= p["y"][0]) & (y <= p["y"][1])
    s[pil] = p["compressed_top"]
    # bed frame edge and the lowered rail on the exit side
    edge = ((x > C.MATTRESS_W / 2) & (x <= C.BED_FRAME_X + 0.03) & (y >= C.BED_FOOTBOARD_Y[1])
            & (y <= C.BED_HEADBOARD_Y[0]) & (z_prev > C.RAIL_DOWN_Z[1] - 0.05))
    s[edge] = np.maximum(s[edge], C.RAIL_DOWN_Z[1])
    env = env or {}
    if env.get("nonexit_down"):   # (third batch, F3) the -X rails lowered too
        edge2 = ((x < -C.MATTRESS_W / 2) & (x >= -C.BED_FRAME_X - 0.03) & (y >= C.BED_FOOTBOARD_Y[1])
                 & (y <= C.BED_HEADBOARD_Y[0]) & (z_prev > C.RAIL_DOWN_Z[1] - 0.05))
        s[edge2] = np.maximum(s[edge2], C.RAIL_DOWN_Z[1])
    if chair:   # seat of the chair used in L9 (clips R29, R30, R39, R40) and L12 (third batch, moved chair)
        ch = dict(C.CHAIR)
        if env.get("chair_xy") is not None:
            ch["x"], ch["y"] = env["chair_xy"]
        seat = ((np.abs(x - ch["x"]) <= ch["w"] / 2) & (np.abs(y - ch["y"]) <= ch["d"] / 2)
                & (z_prev > ch["seat_top"] - MATTRESS_BAND))
        s[seat] = ch["seat_top"] - C.CHAIR_SINK
        if pelvis is not None:
            s[seat & pelvis] = ch["seat_top"] - C.PELVIS_SINK_CHAIR
    return s, inside & ~on_top


# ------------------------------------------------------------------ bake

def _segment(keys, t):
    """Index of the key that starts the segment containing t, and the eased progress through it."""
    times = [k[0] for k in keys]
    i = max([j for j in range(len(keys) - 1) if times[j] <= t] or [0])
    u = min(1.0, max(0.0, (t - times[i]) / (times[i + 1] - times[i])))
    opts = keys[i][2] if len(keys[i]) > 2 else {}
    return i, _ease(u, opts.get("ease", "smooth"))


def bake(body, keys, duration, fps=C.FPS, chair=False, env=None):
    """Solve every frame, write keyframes, return per-frame solver records."""
    n = int(round(duration * fps)) + 1
    rig = body.rig
    rig.animation_data_clear()
    rec = []
    anchor = None        # (mode, world xy of the anchor point)
    prev = None
    z_rest = None        # last resting height (for falls)
    t_fall0 = None
    for f in range(n):
        t = f / fps
        vals, opts = sample(keys, t)
        root, hip, joints = _unflat(vals)
        q = body.apply_pose(root, joints)
        rig.location = (0, 0, 0)
        bpy.context.view_layer.update()
        R = q.to_matrix()
        verts = np.vstack([body.eval_vertices(body.body), body.eval_vertices(body.clothes)])
        bones = {b: rig.matrix_world @ rig.pose.bones[b].head for b in ("foot_l", "foot_r", "hand_l", "hand_r")}
        xy_mode = opts.get("xy", "hip")
        if xy_mode == "hip":
            hip_rel = R @ body.hip_rest
            loc_xy = np.array([hip[0] - hip_rel.x, hip[1] - hip_rel.y])
            anchor = None
        elif xy_mode == "glide":
            # (third batch) the hips move smoothly from where they actually are to the hip of the next key
            seg, ue = _segment(keys, t)
            if anchor is None or anchor[0] != ("glide", seg):
                anchor = (("glide", seg), np.array(prev["hip_xy"]))
            target = np.array(keys[seg + 1][1]["hip"])
            hxy = anchor[1] + (target - anchor[1]) * ue
            hip_rel = R @ body.hip_rest
            loc_xy = np.array([hxy[0] - hip_rel.x, hxy[1] - hip_rel.y])
        else:
            if xy_mode == "feet":
                pt = (bones["foot_l"] + bones["foot_r"]) / 2
            else:
                pt = bones["foot_" + xy_mode[-1]]
            pt = np.array([pt.x, pt.y])
            if anchor is None or anchor[0] != xy_mode:   # (a glide anchor is a tuple, so it never matches)
                # start of a planted phase: keep the anchor where it was in the previous frame
                prev_pt = prev["anchors"][xy_mode]
                anchor = (xy_mode, prev_pt)
            loc_xy = anchor[1] - pt
        w = verts.copy()
        w[:, 0] += loc_xy[0]
        w[:, 1] += loc_xy[1]
        hip_w = np.array(R @ body.hip_rest) + np.array([loc_xy[0], loc_xy[1], 0.0])
        pelvis = np.linalg.norm(w - hip_w, axis=1) < PELVIS_RADIUS
        off3 = np.array([loc_xy[0], loc_xy[1], 0.0])
        hands = np.zeros(len(w), dtype=bool)
        for hb in ("hand_l", "hand_r"):
            hands |= np.linalg.norm(w - (np.array(bones[hb]) + off3), axis=1) < HAND_RADIUS
        z_prev_v = w[:, 2] + (prev["z"] if prev else 0.30)
        chair_now = chair and t >= (env or {}).get("chair_from_s", 0.0)   # (third batch) a pulled chair supports
        s, beside = support_height(w[:, 0], w[:, 1], z_prev_v, pelvis, hands, chair_now, env)   # only once let go
        for _ in range(3):
            dz = float(np.max(s - w[:, 2]))
            s, beside = support_height(w[:, 0], w[:, 1], w[:, 2] + dz, pelvis, hands, chair_now, env)
        z_mode = opts.get("z", "contact")
        dt = 1.0 / fps
        if z_mode == "fall":
            if t_fall0 is None:
                t_fall0, z_rest = t, (prev["z"] if prev else dz)
            z_free = z_rest - 0.5 * G * (t - t_fall0) ** 2
            z = max(z_free, dz)
        elif z_mode == "drop" and prev is not None:
            # (second batch) the body follows its support while it has one; when the support gives way it
            # accelerates down from its current vertical speed (9.81 m/s^2) until something stops it
            # a support pushing the body up does not launch it: only downward speed carries over
            z_ballistic = prev["z"] + min(prev["v"], 0.0) * dt - 0.5 * G * dt * dt
            z = max(z_ballistic, dz)
            t_fall0 = None
        else:
            t_fall0 = None
            z = dz
        v_now = (z - prev["z"]) / dt if prev is not None else 0.0
        rig.location = (loc_xy[0], loc_xy[1], z)
        wz = w[:, 2] + z
        inside_depth = float(np.max((C.MATTRESS_TOP - MATTRESS_BAND) - wz[beside])) if beside.any() else 0.0
        # where each planted-point candidate is now, in the world (for the next frame)
        off = np.array([loc_xy[0], loc_xy[1]])
        fl = np.array([bones["foot_l"].x, bones["foot_l"].y]) + off
        fr = np.array([bones["foot_r"].x, bones["foot_r"].y]) + off
        anchors = {"feet": (fl + fr) / 2, "stance_l": fl, "stance_r": fr}
        rec.append(dict(frame=f, t=t, loc=(float(loc_xy[0]), float(loc_xy[1]), float(z)),
                        rot=tuple(float(c) for c in q),
                        bones={b: tuple(rig.pose.bones[b].rotation_quaternion) for b in DOFS},
                        xy=xy_mode, zmode=z_mode, contact_gap=float(z - dz),
                        min_clearance=float(np.min(wz - s)), beside_mattress_depth=max(0.0, inside_depth),
                        n_beside=int(beside.sum())))
        prev = dict(z=z, anchors=anchors, v=v_now, hip_xy=(float(hip_w[0]), float(hip_w[1])))
    # write keys for every frame
    for r in rec:
        f = r["frame"]
        rig.location = r["loc"]
        rig.rotation_quaternion = r["rot"]
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_quaternion", frame=f)
        for b, qb in r["bones"].items():
            pb = rig.pose.bones[b]
            pb.rotation_quaternion = qb
            pb.keyframe_insert("rotation_quaternion", frame=f)
    ad = rig.animation_data
    if ad and ad.action:
        for fc in _fcurves(ad.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 0, n - 1
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    return rec


def _fcurves(action):
    try:
        return list(action.fcurves)
    except Exception:  # noqa: BLE001  (layered actions, Blender 4.4+)
        out = []
        for layer in action.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out.extend(cb.fcurves)
        return out


def animation_hash(rec):
    """Checksum of the solved motion (root transform and every bone rotation, rounded to 1e-6)."""
    h = hashlib.sha256()
    for r in rec:
        vals = list(r["loc"]) + list(r["rot"]) + [c for b in sorted(r["bones"]) for c in r["bones"][b]]
        h.update(np.round(np.array(vals), 6).tobytes())
    return h.hexdigest()


# ------------------------------------------------------------------ ground truth

COCO17 = ["nose", "left_eye", "right_eye", "left_ear", "right_ear", "left_shoulder", "right_shoulder",
          "left_elbow", "right_elbow", "left_wrist", "right_wrist", "left_hip", "right_hip",
          "left_knee", "right_knee", "left_ankle", "right_ankle"]
BONE_POINTS = {"left_shoulder": "upperarm_l", "right_shoulder": "upperarm_r", "left_elbow": "lowerarm_l",
               "right_elbow": "lowerarm_r", "left_wrist": "hand_l", "right_wrist": "hand_r",
               "left_hip": "thigh_l", "right_hip": "thigh_r", "left_knee": "calf_l", "right_knee": "calf_r",
               "left_ankle": "foot_l", "right_ankle": "foot_r", "neck": "neck_01", "pelvis": "pelvis"}
EXTRA = ["head_top", "neck", "pelvis", "hip_centre", "shoulder_centre", "left_toe", "right_toe"]


def joints_world(body):
    """World positions of the 17 COCO points and extras for the current (evaluated) frame."""
    dg = bpy.context.evaluated_depsgraph_get()
    re = body.rig.evaluated_get(dg)
    mw = re.matrix_world
    pts = {}
    for name, b in BONE_POINTS.items():
        pts[name] = mw @ re.pose.bones[b].head
    pts["head_top"] = mw @ re.pose.bones["head"].tail
    pts["left_toe"] = mw @ re.pose.bones["ball_l"].tail
    pts["right_toe"] = mw @ re.pose.bones["ball_r"].tail
    v = body.eval_vertices(body.body)
    for name, vid in (("nose", body.vid_nose), ("left_eye", body.vid_eye_l), ("right_eye", body.vid_eye_r),
                      ("left_ear", body.vid_ear_l), ("right_ear", body.vid_ear_r)):
        pts[name] = Vector(v[vid])
    pts["hip_centre"] = (pts["left_hip"] + pts["right_hip"]) / 2
    pts["shoulder_centre"] = (pts["left_shoulder"] + pts["right_shoulder"]) / 2
    return {k: np.array(p[:]) for k, p in pts.items()}, v


def trunk_angle_deg(p):
    d = p["shoulder_centre"] - p["hip_centre"]
    return math.degrees(math.acos(max(-1.0, min(1.0, d[2] / np.linalg.norm(d)))))
