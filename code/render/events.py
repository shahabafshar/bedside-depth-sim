"""Event times for each scenario, measured frame by frame from the rendered person (ground truth).

Every rule below turns a definition in scenarios_v0.csv into a test on the
ground-truth body. The time of an event is the first frame (counted from 0)
at which its test holds, divided by the frame rate. Scripted times (the
keyframes in motions.py) are reported alongside as a check.
"""
import numpy as np

import config as C

CONTACT_TOL = 0.015      # a vertex touches the mattress when no more than 1.5 cm above its pressed surface
STILL_STEP = 0.005       # "still": no ground-truth point moves more than 5 mm between frames (7.5 cm/s)
EDGE_X = C.MATTRESS_W / 2.0   # the mattress edge on the exit side


def _first(mask, start=0):
    idx = np.where(mask[start:])[0]
    return int(idx[0] + start) if len(idx) else None


def _still_from(pts_all):
    """First frame from which every later frame is still (all points move < STILL_STEP)."""
    step = np.max(np.linalg.norm(np.diff(pts_all, axis=0), axis=2), axis=1)   # per frame transition
    moving = np.concatenate([[False], step > STILL_STEP])
    last_moving = np.where(moving)[0]
    return int(last_moving[-1]) if len(last_moving) else 0, step


def signals(gt, coco):
    """Per-frame measures from ground truth: gt is a list of dicts with world points and hip-contact flags."""
    names = coco
    P = np.array([[f["world"][n] for n in names] for f in gt])          # frames x 17 x 3
    hip = np.array([f["world"]["hip_centre"] for f in gt])
    sho = np.array([f["world"]["shoulder_centre"] for f in gt])
    trunk = np.array([f["trunk_angle_deg"] for f in gt])
    hips_on_mattress = np.array([f["hips_on_mattress"] for f in gt])
    return P, hip, sho, trunk, hips_on_mattress


def frame_time(f, fps=C.FPS):
    return None if f is None else round(f / fps, 4)


def ev(name, start_f, end_f, start_def, end_def, start_rule, end_rule, fps=C.FPS, **extra):
    d = dict(scenario=name, start_frame=start_f, start_s=frame_time(start_f, fps),
             end_frame=end_f, end_s=frame_time(end_f, fps),
             start_definition=start_def, end_definition=end_def,
             start_rule=start_rule, end_rule=end_rule)
    d.update(extra)
    return d


