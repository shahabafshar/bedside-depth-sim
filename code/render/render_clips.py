"""Render the pilot clips of one scenario: colour MP4, grey infrared-like MP4, 16-bit depth PNGs, JSON.

    blender -b scene_base.blend -P render_clips.py -- --scenario E1 [--clips R02,R01] [--out-root DIR] [--work DIR]

The motion is solved once per run (animate.bake) and every clip of the
scenario is rendered from that same motion; each clip's JSON records the
motion's checksum so this can be checked. Needs only Blender 4.5 (Eevee by
default; --engine CYCLES for machines without a usable GPU).
"""
import argparse
import json
import math
import os
import shutil
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C      # noqa: E402
import scene_room       # noqa: E402
import animate          # noqa: E402
import motions          # noqa: E402
import events as EV     # noqa: E402

DEFAULT_OUT = os.path.normpath(os.path.join(HERE, "..", "..", "data"))
SAMPLES_COLOUR = 12
SAMPLES_MONO = 4


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, choices=sorted(set(motions.MOTIONS) | set(motions.MOTIONS2)),
                    help="motion id (E1, E4, E6, L1; second batch: E5, E7, E6b, L7, L9)")
    ap.add_argument("--body", default="A", choices=sorted(C.BODIES))
    ap.add_argument("--clips", default="", help="comma list; default all clips of the scenario")
    ap.add_argument("--out-root", default=DEFAULT_OUT)
    ap.add_argument("--work", default=os.path.join(HERE, "_work"))
    ap.add_argument("--engine", default="EEVEE", choices=["EEVEE", "CYCLES"])
    ap.add_argument("--cycles-device", default="CPU", choices=["CPU", "CUDA", "OPTIX"],
                    help="with --engine CYCLES: render on the CPU or an NVIDIA GPU")
    ap.add_argument("--max-frames", type=int, default=0, help="testing: render only the first N frames")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--machine", default="unspecified", help="free-text label of the computer, for the timing record")
    return ap.parse_args(argv)


# ------------------------------------------------------------------ cameras

def camera_record(cam_key):
    cam = C.CAMERAS[cam_key]
    yaw, pitch = scene_room.place_cameras(cam)
    rec = {"key": cam_key, "label": cam["label"], "position_m": list(cam["position"]), "aim_point_m": list(cam["aim"]),
           "aim_rule": cam["rule"], "yaw_deg": round(yaw, 3), "pitch_down_deg": round(pitch, 3), "roll_deg": 0.0,
           "model": "pinhole, square pixels, no lens distortion (pilot simplification)"}
    for name, hfov, vpub, res in (("colour", C.COLOUR_HFOV_PUBLISHED, C.COLOUR_VFOV_PUBLISHED, C.COLOUR_RES),
                                  ("mono", C.MONO_HFOV_PUBLISHED, C.MONO_VFOV_PUBLISHED, C.MONO_RES)):
        ob = bpy.data.objects["CAM_" + name.upper()]
        k = C.intrinsics(hfov, res)
        w2c = world_to_cv(ob)
        rec[name] = {"object": ob.name, "resolution": list(res), "hfov_deg": hfov,
                     "vfov_deg": round(C.pinhole_vfov_deg(hfov, res), 3),
                     "published_fov_deg": {"horizontal": hfov, "vertical": vpub},
                     "intrinsics_opencv": {"fx": k["fx"], "fy": k["fy"], "cx": res[0] / 2 - 0.5, "cy": res[1] / 2 - 0.5},
                     "world_to_camera_opencv_4x4": [list(map(float, r)) for r in w2c],
                     "renders": "colour MP4" if name == "colour" else "grey infrared-like MP4 and depth PNGs"}
    return rec


def world_to_cv(cam_ob):
    """4x4 world -> camera matrix in OpenCV axes (x right, y down, z forward)."""
    m = np.array(cam_ob.matrix_world.inverted())
    flip = np.diag([1.0, -1.0, -1.0, 1.0])
    return flip @ m


