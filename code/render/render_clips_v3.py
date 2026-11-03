"""Third batch (R41 to R62): render one motion's clips with scene_v3.blend.

    blender -b scene_v3.blend -P render_clips_v3.py -- --motion F1 --people A [--clips R41] [--work DIR]
    blender -b scene_v3.blend -P render_clips_v3.py -- --motion L11 --people B+A --preview DIR --frames 0,30,60

Outputs per clip as in the first two batches, plus <id>_background_depth.png: the mono camera's depth at frame 0
with every person hidden and every object at its frame-0 position. Two-person clips (B+A): body B is the
patient in bed, body A the visitor or nurse; both get ground truth. Reuses the render and output functions of
render_clips.py.
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
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C          # noqa: E402
import animate              # noqa: E402
import motions3 as M3       # noqa: E402
import objects3 as O3       # noqa: E402
import events as EV         # noqa: E402
import render_clips as RC   # noqa: E402

ROLE = {"L11": "visitor", "L13": "nurse"}


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--motion", required=True, choices=sorted(M3.MOTIONS3))
    ap.add_argument("--people", required=True, choices=["A", "B", "B+A"])
    ap.add_argument("--clips", default="")
    ap.add_argument("--out-root", default=RC.DEFAULT_OUT)
    ap.add_argument("--work", default=os.path.join(HERE, "_work"))
    ap.add_argument("--machine", default="unspecified")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--preview", default="", help="folder: render only --frames at low quality from --cams")
    ap.add_argument("--frames", default="")
    ap.add_argument("--cams", default="foot_centre_2.2,side_1.0")
    return ap.parse_args(argv)


def mesh_world(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    polys = [list(p.vertices) for p in me.polygons]
    mw = np.array(oe.matrix_world)
    oe.to_mesh_clear()
    co = co.reshape(n, 3)
    return co @ mw[:3, :3].T + mw[:3, 3], polys


def dynamic_objects():
    obs = []
    for col in ("BLANKET", "BAG", "SLIPPERS", "CHAIR"):
        c = bpy.data.collections.get(col)
        if c is not None and not c.hide_render:
            obs += [o for o in c.objects if o.type == "MESH"]
    return obs


def static_bvh3():
    verts, polys = [], []
    for colname in ("ROOM", "BED"):
        for ob in bpy.data.collections[colname].objects:
            if ob.type != "MESH":
                continue
            v, p = mesh_world(ob)
            base = len(verts)
            verts.extend([Vector(x) for x in v])
            polys.extend([[base + i for i in q] for q in p])
    return BVHTree.FromPolygons(verts, polys)


def ground_truth3(body, n, env, other=None):
    """Per-frame world points and contact measures of one person; also the meshes of the other person and of the
    moving objects (for occlusion)."""
    sc = bpy.context.scene
    _, polys = mesh_world(body.body)
    gt, meshes, dyn = [], [], []
    ch = dict(C.CHAIR)
    if env.get("chair_xy"):
        ch["x"], ch["y"] = env["chair_xy"]
    dyn_obs = dynamic_objects()
    for f in range(n):
        sc.frame_set(f)
        pts, bv = animate.joints_world(body)
        cv = body.eval_vertices(body.clothes)
        allv = np.vstack([bv, cv])
        hip = pts["hip_centre"]
        near = np.linalg.norm(allv - hip, axis=1) < animate.PELVIS_RADIUS
        x, y, z = allv[near, 0], allv[near, 1], allv[near, 2]
        inside = (np.abs(x) <= C.MATTRESS_W / 2) & (y >= C.MATTRESS_Y0) & (y <= C.MATTRESS_Y1)
        touching = inside & (z <= C.MATTRESS_TOP - animate.MATTRESS_SINK + EV.CONTACT_TOL)
        on_seat = ((np.abs(x - ch["x"]) <= ch["w"] / 2) & (np.abs(y - ch["y"]) <= ch["d"] / 2)
                   & (z <= ch["seat_top"] - C.CHAIR_SINK + EV.CONTACT_TOL) & (z > ch["seat_top"] - 0.12))
        far = ((np.linalg.norm(allv - pts["left_ankle"], axis=1) > 0.25)
               & (np.linalg.norm(allv - pts["right_ankle"], axis=1) > 0.25))
        gt.append({"frame": f, "t_s": round(f / C.FPS, 4),
                   "lowest_non_foot_z": round(float(allv[far, 2].min()), 5),
                   "hips_on_chair": bool(on_seat.any() and bool(env.get("chair_xy"))),
                   "world": {k: [round(float(c), 5) for c in v] for k, v in pts.items()},
                   "trunk_angle_deg": round(animate.trunk_angle_deg(pts), 3),
                   "hip_height_m": round(float(hip[2]), 5),
                   "hips_on_mattress": bool(touching.any()),
                   "lowest_z": round(float(allv[:, 2].min()), 5)})
        meshes.append(bv.astype(np.float32))
        d = []
        if other is not None:
            ov, op = mesh_world(other.body)
            d.append(("person", ov.astype(np.float32), op))
        for ob in dyn_obs:
            v, p = mesh_world(ob)
            d.append(("object", v.astype(np.float32), p))
        dyn.append(d)
    return gt, meshes, polys, dyn


def project3(gt, meshes, polys, dyn, cam_rec, bvh_static):
    names = animate.COCO17 + animate.EXTRA
    out = []
    for fr, mv, dd in zip(gt, meshes, dyn):
        body_bvh = BVHTree.FromPolygons([Vector(v) for v in mv], polys)
        dyn_bvh = {}
        for kind in ("person", "object"):
            vv, pp = [], []
            for k, v, p in dd:
                if k != kind:
                    continue
                base = len(vv)
                vv.extend([Vector(x) for x in v])
                pp.extend([[base + i for i in q] for q in p])
            dyn_bvh[kind] = BVHTree.FromPolygons(vv, pp) if vv else None
        W = np.array([fr["world"][k] for k in names])
        entry = {"frame": fr["frame"], "t_s": fr["t_s"]}
        cam_pos = Vector(cam_rec["position_m"])
        for cname in ("colour", "mono"):
            c = cam_rec[cname]
            pc, u, v = RC.project(W, np.array(c["world_to_camera_opencv_4x4"]), c["intrinsics_opencv"])
            pts = {}
            for i, k in enumerate(names):
                in_img = bool(pc[i, 2] > 0 and -0.5 <= u[i] <= c["resolution"][0] - 0.5
                              and -0.5 <= v[i] <= c["resolution"][1] - 0.5)
                d = Vector(W[i]) - cam_pos
                dist, dn = d.length, d.normalized()
                occ = bvh_static.ray_cast(cam_pos, dn, dist - 0.02)[0] is not None
                if not occ and dyn_bvh["object"] is not None:
                    occ = dyn_bvh["object"].ray_cast(cam_pos, dn, dist - 0.02)[0] is not None
                occ_p = dyn_bvh["person"] is not None and dyn_bvh["person"].ray_cast(cam_pos, dn, dist - 0.02)[0] is not None
                hb = body_bvh.ray_cast(cam_pos, dn, dist)
                pts[k] = {"cam_xyz_m": [round(float(a), 5) for a in pc[i]], "uv_px": [round(float(u[i]), 3), round(float(v[i]), 3)],
                          "in_image": in_img, "hidden_by_object": bool(occ), "hidden_by_other_person": bool(occ_p),
                          "hidden_by_body": bool(hb[0] is not None and (dist - hb[3]) > 0.15)}
            hu, hv = pts["hip_centre"]["uv_px"]
            su, sv = pts["shoulder_centre"]["uv_px"]
            ang = math.degrees(math.atan2(abs(su - hu), -(sv - hv))) if (su, sv) != (hu, hv) else 0.0
            entry[cname] = {"points": pts, "image_trunk_angle_deg": round(ang, 3)}
        out.append(entry)
    return out


def render_background(clip, cam_rec, out_dir, work, engine):
    """Mono depth at frame 0 without any person (objects at their frame-0 positions)."""
    vis = {c: bpy.data.collections[c].hide_render for c in ("PERSON", "PERSON_B")}
    for c in vis:
        bpy.data.collections[c].hide_render = True
    bpy.context.scene.frame_set(0)
    RC.mono_pass(engine)
    d = os.path.join(work, "bg")
    os.makedirs(d, exist_ok=True)
    RC.render_frames(os.path.join(d, "b_"), 0, 0)
    _, z = RC.read_exr(os.path.join(d, "b_0000.exr"))
    valid = np.isfinite(z) & (z > 0) & (z < 65.0)
    mm = np.zeros(z.shape, dtype=np.uint16)
    mm[valid] = np.round(z[valid] * 1000.0).astype(np.uint16)
    path = os.path.join(out_dir, f"{clip}_background_depth.png")
    RC.write_png(path, mm, np.uint16)
    for c, h in vis.items():
        bpy.data.collections[c].hide_render = h
    return {"file": os.path.basename(path), "frame": 0, "min_mm": int(mm[valid].min()), "max_mm": int(mm[valid].max()),
            "zero_pixels": int((~valid).sum()),
            "what": "mono camera depth at frame 0 with every person hidden; every object (bed, rails, table, chair, "
                    "blanket, bag, slippers) at its frame-0 position; same format as the depth PNGs"}


def main():
    a = parse()
    t_all = time.time()
    people = a.people
    pid = people[0]
    sid = people[2] if "+" in people else None
    clips = [c for c in (a.clips.split(",") if a.clips else C.CLIPS)
             if C.clip_spec(c)[1] == a.motion and C.clip_spec(c)[0] == people]
    RC.setup_engine("EEVEE")
    changes = O3.setup_scene(a.motion, people)
    bp = animate.Body(C.BODIES[pid]["prefix"], C.BODIES[pid]["eyes"])
    bs = animate.Body(C.BODIES[sid]["prefix"], C.BODIES[sid]["eyes"]) if sid else None
    fn = M3.MOTIONS3[a.motion]
    md = fn(bp.dims, bs.dims) if bs else fn(bp.dims)
    print("START", a.motion, people, clips, time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()), flush=True)
    t0 = time.time()
    chair = "chair" in md["objects"]
    if a.motion == "L12":       # first solve: where the hands let go of the chair decides where the chair ends
        animate.bake(bp, md["keys"], md["dur"], chair=chair, env=md["env"])
        cf = O3.chair_final_from_hands(bp, md["objects"]["chair"]["release"])
        md = fn(bp.dims, chair_final=cf)
    rec = animate.bake(bp, md["keys"], md["dur"], chair=chair, env=md["env"])
    rec2 = animate.bake(bs, md["keys2"], md["dur"]) if bs else None
    n = len(rec)
    obj_info = {}
    objs = md["objects"]
    if "blanket" in objs:
        obj_info["blanket"] = O3.bake_blanket(bp, n, *objs["blanket"])
    if "bag" in objs:
        obj_info["bag"] = O3.bake_bag(bs, n, objs["bag"]["carry_until"])
    if "slippers" in objs:
        obj_info["slippers"] = O3.bake_slippers(bp, n, objs["slippers"])
    if "chair" in objs:
        c = objs["chair"]
        obj_info["chair"] = O3.bake_chair(bp, n, c["grab"], c["release"], c["final"])
    ahash = animate.animation_hash(rec)
    ahash2 = animate.animation_hash(rec2) if rec2 else None
    gt, meshes, polys, dyn = ground_truth3(bp, n, md["env"], other=bs)
    gt2 = meshes2 = polys2 = dyn2 = None
    if bs:
        gt2, meshes2, polys2, dyn2 = ground_truth3(bs, n, {}, other=bp)
    evs = EV.compute3(a.motion, md, gt, gt2, animate.COCO17)
    t_bake = time.time() - t0
    worst = max(r["beside_mattress_depth"] for r in rec)
    print(f"BAKED {a.motion} {people}: {n} frames, hash {ahash[:12]}, {t_bake:.1f} s, beside-mattress {worst:.3f} m",
          flush=True)
    print("EVENTS", json.dumps(evs["events"] or evs["phases"])[:1500], flush=True)
    print("OBJECTS", json.dumps(obj_info)[:600], flush=True)
    sc = bpy.context.scene

    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        sc.camera = bpy.data.objects["CAM_COLOUR"]
        sc.render.resolution_x, sc.render.resolution_y = C.COLOUR_RES
        bpy.data.collections["LIGHTS_IR"].hide_render = True
        bpy.data.collections["LIGHTS_ROOM"].hide_render = False
        sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
        sc.view_settings.view_transform = "AgX"
        sc.eevee.taa_render_samples = 4
        sc.render.image_settings.file_format = "PNG"
        frames = [int(x) for x in a.frames.split(",")] if a.frames else list(range(0, n, 15))
        for f in frames:
            r = rec[f]
            print(f"  f{f:03d} t={f / C.FPS:.2f} xy={r['xy']} z={r['zmode']} gap={r['contact_gap']:.3f} "
                  f"hip={gt[f]['hip_height_m']:.3f} low_nf={gt[f]['lowest_non_foot_z']:.3f} on_mat={gt[f]['hips_on_mattress']}"
                  + (f" | 2nd hip={gt2[f]['hip_height_m']:.3f}" if gt2 else ""))
        for camkey in a.cams.split(","):
            RC.scene_room.place_cameras(C.CAMERAS[camkey])
            for f in frames:
                sc.frame_set(f)
                sc.render.filepath = os.path.join(a.preview, f"{a.motion}_{people.replace('+', '')}_{camkey}_f{f:03d}.png")
                bpy.ops.render.render(write_still=True)
        return

    bvh_static = static_bvh3()
    frames = list(range(n))
    motion_rec = {"motion": a.motion, "people": people, "fps": C.FPS, "frames": n, "sha256": ahash,
                  "sha256_second_person": ahash2,
                  "frames_data": [{"frame": r["frame"], "rig_location_m": [round(x, 6) for x in r["loc"]],
                                   "rig_rotation_wxyz": [round(x, 6) for x in r["rot"]], "xy_mode": r["xy"],
                                   "z_mode": r["zmode"],
                                   "bones_rotation_wxyz": {b: [round(x, 6) for x in q] for b, q in r["bones"].items()}}
                                  for r in rec]}
    for clip in clips:
        tc = time.time()
        t_start_utc = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        _, _, cam_key = C.clip_spec(clip)
        out_dir = os.path.join(a.out_root, clip)
        work = os.path.join(a.work, clip)
        for d in (out_dir, work):
            if os.path.isdir(d):
                shutil.rmtree(d)
            os.makedirs(d)
        cam_rec = RC.camera_record(cam_key)
        proj_err = RC.check_projection(cam_rec)
        bg = render_background(clip, cam_rec, out_dir, work, "EEVEE")
        RC.colour_pass("EEVEE")
        t_col = RC.render_frames(os.path.join(work, "colour", "c_"), 0, n - 1)
        RC.mono_pass("EEVEE")
        t_mono = RC.render_frames(os.path.join(work, "exr", "m_"), 0, n - 1)
        t1 = time.time()
        depth_dir = os.path.join(out_dir, "depth")
        dstats = RC.mono_post(os.path.join(work, "exr"), os.path.join(work, "grey"), depth_dir, clip, frames)
        RC.encode_mp4([os.path.join(work, "colour", f"c_{f:04d}.png") for f in frames],
                      os.path.join(out_dir, f"{clip}_colour.mp4"), C.COLOUR_RES, C.FPS)
        RC.encode_mp4([os.path.join(work, "grey", f"g_{f:04d}.png") for f in frames],
                      os.path.join(out_dir, f"{clip}_grey.mp4"), C.MONO_RES, C.FPS)
        t_post = time.time() - t1
        dcheck = RC.check_depth(cam_rec, os.path.join(depth_dir, f"{clip}_depth_000000.png"), bvh_static)
        gtp = project3(gt, meshes, polys, dyn, cam_rec, bvh_static)
        gtp2 = project3(gt2, meshes2, polys2, dyn2, cam_rec, bvh_static) if gt2 else None
        # look-alike L15: when the person has left the mono camera's view
        extra = {}
        if a.motion == "L15":
            gone = [all(not p["in_image"] for k, p in e["mono"]["points"].items() if k in animate.COCO17) for e in gtp]
            fgone = next((i for i in range(n) if all(gone[i:])), None)
            extra["leaves_mono_view"] = dict(frame=fgone, t_s=None if fgone is None else round(fgone / C.FPS, 4),
                                             rule="first frame from which none of the 17 COCO points is inside the mono "
                                                  "image for the rest of the clip")
        hidden = {}
        for cname in ("colour", "mono"):
            last = gtp[-1][cname]["points"]
            hidden[cname] = sum(1 for k in animate.COCO17 if last[k]["hidden_by_object"] or not last[k]["in_image"])
        pick = sorted(set([0] + [min(n - 1, int(round(x))) for x in np.linspace(0, n - 1, 5)[1:]]))
        RC.contact_sheet(clip, work, depth_dir, os.path.join(out_dir, f"{clip}_contact_sheet.png"), pick)
        kf = set()
        for e in evs["events"]:
            kf.update(x for x in (e["start_frame"], e["end_frame"], e.get("first_floor_touch_frame")) if x is not None)
        for ph in evs["phases"].values():
            kf.update(x for x in (ph.get("start_frame"), ph.get("end_frame")) if x is not None)
        kf = sorted(f for f in kf if 0 <= f < n)
        os.makedirs(os.path.join(out_dir, "keyframes"), exist_ok=True)
        for f in kf:
            shutil.copy(os.path.join(work, "colour", f"c_{f:04d}.png"), os.path.join(out_dir, "keyframes", f"{clip}_colour_f{f:03d}.png"))
            shutil.copy(os.path.join(work, "grey", f"g_{f:04d}.png"), os.path.join(out_dir, "keyframes", f"{clip}_grey_f{f:03d}.png"))
        person = lambda b: {"body": b, "description": C.BODIES[b]["label"],
                            "macro": C.PERSON_MACRO if b == "A" else C.PERSON_B_MACRO}
        meta = {
            "clip_id": clip, "scenario_id": a.motion, "motion_id": a.motion,
            "closest_scenario_in_scenarios_v0": M3.CLOSEST_SCENARIO[a.motion],
            "kind": "fall" if a.motion.startswith("F") else "look-alike (no fall; nobody lies or sits on the floor)",
            "people": people,
            "person": dict(person(pid), role="patient" if sid else "patient (the only person)"),
            "second_person": dict(person(sid), role=ROLE[a.motion]) if sid else None,
            "camera_height_m": cam_rec["position_m"][2], "camera": cam_rec,
            "bed_rect_m": C.BED_RECT_M,
            "bed_rect_note": "outer footprint of the bed seen from above, x0, x1, y0, y1 in room coordinates: side rails at "
                             "x +/-0.53 (frame and boards end at +/-0.50), footboard front at y 1.60, headboard back at "
                             "y 3.80; the same in every clip (rails lowered or not)",
            "fps": C.FPS, "frame_count": n, "duration_s": round(n / C.FPS, 4),
            "time_convention": "frame i (from 0) is shown at t = i / fps seconds; event times are frame / fps",
            "events": evs["events"], "phases": evs["phases"], "first_stands": evs["first_stands"],
            "min_hip_height_m": evs["min_hip_height_m"],
            "min_hip_height_second_person_m": evs.get("min_hip_height_second_person_m"),
            "hips_on_mattress_every_frame": evs.get("hips_on_mattress_every_frame"),
            "view": extra, "scripted_keyframe_times_s": md["scripted"],
            "scene_changes_for_this_clip": changes, "objects": obj_info,
            "coco_points_hidden_or_outside_at_last_frame": hidden,
            "files": {"colour_mp4": f"{clip}_colour.mp4", "grey_mp4": f"{clip}_grey.mp4",
                      "depth_png": f"depth/{clip}_depth_NNNNNN.png (NNNNNN = frame)",
                      "background_depth_png": f"{clip}_background_depth.png",
                      "ground_truth": f"{clip}_ground_truth.json", "motion": f"{clip}_motion.json",
                      "contact_sheet": f"{clip}_contact_sheet.png",
                      "keyframes": f"keyframes/{clip}_colour_fNNN.png and {clip}_grey_fNNN.png at event starts, floor "
                                   f"touches and ends (look-alikes: movement starts and ends)"},
            "background_depth": bg,
            "depth": {"units": "millimetres, uint16", "meaning": "distance along the mono camera's optical axis (planar "
                      "depth), ideal: no noise, no holes, no minimum range; 0 = no data (no surface)", **dstats,
                      "check_against_ray_casts": dcheck},
            "grey_image": {"what": "luminance of the scene lit only by a spot light at the camera; sRGB-encoded 8-bit",
                           "not_modelled": "940 nm reflectance, dot pattern, sensor noise, auto exposure"},
            "motion_sha256": ahash, "motion_sha256_second_person": ahash2,
            "solver_checks": {"worst_vertex_depth_beside_mattress_m": round(worst, 4),
                              "projection_agreement_px": round(proj_err, 4)},
            "render": {"engine": sc.render.engine, "samples_colour": RC.SAMPLES_COLOUR, "samples_mono": RC.SAMPLES_MONO,
                       "blender": bpy.app.version_string, "seconds_colour": round(t_col, 1),
                       "seconds_mono": round(t_mono, 1), "seconds_post": round(t_post, 1),
                       "seconds_total_clip": round(time.time() - tc, 1), "machine": a.machine,
                       "bake_and_ground_truth_seconds": round(t_bake, 1)},
            "scene_file": "scene_v3.blend",
            "batch": "R41 to R62: test clips for rules v5 (depth-only floor check) frozen at 2026-10-20 01:19 UTC",
            "render_started_utc": t_start_utc,
            "render_finished_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "made": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        }
        with open(os.path.join(out_dir, f"{clip}_meta.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1)
        gt_doc = {"clip_id": clip, "coordinates": {
            "world": "metres; X right as seen from the foot-wall camera, Y towards the head of the bed, Z up, floor z = 0",
            "cam_xyz_m": "metres in OpenCV camera axes: x right, y down, z forward",
            "uv_px": "pixels, OpenCV convention: centre of the top-left pixel is (0, 0)",
            "hidden_by_object": "a ray from the camera to the point hits the room, the bed, the table or a moving object "
                                "(blanket, bag, slippers, chair) first",
            "hidden_by_other_person": "the ray hits the other person first (two-person clips)",
            "hidden_by_body": "the ray hits the person's own body more than 15 cm before the point (approximate)"},
            "point_names": animate.COCO17 + animate.EXTRA,
            "person": {"body": pid, "role": "patient"},
            "frames": [{**g, **p} for g, p in zip(gt, gtp)]}
        if gt2:
            gt_doc["second_person"] = {"body": sid, "role": ROLE[a.motion],
                                       "frames": [{**g, **p} for g, p in zip(gt2, gtp2)]}
        with open(os.path.join(out_dir, f"{clip}_ground_truth.json"), "w", encoding="utf-8") as fh:
            json.dump(gt_doc, fh)
        with open(os.path.join(out_dir, f"{clip}_motion.json"), "w", encoding="utf-8") as fh:
            json.dump(motion_rec, fh)
        if not a.keep_work:
            shutil.rmtree(work, ignore_errors=True)
        print(f"CLIP {clip} done: colour {t_col:.0f} s, mono {t_mono:.0f} s, post {t_post:.0f} s, total "
              f"{time.time() - tc:.0f} s; depth check {dcheck['median_abs_error_mm']} mm; proj {proj_err:.4f} px; "
              f"started {t_start_utc}, finished {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}", flush=True)
    print(f"ALL DONE {a.motion} {people} in {time.time() - t_all:.0f} s", flush=True)


if __name__ == "__main__":
    main()