def compute(scenario, gt, scripted, coco, fps=C.FPS):
    P, hip, sho, trunk, on_mat = signals(gt, coco)
    n = len(gt)
    out = {"events": [], "phases": {}, "scripted_s": scripted}
    still_f, step = _still_from(P)

    def sit_up(window_end_s=None):
        z0 = sho[0, 2]
        s = _first(sho[:, 2] > z0 + 0.01)
        # upright = trunk within 2 degrees of the seated angle reached at the end of the sit-up
        up = None
        if s is not None:
            seg_end = n if window_end_s is None else int(round(window_end_s * fps))
            target = trunk[seg_end - 1]
            ok = np.abs(trunk[:seg_end] - target) <= 2.0
            up = _first(ok, s)
        return s, up

    if scenario == "E1":
        s, up = sit_up()
        e = None if up is None else up + int(round(1.0 * fps))
        out["events"].append(ev("E1", s, e, "trunk leaves the mattress", "trunk upright and held for 1 s",
                                "first frame at which the shoulder centre is more than 1 cm above its height in frame 0",
                                "1 s after the first frame at which the 3D trunk angle (hip centre to shoulder centre "
                                "against vertical) is within 2 degrees of its seated value; it stays there to the end",
                                fps, trunk_upright_frame=up, trunk_upright_s=frame_time(up, fps)))
    elif scenario == "E4":
        s1, up = sit_up(scripted["legs_start_turning"])
        e1 = None if up is None else up + int(round(1.0 * fps))
        out["events"].append(ev("E1", s1, e1, "trunk leaves the mattress", "trunk upright and held for 1 s",
                                "as in E1 clips", "as in E1 clips (the seated position is held 0.3 s here, then the "
                                "legs turn; the 1 s hold is measured from the upright frame regardless)", fps,
                                note="contained in the E4 movement; the person does not hold the seated position for 1 s"))
        legs = ["left_knee", "right_knee", "left_ankle", "right_ankle"]
        li = [coco.index(k) for k in legs]
        crosses = np.any(P[:, li, 0] > EDGE_X, axis=1)
        s2 = _first(crosses)
        ai = [coco.index("left_ankle"), coco.index("right_ankle")]
        hang = np.all((P[:, ai, 0] > EDGE_X) & (P[:, ai, 2] < C.MATTRESS_TOP), axis=1)
        e2 = _first(hang, s2 or 0)
        out["events"].append(ev("E2", s2, e2, "first leg crosses the mattress edge", "both feet hanging or on the floor",
                                "first frame at which a knee or ankle point is beyond the mattress edge on the exit side "
                                f"(x > {EDGE_X:.2f} m)",
                                "first frame at which both ankle points are beyond that edge and below the mattress top",
                                fps))
        s3 = _first(~on_mat, e2 or 0)
        # standing height: median hip height over still frames, off the mattress, trunk within 10 degrees of vertical
        still = np.concatenate([[False], step <= STILL_STEP])
        st = still & ~on_mat & (trunk <= 10.0)
        stand_h = float(np.median(hip[st, 2])) if st.any() else float(np.max(hip[:, 2]))
        upright = (trunk <= 10.0) & (hip[:, 2] >= stand_h - 0.03)
        up3 = _first(upright, s3 or 0)
        e3 = None if up3 is None else up3 + int(round(1.0 * fps))
        out["events"].append(ev("E3", s3, e3, "hips leave the mattress", "standing upright for 1 s",
                                "first frame (after the legs are over the edge) at which no body or clothes vertex "
                                "within 0.22 m of the hip centre touches the mattress (at or below 1.5 cm above its "
                                "pressed top)",
                                "1 s after the first frame with trunk angle at most 10 degrees and the hip centre within "
                                "3 cm of its standing height (median over the still, upright frames off the mattress)", fps,
                                standing_height_m=round(stand_h, 4),
                                standing_upright_frame=up3, standing_upright_s=frame_time(up3, fps)))
        bx, by = C.BED_AREA["x"], C.BED_AREA["y"]
        inside = (P[:, :, 0] >= bx[0]) & (P[:, :, 0] <= bx[1]) & (P[:, :, 1] >= by[0]) & (P[:, :, 1] <= by[1])
        e4 = _first(~np.any(inside, axis=1), s3 or 0)
        out["events"].append(ev("E4", s3, e4, "hips leave the mattress", "person leaves the bed area",
                                "same frame as the E3 start",
                                f"first frame at which none of the 17 COCO points is inside the bed area (bed outline "
                                f"x {bx[0]:.2f} to {bx[1]:.2f} m, y {by[0]:.2f} to {by[1]:.2f} m, i.e. the frame "
                                f"from footboard to headboard enlarged by {C.BED_AREA_MARGIN} m), seen from above", fps))
    elif scenario == "E6":
        s = int(round(scripted["slide_off_starts"] * fps))
        on_floor = hip[:, 2] < 0.30
        settled = max(still_f, _first(on_floor) or 0)
        e = settled + int(round(2.0 * fps))
        cross = _first(hip[:, 0] > EDGE_X)
        floor_contact = _first(np.array([f["lowest_z"] for f in gt]) < 0.005, s)
        out["events"].append(ev("E6", s, e, "body starts to leave the mattress without standing",
                                "body on the floor and still for 2 s",
                                "scripted: the keyframe at which the body, lying on its side at the edge, starts to "
                                "move over the edge (motions.py, 'slide_off_starts'); no ground-truth test separates "
                                "this from the roll before it",
                                "2 s after the first frame from which no ground-truth point moves more than 5 mm per "
                                "frame for the rest of the clip, with the hip centre below 0.30 m", fps,
                                hip_centre_crosses_edge_frame=cross, hip_centre_crosses_edge_s=frame_time(cross, fps),
                                first_floor_contact_frame=floor_contact,
                                first_floor_contact_s=frame_time(floor_contact, fps),
                                still_on_floor_from_frame=settled, still_on_floor_from_s=frame_time(settled, fps)))
        if e >= n:
            out["events"][-1]["warning"] = "clip ends before the end of the event"
    elif scenario == "L1":
        moving = np.concatenate([[False], step > STILL_STEP])
        ms = _first(moving)
        me = int(np.where(moving)[0][-1]) if moving.any() else None
        out["phases"]["L1_movement"] = dict(start_frame=ms, start_s=frame_time(ms, fps), end_frame=me,
                                            end_s=frame_time(me, fps),
                                            rule="first and last frame at which some ground-truth point moves more "
                                                 "than 5 mm since the previous frame",
                                            note="look-alike: no event; these times bound the movement only")
    elif scenario in ("E5", "E7", "E6b", "L7", "L9"):
        _compute_second_batch(scenario, out, gt, scripted, coco, P, hip, trunk, on_mat, still_f, step, n, fps)
    out["per_frame_max_point_step_m"] = [round(float(x), 5) for x in step]
    return out