def project(points_w, w2c, intr):
    p = np.c_[points_w, np.ones(len(points_w))] @ w2c.T
    z = p[:, 2]
    u = intr["fx"] * p[:, 0] / z + intr["cx"]
    v = intr["fy"] * p[:, 1] / z + intr["cy"]
    return p[:, :3], u, v


# ------------------------------------------------------------------ render passes

def setup_engine(engine, cycles_device="CPU"):
    sc = bpy.context.scene
    if engine == "EEVEE":
        sc.render.engine = "BLENDER_EEVEE_NEXT"
        sc.eevee.use_fast_gi = False
        sc.eevee.shadow_resolution_scale = 0.5
    else:
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.use_denoising = True
        if cycles_device != "CPU":
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = cycles_device
            prefs.get_devices()
            for dev in prefs.devices:
                dev.use = True
            sc.cycles.device = "GPU"
    sc.render.use_motion_blur = False
    sc.render.film_transparent = False
    sc.display_settings.display_device = "sRGB"


def colour_pass(engine):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects["CAM_COLOUR"]
    sc.render.resolution_x, sc.render.resolution_y = C.COLOUR_RES
    sc.render.resolution_percentage = 100
    bpy.data.collections["LIGHTS_ROOM"].hide_render = False
    bpy.data.collections["LIGHTS_IR"].hide_render = True
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    bpy.context.view_layer.use_pass_z = False
    if engine == "EEVEE":
        sc.eevee.taa_render_samples = SAMPLES_COLOUR
        sc.eevee.use_shadows = True
    else:
        sc.cycles.samples = 32


def mono_pass(engine):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects["CAM_MONO"]
    sc.render.resolution_x, sc.render.resolution_y = C.MONO_RES
    sc.render.resolution_percentage = 100
    bpy.data.collections["LIGHTS_ROOM"].hide_render = True
    bpy.data.collections["LIGHTS_IR"].hide_render = False
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
    sc.render.image_settings.color_depth = "32"
    sc.render.image_settings.exr_codec = "ZIP"
    bpy.context.view_layer.use_pass_z = True
    if engine == "EEVEE":
        sc.eevee.taa_render_samples = SAMPLES_MONO
        sc.eevee.use_shadows = False
    else:
        sc.cycles.samples = 16


def render_frames(path_prefix, f0, f1):
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = f0, f1
    sc.render.filepath = path_prefix
    sc.render.use_file_extension = True
    t = time.time()
    bpy.ops.render.render(animation=True)
    return time.time() - t


# ------------------------------------------------------------------ post-processing (OpenImageIO, bundled with Blender)

def read_exr(path):
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(path)
    spec = inp.spec()
    names = list(spec.channelnames)
    data = inp.read_image(format=oiio.FLOAT)
    inp.close()
    data = np.asarray(data).reshape(spec.height, spec.width, spec.nchannels)

    def ch(suffix):
        for i, nm in enumerate(names):
            if nm.endswith(suffix):
                return data[:, :, i]
        raise KeyError(suffix + " not in " + str(names))
    rgb = np.stack([ch("Combined.R"), ch("Combined.G"), ch("Combined.B")], axis=2)
    z = ch("Depth.Z")
    return rgb, z


def write_png(path, arr, dtype):
    import OpenImageIO as oiio
    if arr.ndim == 2:
        arr = arr[:, :, None]          # OpenImageIO needs height x width x channels
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    nch = 1 if arr.ndim == 2 else arr.shape[2]
    spec = oiio.ImageSpec(w, h, nch, oiio.UINT16 if dtype == np.uint16 else oiio.UINT8)
    out = oiio.ImageOutput.create(path)
    out.open(path, spec)
    out.write_image(arr)
    out.close()