FLOOR_TOUCH = 0.01        # a body part (not a foot) touches the floor when its lowest vertex is within 1 cm of it


def _compute_second_batch(scenario, out, gt, scripted, coco, P, hip, trunk, on_mat, still_f, step, n, fps):
    """Rules for the clips made for the v4 fall rule (R23 to R40)."""
    low_nf = np.array([f["lowest_non_foot_z"] for f in gt])
    on_floor = hip[:, 2] < 0.30
    still_end_rule = ("2 s after the first frame from which no ground-truth point moves more than 5 mm per frame "
                      "for the rest of the clip, with the hip centre below 0.30 m")

    def floor_end():
        settled = max(still_f, _first(on_floor) or 0)
        return settled, settled + int(round(2.0 * fps))

    def first_stands():
        s3 = _first(~on_mat)
        still = np.concatenate([[False], step <= STILL_STEP])
        upright = (trunk <= 10.0) & ~on_mat
        up = _first(upright, s3 or 0)
        return s3, up

    if scenario in ("E5", "E7", "E6b"):
        key = {"E5": "loss_of_balance", "E7": "loss_of_balance", "E6b": "roll_starts"}[scenario]
        s = int(round(scripted[key] * fps))
        settled, e = floor_end()
        impact = _first(low_nf < FLOOR_TOUCH, s)
        name = "E6" if scenario == "E6b" else scenario
        defs = {"E5": ("first loss of balance after standing", "body on the floor and still for 2 s"),
                "E7": ("first loss of balance while sitting on the edge", "body on the floor and still for 2 s"),
                "E6": ("body starts to leave the mattress", "body on the floor and still for 2 s")}[name]
        start_rule = {"E5": "scripted: the keyframe at which the person, standing after one step, starts to pitch "
                            "forward and the knees give way (motions.py, 'loss_of_balance')",
                      "E7": "scripted: the keyframe at which the person, leaning forward on the edge, starts to "
                            "slide off it (motions.py, 'loss_of_balance')",
                      "E6": "scripted: the keyframe at which the fast roll starts; the roll carries the body off "
                            "the mattress without a pause (motions.py, 'roll_starts')"}[name]
        extra = dict(first_floor_impact_frame=impact, first_floor_impact_s=frame_time(impact, fps),
                     still_on_floor_from_frame=settled, still_on_floor_from_s=frame_time(settled, fps),
                     impact_rule="first frame at or after the start at which a body vertex more than 0.25 m from both "
                                 "ankle points is within 1 cm of the floor")
        if scenario == "E5":
            st = int(round(scripted["step_lands"] * fps))
            t_stand = float(np.median(trunk[st - 3:st + 1]))
            tilt = _first(trunk > t_stand + 5.0, st)
            extra.update(measured_check_trunk_tilts_5deg_frame=tilt, measured_check_trunk_tilts_5deg_s=frame_time(tilt, fps))
        if scenario == "E7":
            off = _first(~on_mat, int(round(1.0 * fps)))
            extra.update(measured_check_hips_leave_mattress_frame=off, measured_check_hips_leave_mattress_s=frame_time(off, fps))
        if scenario == "E6b":
            cross = _first(hip[:, 0] > EDGE_X)
            extra.update(hip_centre_crosses_edge_frame=cross, hip_centre_crosses_edge_s=frame_time(cross, fps),
                         note="body B's E6 motion: a fast continuous roll, unlike body A's E6 (roll, pause on the side, slide)")
        out["events"].append(ev(name, s, e, defs[0], defs[1], start_rule, still_end_rule, fps, **extra))
        if e >= n:
            out["events"][-1]["warning"] = "clip ends before the end of the event"
        if scenario == "E5":
            s3, up = first_stands()
            out["first_stands"] = dict(e3_start_frame=s3, e3_start_s=frame_time(s3, fps),
                                       e3_start_rule="first frame at which no body or clothes vertex within 0.22 m of the "
                                                     "hip centre touches the mattress (hips leave the mattress)",
                                       standing_upright_frame=up, standing_upright_s=frame_time(up, fps),
                                       standing_upright_rule="first frame after that with the trunk within 10 degrees of "
                                                             "vertical",
                                       note="the person steps 0.3 s after standing upright, so the E3 end "
                                            "('standing upright for 1 s') is not reached")
        else:
            out["first_stands"] = "not applicable: the person does not stand up in this clip"
    else:   # L7, L9: look-alikes
        moving = np.concatenate([[False], step > STILL_STEP])
        ms = _first(moving)
        me = int(np.where(moving)[0][-1]) if moving.any() else None
        ph = dict(start_frame=ms, start_s=frame_time(ms, fps), end_frame=me, end_s=frame_time(me, fps),
                  rule="first and last frame at which some ground-truth point moves more than 5 mm since the previous frame",
                  note="look-alike: no event; these times bound the movement only")
        if scenario == "L9":
            seat = _first(np.array([f["hips_on_chair"] for f in gt]), ms or 0)
            ph.update(hips_reach_seat_frame=seat, hips_reach_seat_s=frame_time(seat, fps),
                      sit_down_duration_s=None if (seat is None or ms is None) else round((seat - ms) / fps, 4),
                      seat_rule="first frame at which a body or clothes vertex within 0.22 m of the hip centre touches the "
                                "chair seat (no more than 1.5 cm above its pressed top)")
            out["first_stands"] = "not applicable: the person is standing from the first frame"
        else:
            out["first_stands"] = "not applicable: the person does not stand up in this clip"
        out["phases"][scenario + "_movement"] = ph


# ====================================================================== third batch (R41 to R62)

def _movement(P, fps):
    step = np.max(np.linalg.norm(np.diff(P, axis=0), axis=2), axis=1)
    moving = np.concatenate([[False], step > STILL_STEP])
    ms = _first(moving)
    me = int(np.where(moving)[0][-1]) if moving.any() else None
    return ms, me, step


def compute3(motion_id, md, gt, gt2, coco, fps=C.FPS):
    """Falls F1 to F5: start (scripted loss of balance, or start of leaving the mattress for F3), first floor touch,
    end = on the floor and still for 2 s. Look-alikes: movement times of each person and named moments."""
    P = np.array([[f["world"][n] for n in coco] for f in gt])
    hip = np.array([f["world"]["hip_centre"] for f in gt])
    trunk = np.array([f["trunk_angle_deg"] for f in gt])
    on_mat = np.array([f["hips_on_mattress"] for f in gt])
    low_nf = np.array([f["lowest_non_foot_z"] for f in gt])
    n = len(gt)
    scripted = md["scripted"]
    out = {"events": [], "phases": {}, "scripted_s": scripted}
    still_f, step = _still_from(P)
    out["min_hip_height_m"] = round(float(hip[:, 2].min()), 4)
    if md.get("stands"):
        # search from the scripted stand-up, so that a pelvis lifting during an earlier sit-up does not count
        s3 = _first(~on_mat, int(round(scripted.get("standing_up_starts", 0.0) * fps)))
        up = _first((trunk <= 10.0) & ~on_mat, s3 or 0)
        out["first_stands"] = dict(e3_start_frame=s3, e3_start_s=frame_time(s3, fps),
                                   e3_start_rule="first frame at which no body or clothes vertex within 0.22 m of the hip "
                                                 "centre touches the mattress (hips leave the mattress)",
                                   standing_upright_frame=up, standing_upright_s=frame_time(up, fps),
                                   standing_upright_rule="first frame after that with the trunk within 10 degrees of vertical")
    else:
        out["first_stands"] = "not applicable: the person does not stand up from the bed in this clip"
    if motion_id.startswith("F"):
        s = int(round(scripted[md["start_key"]] * fps))
        on_floor = hip[:, 2] < 0.30
        settled = max(still_f, _first(on_floor) or 0)
        e = settled + int(round(2.0 * fps))
        touch = _first(low_nf < FLOOR_TOUCH, s)
        start_rule = {"F3": "scripted: the keyframe at which the fast roll that carries the body over the (non-exit) "
                            "edge starts: the start of leaving the mattress"}.get(
            motion_id, "scripted: the keyframe of the first loss of balance (motions3.py, 'loss_of_balance')")
        d = ev(motion_id, s, e, "first loss of balance" if motion_id != "F3" else "body starts to leave the mattress",
               "body on the floor and still for 2 s", start_rule,
               "2 s after the first frame from which no ground-truth point moves more than 5 mm per frame for the rest "
               "of the clip, with the hip centre below 0.30 m", fps,
               first_floor_touch_frame=touch, first_floor_touch_s=frame_time(touch, fps),
               first_floor_touch_rule="first frame at or after the start at which a body vertex more than 0.25 m from "
                                      "both ankle points is within 1 cm of the floor",
               still_on_floor_from_frame=settled, still_on_floor_from_s=frame_time(settled, fps),
               still_until_clip_end_s=round((n - 1 - settled) / fps, 4))
        if motion_id == "F3":
            cross = _first(hip[:, 0] < -EDGE_X)
            d.update(hip_centre_crosses_edge_frame=cross, hip_centre_crosses_edge_s=frame_time(cross, fps))
        if e >= n:
            d["warning"] = "clip ends before the end of the event"
        out["events"].append(d)
    else:
        ms, me, _ = _movement(P, fps)
        out["phases"]["patient_movement" if gt2 is not None else "movement"] = dict(
            start_frame=ms, start_s=frame_time(ms, fps), end_frame=me, end_s=frame_time(me, fps),
            rule="first and last frame at which some ground-truth point of this person moves more than 5 mm since the "
                 "previous frame", note="look-alike: no event")
        if gt2 is not None:
            P2 = np.array([[f["world"][k] for k in coco] for f in gt2])
            ms2, me2, _ = _movement(P2, fps)
            hip2 = np.array([f["world"]["hip_centre"] for f in gt2])
            out["phases"]["second_person_movement"] = dict(start_frame=ms2, start_s=frame_time(ms2, fps),
                                                           end_frame=me2, end_s=frame_time(me2, fps),
                                                           rule="as above, for the second person")
            out["min_hip_height_second_person_m"] = round(float(hip2[:, 2].min()), 4)
            if motion_id == "L13":
                kn = np.array([min(f["world"]["left_knee"][2], f["world"]["right_knee"][2]) for f in gt2])
                down = kn < 0.12
                k0 = _first(down)
                k1 = int(np.where(down)[0][-1]) if down.any() else None
                out["phases"]["nurse_kneeling"] = dict(start_frame=k0, start_s=frame_time(k0, fps), end_frame=k1,
                                                       end_s=frame_time(k1, fps),
                                                       rule="frames with a knee point of the nurse below 0.12 m")
        if motion_id == "L12":
            seat = _first(np.array([f["hips_on_chair"] for f in gt]))
            out["phases"]["hips_reach_seat"] = dict(start_frame=seat, start_s=frame_time(seat, fps), end_frame=None,
                                                    end_s=None, rule="first frame at which a body or clothes vertex "
                                                    "within 0.22 m of the hip centre touches the chair seat")
        if motion_id == "L14":
            out["hips_on_mattress_every_frame"] = bool(on_mat.all())
    out["per_frame_max_point_step_m"] = [round(float(x), 5) for x in step]
    return out