def srgb_encode(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def mono_post(exr_dir, grey_dir, depth_dir, clip_id, frames):
    """EXR (linear colour + depth) -> grey 8-bit PNG frames and 16-bit depth PNGs in millimetres."""
    os.makedirs(grey_dir, exist_ok=True)
    os.makedirs(depth_dir, exist_ok=True)
    stats = {"depth_min_mm": None, "depth_max_mm": None, "zero_pixels": 0}
    for f in frames:
        rgb, z = read_exr(os.path.join(exr_dir, f"m_{f:04d}.exr"))
        lum = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
        grey = np.round(srgb_encode(lum * C.IR_EXPOSURE) * 255.0).astype(np.uint8)
        write_png(os.path.join(grey_dir, f"g_{f:04d}.png"), grey, np.uint8)
        valid = np.isfinite(z) & (z > 0) & (z < 65.0)
        mm = np.zeros(z.shape, dtype=np.uint16)
        mm[valid] = np.round(z[valid] * 1000.0).astype(np.uint16)
        write_png(os.path.join(depth_dir, f"{clip_id}_depth_{f:06d}.png"), mm, np.uint16)
        v = mm[valid]
        if v.size:
            stats["depth_min_mm"] = int(v.min()) if stats["depth_min_mm"] is None else min(stats["depth_min_mm"], int(v.min()))
            stats["depth_max_mm"] = int(v.max()) if stats["depth_max_mm"] is None else max(stats["depth_max_mm"], int(v.max()))
        stats["zero_pixels"] += int((~valid).sum())
    return stats


def encode_mp4(frame_paths, out_path, res, fps):
    """H.264 MP4 from PNG frames with Blender's own FFmpeg (video sequencer), no colour transform."""
    main = bpy.context.window.scene if bpy.context.window else bpy.context.scene
    enc = bpy.data.scenes.new("ENC")
    enc.render.resolution_x, enc.render.resolution_y = res
    enc.render.resolution_percentage = 100
    enc.render.fps, enc.render.fps_base = fps, 1.0
    enc.frame_start, enc.frame_end = 0, len(frame_paths) - 1
    enc.view_settings.view_transform = "Standard"
    enc.view_settings.look = "None"
    enc.sequencer_colorspace_settings.name = "sRGB"
    ed = enc.sequence_editor_create()
    coll = ed.strips if hasattr(ed, "strips") else ed.sequences
    d = os.path.dirname(frame_paths[0])
    st = coll.new_image(name="frames", filepath=frame_paths[0], channel=1, frame_start=0)
    for p in frame_paths[1:]:
        st.elements.append(os.path.basename(p))
    st.directory = d + os.sep
    try:
        st.colorspace_settings.name = "sRGB"
    except Exception:  # noqa: BLE001
        pass
    r = enc.render
    r.image_settings.file_format = "FFMPEG"
    r.ffmpeg.format = "MPEG4"
    r.ffmpeg.codec = "H264"
    r.ffmpeg.constant_rate_factor = "HIGH"
    r.ffmpeg.ffmpeg_preset = "GOOD"
    r.ffmpeg.gopsize = fps
    r.ffmpeg.audio_codec = "NONE"
    r.use_sequencer = True
    r.filepath = out_path
    r.use_file_extension = False
    bpy.ops.render.render(animation=True, scene=enc.name)
    bpy.data.scenes.remove(enc)


def contact_sheet(clip_id, work, depth_dir, out_path, frames_pick):
    """Tiles of colour, grey and depth at a few frames (for a quick look). Depth shown as 0.5 to 6 m, near = bright."""
    import OpenImageIO as oiio

    def load(p):
        inp = oiio.ImageInput.open(p)
        sp = inp.spec()
        a = np.asarray(inp.read_image(format=oiio.FLOAT)).reshape(sp.height, sp.width, sp.nchannels)
        inp.close()
        return a

    rows = []
    for f in frames_pick:
        col = load(os.path.join(work, "colour", f"c_{f:04d}.png"))[:, :, :3]
        g = load(os.path.join(work, "grey", f"g_{f:04d}.png"))[:, :, 0]
        dm = load(os.path.join(depth_dir, f"{clip_id}_depth_{f:06d}.png"))[:, :, 0] * 65535.0 / 1000.0
        dv = np.clip(1.0 - (dm - 0.5) / 5.5, 0, 1) * (dm > 0)
        pad = np.ones((480, 640, 3), dtype=np.float32)
        g3 = pad.copy(); g3[:400] = np.repeat(g[:, :, None], 3, axis=2)
        d3 = pad.copy(); d3[:400] = np.repeat(dv[:, :, None], 3, axis=2)
        rows.append(np.concatenate([col, g3, d3], axis=1))
    sheet = np.concatenate(rows, axis=0)
    small = sheet[::2, ::2]
    write_png(out_path, np.round(np.clip(small, 0, 1) * 255).astype(np.uint8), np.uint8)


# ------------------------------------------------------------------ ground truth

def static_bvh():
    verts, polys = [], []
    cols = ["ROOM", "BED"]
    if bpy.data.collections.get("CHAIR") is not None and not bpy.data.collections["CHAIR"].hide_render:
        cols.append("CHAIR")
    for colname in cols:
        for ob in bpy.data.collections[colname].objects:
            if ob.type != "MESH":
                continue
            dg = bpy.context.evaluated_depsgraph_get()
            oe = ob.evaluated_get(dg)
            me = oe.to_mesh()
            base = len(verts)
            mw = oe.matrix_world
            verts.extend([mw @ v.co for v in me.vertices])
            polys.extend([[base + i for i in p.vertices] for p in me.polygons])
            oe.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def ground_truth(body, n_frames, second_batch=False, chair_used=False):
    """World points and contact measures for every frame (evaluated from the baked animation)."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    oe = body.body.evaluated_get(dg)
    me = oe.to_mesh()
    polys = [list(p.vertices) for p in me.polygons]
    oe.to_mesh_clear()
    out, meshes = [], []
    for f in range(n_frames):
        sc.frame_set(f)
        pts, bv = animate.joints_world(body)
        cv = body.eval_vertices(body.clothes)
        allv = np.vstack([bv, cv])
        hip = pts["hip_centre"]
        near = np.linalg.norm(allv - hip, axis=1) < animate.PELVIS_RADIUS
        x, y, z = allv[near, 0], allv[near, 1], allv[near, 2]
        inside = (np.abs(x) <= C.MATTRESS_W / 2) & (y >= C.MATTRESS_Y0) & (y <= C.MATTRESS_Y1)
        touching = inside & (z <= C.MATTRESS_TOP - animate.MATTRESS_SINK + EV.CONTACT_TOL)
        ch = C.CHAIR
        on_seat = ((np.abs(x - ch["x"]) <= ch["w"] / 2) & (np.abs(y - ch["y"]) <= ch["d"] / 2)
                   & (z <= ch["seat_top"] - C.CHAIR_SINK + EV.CONTACT_TOL) & (z > ch["seat_top"] - 0.12))
        far_from_feet = ((np.linalg.norm(allv - pts["left_ankle"], axis=1) > 0.25)
                         & (np.linalg.norm(allv - pts["right_ankle"], axis=1) > 0.25))
        extra = {"lowest_non_foot_z": round(float(allv[far_from_feet, 2].min()), 5),
                 "hips_on_chair": bool(on_seat.any() and chair_used)} if second_batch else {}
        out.append({"frame": f, "t_s": round(f / C.FPS, 4), **extra,
                    "world": {k: [round(float(c), 5) for c in v] for k, v in pts.items()},
                    "trunk_angle_deg": round(animate.trunk_angle_deg(pts), 3),
                    "hip_height_m": round(float(hip[2]), 5),
                    "hips_on_mattress": bool(touching.any()),
                    "lowest_z": round(float(allv[:, 2].min()), 5)})
        meshes.append(bv.astype(np.float32))
    return out, meshes, polys


def project_gt(gt, meshes, polys, cam_rec, bvh_static):
    names = animate.COCO17 + animate.EXTRA
    per_frame = []
    for fr, mv in zip(gt, meshes):
        body_bvh = BVHTree.FromPolygons([Vector(v) for v in mv], polys)
        W = np.array([fr["world"][k] for k in names])
        entry = {"frame": fr["frame"], "t_s": fr["t_s"]}
        for cname in ("colour", "mono"):
            c = cam_rec[cname]
            w2c = np.array(c["world_to_camera_opencv_4x4"])
            pc, u, v = project(W, w2c, c["intrinsics_opencv"])
            cam_pos = Vector(cam_rec["position_m"])
            pts = {}
            for i, k in enumerate(names):
                in_img = bool(pc[i, 2] > 0 and -0.5 <= u[i] <= c["resolution"][0] - 0.5 and -0.5 <= v[i] <= c["resolution"][1] - 0.5)
                target = Vector(W[i])
                d = target - cam_pos
                dist = d.length
                hit = bvh_static.ray_cast(cam_pos, d.normalized(), dist - 0.02)
                occ_obj = hit[0] is not None
                hb = body_bvh.ray_cast(cam_pos, d.normalized(), dist)
                self_occ = hb[0] is not None and (dist - hb[3]) > 0.15
                pts[k] = {"cam_xyz_m": [round(float(a), 5) for a in pc[i]], "uv_px": [round(float(u[i]), 3), round(float(v[i]), 3)],
                          "in_image": in_img, "hidden_by_object": occ_obj, "hidden_by_body": bool(self_occ)}
            # trunk angle as a camera sees it: hip-to-shoulder line against image "up"
            hu, hv = pts["hip_centre"]["uv_px"]; su, sv = pts["shoulder_centre"]["uv_px"]
            ang = math.degrees(math.atan2(abs(su - hu), -(sv - hv))) if (su, sv) != (hu, hv) else 0.0
            entry[cname] = {"points": pts, "image_trunk_angle_deg": round(ang, 3)}
        per_frame.append(entry)
    return per_frame


def check_projection(cam_rec):
    """Our pinhole projection must agree with Blender's own camera projection."""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    errs = []
    for cname in ("colour", "mono"):
        c = cam_rec[cname]
        ob = bpy.data.objects[c["object"]]
        sc.render.resolution_x, sc.render.resolution_y = c["resolution"]
        for p in ([0.3, 2.2, 0.6], [-1.0, 1.5, 0.2], [0.0, 3.6, 1.0], [1.2, 2.6, 1.4]):
            ndc = world_to_camera_view(sc, ob, Vector(p))
            if ndc.z <= 0:
                continue
            ub, vb = ndc.x * c["resolution"][0] - 0.5, (1 - ndc.y) * c["resolution"][1] - 0.5
            _, u, v = project(np.array([p]), np.array(c["world_to_camera_opencv_4x4"]), c["intrinsics_opencv"])
            errs.append(max(abs(ub - u[0]), abs(vb - v[0])))
    return max(errs)


def check_depth(cam_rec, depth_png, bvh_static, n=40, seed=0):
    """Rendered depth vs ray-cast distance along the optical axis at random pixels on static surfaces (frame 0)."""
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(depth_png)
    sp = inp.spec()
    mm = np.asarray(inp.read_image(format=oiio.UINT16)).reshape(sp.height, sp.width)
    inp.close()
    c = cam_rec["mono"]
    K = c["intrinsics_opencv"]
    w2c = np.array(c["world_to_camera_opencv_4x4"])
    c2w = np.linalg.inv(w2c)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n * 3):
        u, v = int(rng.integers(0, sp.width)), int(rng.integers(0, sp.height))
        d_cam = np.array([(u - K["cx"]) / K["fx"], (v - K["cy"]) / K["fy"], 1.0])
        d_w = c2w[:3, :3] @ d_cam
        o = Vector(cam_rec["position_m"])
        hit = bvh_static.ray_cast(o, Vector(d_w / np.linalg.norm(d_w)))
        if hit[0] is None:
            continue
        p_cam = w2c @ np.r_[np.array(hit[0]), 1.0]
        rendered = mm[v, u] / 1000.0
        if rendered == 0 or abs(rendered - p_cam[2]) > 0.5:   # pixel shows the person or an edge: skip
            continue
        out.append(abs(rendered - p_cam[2]))
        if len(out) >= n:
            break
    return {"pixels_checked": len(out), "median_abs_error_mm": round(float(np.median(out)) * 1000, 2) if out else None,
            "max_abs_error_mm": round(float(np.max(out)) * 1000, 2) if out else None,
            "how": "random pixels of frame 0 on room and bed surfaces; rendered depth against the distance along the "
                   "optical axis of a ray cast through the pixel centre"}


# ------------------------------------------------------------------ main

def main():
    a = parse()
    t_all = time.time()
    clips = [c for c in (a.clips.split(",") if a.clips else C.CLIPS)
             if C.clip_spec(c)[1] == a.scenario and C.clip_spec(c)[0] == a.body]
    setup_engine(a.engine, a.cycles_device)
    spec = C.BODIES[a.body]
    for bname, b in C.BODIES.items():          # only the chosen person is rendered
        col = bpy.data.collections.get(b["collection"])
        if col is not None:
            col.hide_render = (bname != a.body)
    body = animate.Body(spec["prefix"], spec["eyes"])
    second_batch = a.scenario in motions.MOTIONS2
    extras = {}
    if second_batch:
        keys, dur, scripted, extras = motions.MOTIONS2[a.scenario](body.dims)
    else:
        keys, dur, scripted = motions.MOTIONS[a.scenario]()
    chair_used = bool(extras.get("chair"))
    if bpy.data.collections.get("CHAIR") is not None:
        bpy.data.collections["CHAIR"].hide_render = not chair_used
    print("START", a.scenario, "body", a.body, "clips", clips, time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
          flush=True)
    t0 = time.time()
    rec = animate.bake(body, keys, dur, chair=chair_used)
    n = len(rec)
    ahash = animate.animation_hash(rec)
    gt, meshes, polys = ground_truth(body, n, second_batch, chair_used)
    evs = EV.compute(a.scenario, gt, scripted, animate.COCO17)
    t_bake = time.time() - t0
    worst_beside = max(r["beside_mattress_depth"] for r in rec)
    print(f"BAKED {a.scenario}: {n} frames, hash {ahash[:12]}, {t_bake:.1f} s, worst beside-mattress depth {worst_beside:.3f} m")
    print("EVENTS", json.dumps(evs["events"] or evs["phases"], indent=None)[:2000])
    bvh_static = static_bvh()
    last = n - 1 if not a.max_frames else min(n - 1, a.max_frames - 1)
    frames = list(range(0, last + 1))
    motion_rec = {"scenario": a.scenario, "body": a.body, "fps": C.FPS, "frames": n, "sha256": ahash,
                  "frames_data": [{"frame": r["frame"], "rig_location_m": [round(x, 6) for x in r["loc"]],
                                   "rig_rotation_wxyz": [round(x, 6) for x in r["rot"]],
                                   "xy_mode": r["xy"], "z_mode": r["zmode"],
                                   "bones_rotation_wxyz": {b: [round(x, 6) for x in q] for b, q in r["bones"].items()}}
                                  for r in rec]}

    for clip in clips:
        tc = time.time()
        _, motion_id, cam_key = C.clip_spec(clip)
        scen = "E6" if motion_id == "E6b" else motion_id
        t_start_utc = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        out_dir = os.path.join(a.out_root, clip)
        work = os.path.join(a.work, clip)
        for d in (out_dir, work):
            if os.path.isdir(d):
                shutil.rmtree(d)
            os.makedirs(d)
        cam_rec = camera_record(cam_key)
        proj_err = check_projection(cam_rec)
        # colour
        colour_pass(a.engine)
        t_col = render_frames(os.path.join(work, "colour", "c_"), frames[0], frames[-1])
        # mono: grey + depth
        mono_pass(a.engine)
        t_mono = render_frames(os.path.join(work, "exr", "m_"), frames[0], frames[-1])
        t1 = time.time()
        depth_dir = os.path.join(out_dir, "depth")
        dstats = mono_post(os.path.join(work, "exr"), os.path.join(work, "grey"), depth_dir, clip, frames)
        encode_mp4([os.path.join(work, "colour", f"c_{f:04d}.png") for f in frames],
                   os.path.join(out_dir, f"{clip}_colour.mp4"), C.COLOUR_RES, C.FPS)
        encode_mp4([os.path.join(work, "grey", f"g_{f:04d}.png") for f in frames],
                   os.path.join(out_dir, f"{clip}_grey.mp4"), C.MONO_RES, C.FPS)
        t_post = time.time() - t1
        dcheck = check_depth(cam_rec, os.path.join(depth_dir, f"{clip}_depth_{frames[0]:06d}.png"), bvh_static)
        gtp = project_gt([gt[f] for f in frames], [meshes[f] for f in frames], polys, cam_rec, bvh_static)
        pick = sorted(set([frames[0]] + [min(frames[-1], int(round(x)))
                                         for x in np.linspace(0, frames[-1], 5)[1:]]))
        contact_sheet(clip, work, depth_dir, os.path.join(out_dir, f"{clip}_contact_sheet.png"), pick)
        # full-size key frames: colour and grey at every event start and end (look-alike: movement start and end)
        kf = set()
        for e in evs["events"]:
            kf.update(x for x in (e["start_frame"], e["end_frame"]) if x is not None)
        for ph in evs["phases"].values():
            kf.update(x for x in (ph["start_frame"], ph["end_frame"]) if x is not None)
        kf = sorted(f for f in kf if frames[0] <= f <= frames[-1])
        os.makedirs(os.path.join(out_dir, "keyframes"), exist_ok=True)
        for f in kf:
            shutil.copy(os.path.join(work, "colour", f"c_{f:04d}.png"),
                        os.path.join(out_dir, "keyframes", f"{clip}_colour_f{f:03d}.png"))
            shutil.copy(os.path.join(work, "grey", f"g_{f:04d}.png"),
                        os.path.join(out_dir, "keyframes", f"{clip}_grey_f{f:03d}.png"))
        meta = {
            "clip_id": clip, "scenario_id": scen,
            "scenario_name": {"E1": "Sit up in bed", "E4": "Leave the bed and walk away",
                              "E6": "Slide or roll out of bed to the floor", "L1": "Turn onto the side in bed",
                              "E5": "Fall while getting out of bed (after standing and one step)",
                              "E7": "Fall from sitting on the edge",
                              "L7": "Sit on the edge then lie back down",
                              "L9": "Sit down quickly on a chair beside the bed (look-alike defined for this batch; "
                                    "not in scenarios_v0.csv)"}[scen],
            "camera_height_m": cam_rec["position_m"][2], "camera": cam_rec,
            "fps": C.FPS, "frame_count": len(frames), "duration_s": round(len(frames) / C.FPS, 4),
            "time_convention": "frame i (from 0) is shown at t = i / fps seconds; event times are frame / fps",
            "events": evs["events"], "phases": evs["phases"], "scripted_keyframe_times_s": scripted,
            "files": {"colour_mp4": f"{clip}_colour.mp4", "grey_mp4": f"{clip}_grey.mp4",
                      "depth_png": f"depth/{clip}_depth_NNNNNN.png (NNNNNN = frame)", "ground_truth": f"{clip}_ground_truth.json",
                      "motion": f"{clip}_motion.json", "contact_sheet": f"{clip}_contact_sheet.png",
                      "keyframes": f"keyframes/{clip}_colour_fNNN.png and {clip}_grey_fNNN.png at event starts and ends"},
            "depth": {"units": "millimetres, uint16", "meaning": "distance along the mono camera's optical axis (planar depth), "
                      "ideal: no noise, no holes, no minimum range; 0 = no data (no surface)",
                      "camera": "mono (infrared-sensitive) camera, same pixels as the grey video", **dstats,
                      "check_against_ray_casts": dcheck},
            "grey_image": {"what": "luminance of the scene lit only by a spot light at the camera (infrared flood light "
                                   "stand-in), no room light, black world; sRGB-encoded 8-bit",
                           "not_modelled": "940 nm reflectance (visible-light materials used), dot projector pattern, "
                                           "sensor noise, auto exposure"},
            "person": ({"body": "A", "generator": "MPFB 2.0.18 (MakeHuman), CC0 assets", "macro": C.PERSON_MACRO,
                        "skin": C.PERSON_SKIN, "clothes": C.PERSON_CLOTHES[0] + " recoloured pale blue (pyjama-like)",
                        "rig": "MPFB game_engine rig"} if a.body == "A" else
                       {"body": "B", "generator": "MPFB 2.0.18 (MakeHuman), CC0 assets", "macro": C.PERSON_B_MACRO,
                        "skin": C.PERSON_B_SKIN, "hair": C.PERSON_B_HAIR,
                        "clothes": C.PERSON_B_CLOTHES + " (CC0 Dress 01 pack) recoloured as a pale gown",
                        "rig": "MPFB game_engine rig", "description": C.BODIES["B"]["label"]}),
            "motion_sha256": ahash,
            "motion_note": "solved once per scenario and reused for every camera; identical across clips with the same scenario",
            "solver_checks": {"worst_vertex_depth_beside_mattress_m": round(worst_beside, 4),
                              "projection_agreement_px": round(proj_err, 4)},
            "render": {"engine": bpy.context.scene.render.engine, "samples_colour": SAMPLES_COLOUR,
                       "samples_mono": SAMPLES_MONO, "blender": bpy.app.version_string,
                       "seconds_colour": round(t_col, 1), "seconds_mono": round(t_mono, 1),
                       "seconds_post": round(t_post, 1), "seconds_total_clip": round(time.time() - tc, 1),
                       "machine": a.machine,
                       "bake_and_ground_truth_seconds_per_scenario": round(t_bake, 1)},
            "made": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        }
        if second_batch:
            meta.update({"motion_id": motion_id, "body": a.body, "first_stands": evs.get("first_stands"),
                         "chair_in_scene": chair_used, "scene_file": "scene_v2.blend",
                         "batch": "R23 to R40: fresh test clips for the fall rule frozen at 21:23 UTC on 2026-10-19 (v4)",
                         "render_started_utc": t_start_utc,
                         "render_finished_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())})
        with open(os.path.join(out_dir, f"{clip}_meta.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1)
        with open(os.path.join(out_dir, f"{clip}_ground_truth.json"), "w", encoding="utf-8") as fh:
            json.dump({"clip_id": clip, "coordinates": {
                "world": "metres; X right as seen from the foot-wall camera, Y towards the head of the bed, Z up, floor z = 0",
                "cam_xyz_m": "metres in OpenCV camera axes: x right, y down, z forward (along the optical axis)",
                "uv_px": "pixels, OpenCV convention: centre of the top-left pixel is (0, 0)",
                "hidden_by_object": "a ray from the camera to the point hits the bed, table or room first",
                "hidden_by_body": "the ray hits the person's own body more than 15 cm before the point (approximate)",
                "points": "17 COCO points (shoulders, elbows, wrists, hips, knees, ankles = joint centres of the rig; "
                          "nose, eyes, ears = surface vertices) plus extras"},
                "point_names": animate.COCO17 + animate.EXTRA,
                "frames": [{**g, "world": g["world"], **p} for g, p in zip([gt[f] for f in frames], gtp)]}, fh)
        with open(os.path.join(out_dir, f"{clip}_motion.json"), "w", encoding="utf-8") as fh:
            json.dump(motion_rec, fh)
        if not a.keep_work:
            shutil.rmtree(work, ignore_errors=True)
        print(f"CLIP {clip} done: colour {t_col:.0f} s, mono {t_mono:.0f} s, post {t_post:.0f} s, "
              f"total {time.time() - tc:.0f} s; depth check {dcheck['median_abs_error_mm']} mm; proj {proj_err:.4f} px; "
              f"started {t_start_utc}, finished {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}", flush=True)
    print(f"ALL DONE {a.scenario} in {time.time() - t_all:.0f} s")


if __name__ == "__main__":
    main()
