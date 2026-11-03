"""Third batch (R41 to R62): falls F1 to F5 and look-alikes L10 to L15, as keyframed poses.

Each function takes the body's dimensions (animate.Body.dims) and returns a dict:
  keys      the person's keys (for two-person clips: the patient's keys)
  keys2     (two-person clips only) the second person's keys
  dur       clip length in seconds
  scripted  scripted times (s)
  env       options for the motion solver (chair position, lowered rails)
  objects   which extra objects the clip uses and their timings (objects3.py animates them)
Falls: loss of balance, a drop under gravity (z="drop"), an impact with a small rebound, then stillness on
the floor for more than 3 s. Yaw convention: 0 = facing the camera (-Y), 90 = facing +X (exit side),
-90 = facing -X, 180 = facing +Y.
"""
import copy
import math

import config as C
from motions import (LYING, LEFT_SIDE, SITTING_EDGE, SITTING_IN_BED, STANDING, at, both, mix, pose,
                     sit_up_phases, _hip_y_lying, _prone, _stand_up_from_edge)


def yaw_towards(dx, dy):
    """Yaw (degrees) that faces the direction (dx, dy)."""
    return math.degrees(math.atan2(dx, -dy))


def stand_at(yaw, hip=None, **over):
    p = mix(STANDING, root=(yaw, 0, 0), spine_01=dict(flex=4.0), neck_01=dict(flex=6.0))
    if hip is not None:
        p["hip"] = tuple(hip)
    return mix(p, **over) if over else p


def walk_pose(yaw, front=None, back=None, pass_leg=None, amp=1.0, upper=None):
    """Walking pose facing `yaw`. Contact pose: `front` leg ahead, `back` leg behind. Passing pose: `pass_leg` swings.
    amp scales the leg angles (1.0 = short elderly steps). upper: joints overriding the arms and trunk."""
    j = copy.deepcopy(STANDING["joints"])
    if pass_leg is None:
        j[f"thigh_{front}"] = dict(flex=17.0 * amp, abd=1.0)
        j[f"calf_{front}"] = dict(flex=5.0)
        j[f"foot_{front}"] = dict(flex=6.0)
        j[f"thigh_{back}"] = dict(flex=-9.0 * amp, abd=1.0)
        j[f"calf_{back}"] = dict(flex=14.0 * amp)
        j[f"foot_{back}"] = dict(flex=-12.0)
        j[f"upperarm_{back}"] = dict(abd=-34.0, flex=14.0 * amp)
        j[f"upperarm_{front}"] = dict(abd=-34.0, flex=-8.0 * amp)
        j["spine_02"] = dict(twist=4.0 if front == "r" else -4.0)
    else:
        stance = "l" if pass_leg == "r" else "r"
        j[f"thigh_{pass_leg}"] = dict(flex=14.0 * amp, abd=1.0)
        j[f"calf_{pass_leg}"] = dict(flex=42.0)
        j[f"foot_{pass_leg}"] = dict(flex=4.0)
        j[f"thigh_{stance}"] = dict(flex=1.0, abd=1.0)
        j[f"calf_{stance}"] = dict(flex=4.0)
    j["spine_01"] = dict(flex=5.0)
    j["neck_01"] = dict(flex=8.0)
    for k, v in (upper or {}).items():
        j[k] = dict(v)
    return pose((yaw, 0, 0), None, j)


def walk(t0, yaws, first="r", dt=0.3, amp=1.0, backward=False, upper=None, root_back=0.0):
    """Keys for len(yaws) steps starting at t0 from a standing pose (the caller's key at t0 must use
    xy=stance of the first stance leg). yaws: facing for each step (turning while walking).
    Returns (keys, t_end, last_leg). The last key (both feet down) is left to the caller."""
    keys = []
    leg = first
    t = t0
    for i, yaw in enumerate(yaws):
        st = "l" if leg == "r" else "r"
        ps = walk_pose(yaw, pass_leg=leg, amp=amp, upper=upper)
        ps["root"] = (yaw, root_back, 0)
        keys.append(at(t + dt, ps, xy="stance_" + st, ease="linear"))
        if backward:
            ct = walk_pose(yaw, front=st, back=leg, amp=amp, upper=upper)
        else:
            ct = walk_pose(yaw, front=leg, back=st, amp=amp, upper=upper)
        ct["root"] = (yaw, root_back, 0)
        last = i == len(yaws) - 1
        keys.append(at(t + 2 * dt, ct, xy=("feet" if last else "stance_" + leg), ease="linear"))
        t += 2 * dt
        leg = st
    return keys, t, leg


def prone_flat(yaw, knees=10.0, head_turn=55.0):
    """Face down flat on the floor (third batch): one arm out to the side and one along the body, both held level
    with the shoulders so that the hands do not prop the trunk up (the batch 2 pose _prone rests on one hand)."""
    side = "l" if head_turn > 0 else "r"
    other = "r" if side == "l" else "l"
    j = both(dict(spine_01=dict(flex=0.0), spine_02=dict(flex=0.0),
                  neck_01=dict(flex=-25.0, twist=head_turn), head=dict(flex=-5.0)),
             thigh=dict(flex=2.0, abd=4.0), calf=dict(flex=knees), foot=dict(flex=-40.0))
    j[f"upperarm_{side}"] = dict(abd=45.0, flex=-6.0)
    j[f"lowerarm_{side}"] = dict(flex=-40.0)        # MPFB's rest pose bends the elbow about 43 degrees forward
    j[f"upperarm_{other}"] = dict(abd=-36.0, flex=-5.0)
    j[f"lowerarm_{other}"] = dict(flex=-40.0)
    return pose((yaw, -90, 0), None, j)


# ====================================================================== falls

def motion_F1(dims):
    """Sitting on the exit-side edge, stands, one step away from the bed, turns to face the camera, loses balance
    backwards and falls onto the floor beside the bed (lands sitting, then on the back)."""
    edge = mix(SITTING_EDGE, hip=(0.30, 2.30))
    scoot, lean, rise, stand = _stand_up_from_edge()
    scoot = mix(scoot, hip=(0.40, 2.30))
    face_cam = stand_at(0.0)
    tilt = mix(face_cam, root=(0, 14, 0), thigh_l=dict(flex=22.0, abd=3.0), thigh_r=dict(flex=22.0, abd=3.0),
               calf_l=dict(flex=28.0), calf_r=dict(flex=28.0), upperarm_l=dict(flex=55.0, abd=-20.0),
               upperarm_r=dict(flex=60.0, abd=-20.0), neck_01=dict(flex=20.0))
    # lands sitting (thighs up, feet flat), then the trunk goes back onto the floor, knees still bent
    sit = mix(face_cam, root=(0, 30, 0), thigh_l=dict(flex=108.0, abd=6.0), thigh_r=dict(flex=104.0, abd=6.0),
              calf_l=dict(flex=118.0), calf_r=dict(flex=112.0), foot_l=dict(flex=10.0), foot_r=dict(flex=10.0),
              upperarm_l=dict(flex=45.0, abd=-20.0), upperarm_r=dict(flex=45.0, abd=-34.0),
              lowerarm_l=dict(flex=15.0), lowerarm_r=dict(flex=15.0), neck_01=dict(flex=25.0), spine_02=dict(flex=12.0))
    tall = dims["shin"] > 0.42      # longer shins: bend the knees less, so the feet do not hold the back off the floor
    down = mix(face_cam, root=(0, 88, 0), thigh_l=dict(flex=50.0, abd=6.0), thigh_r=dict(flex=44.0, abd=6.0),
               calf_l=dict(flex=90.0 if tall else 100.0), calf_r=dict(flex=86.0 if tall else 94.0),
               foot_l=dict(flex=0.0), foot_r=dict(flex=0.0),
               upperarm_l=dict(flex=10.0, abd=10.0), upperarm_r=dict(flex=12.0, abd=-34.0),
               lowerarm_l=dict(flex=-20.0), lowerarm_r=dict(flex=15.0), neck_01=dict(flex=4.0), head=dict(flex=0.0))
    rebound = mix(down, root=(0, 82, 0), neck_01=dict(flex=12.0))
    rest = mix(down, root=(0, 90, 0))
    keys = [at(0.0, edge), at(1.0, edge),
            at(1.4, scoot, xy="feet"), at(2.0, lean, xy="feet"), at(2.8, rise, xy="feet"), at(3.4, stand, xy="feet"),
            at(3.7, stand, xy="stance_l", ease="in")]
    wk, t, _ = walk(3.7, [90.0], first="r", dt=0.3, amp=1.7)
    keys += wk                                              # one long step away from the bed (ends 4.3)
    keys += [at(4.5, mix(stand, root=(90, 0, 0)), xy="feet"),
             at(5.1, face_cam, xy="feet"),                  # turns in place to face the camera
             at(5.5, face_cam, xy="feet", ease="in"),       # loss of balance backwards at 5.5 s
             at(5.75, tilt, xy="feet", z="drop", ease="linear"),
             at(6.05, sit, xy="feet", z="drop", ease="in"),
             at(6.35, down, xy="feet", z="drop", ease="out"),
             at(6.45, rebound, xy="feet", z="drop"), at(6.65, rest, xy="feet", z="drop"),
             at(10.0, rest, xy="feet", z="drop")]
    scripted = {"standing_up_starts": 1.4, "standing_upright_reached": 3.4, "step": [3.7, 4.3], "turn": [4.5, 5.1],
                "loss_of_balance": 5.5, "buttocks_impact_key": 6.05, "back_impact_key": 6.35, "settled_key": 6.65}
    return dict(keys=keys, dur=10.0, scripted=scripted, env={}, objects={}, start_key="loss_of_balance",
                stands=True)


def motion_F2(dims):
    """Walking back towards the bed from about 1 m away on the exit side, trips and falls forward onto the floor."""
    yaw = 180.0                                     # walks along the bed's exit side, 0.8 m out, towards its head end
    start = stand_at(yaw, hip=(1.33, 1.10))
    keys = [at(0.0, start), at(0.6, start, xy="stance_l", ease="in")]
    wk, t, _ = walk(0.6, [yaw, yaw], first="r", dt=0.3, amp=1.3)
    keys += wk[:-1]
    t_trip = 1.8
    contact_l = wk[-1][1]
    # the next swing (right foot) catches the floor at 2.1 s: the trunk pitches forward over the stopped leg
    swing = walk_pose(yaw, pass_leg="r", amp=1.3)
    trip = mix(swing, root=(yaw, -22, 0), thigh_r=dict(flex=-14.0, abd=2.0), calf_r=dict(flex=34.0),
               thigh_l=dict(flex=26.0, abd=2.0), calf_l=dict(flex=24.0), upperarm_l=dict(flex=60.0, abd=-20.0),
               upperarm_r=dict(flex=65.0, abd=-20.0), lowerarm_l=dict(flex=5.0), lowerarm_r=dict(flex=5.0),
               neck_01=dict(flex=-10.0), spine_01=dict(flex=10.0))
    collapse = mix(trip, root=(yaw, -50, 0), thigh_l=dict(flex=60.0, abd=3.0), thigh_r=dict(flex=34.0, abd=3.0),
                   calf_l=dict(flex=95.0), calf_r=dict(flex=100.0), foot_l=dict(flex=-35.0), foot_r=dict(flex=-35.0),
                   upperarm_l=dict(flex=100.0, abd=-15.0), upperarm_r=dict(flex=105.0, abd=-15.0),
                   neck_01=dict(flex=-20.0))
    down = prone_flat(yaw, knees=10.0, head_turn=-55.0)  # the arm on the side away from the bed goes out
    rebound = mix(down, root=(yaw, -85, 0), calf_l=dict(flex=22.0), calf_r=dict(flex=22.0))
    keys += [at(t_trip, contact_l, xy="stance_l", ease="linear"),
             at(2.1, swing, xy="stance_l", ease="in"),      # loss of balance (trip) at 2.1 s
             at(2.3, trip, xy="stance_l", z="drop", ease="linear"),
             at(2.55, collapse, xy="feet", z="drop", ease="in"),
             at(2.85, down, xy="feet", z="drop", ease="out"),
             at(2.97, rebound, xy="feet", z="drop"), at(3.15, down, xy="feet", z="drop"),
             at(6.5, down, xy="feet", z="drop")]
    scripted = {"walking_starts": 0.6, "loss_of_balance": 2.1, "knees_down_key": 2.55, "trunk_impact_key": 2.85,
                "settled_key": 3.15}
    return dict(keys=keys, dur=6.5, scripted=scripted, env={}, objects={}, start_key="loss_of_balance",
                stands=False)


def motion_F3(dims):
    """Fast roll out of bed on the NON-exit side (-X; rails lowered there for these clips), landing between the bed
    and the bedside table."""
    hy = _hip_y_lying(dims)
    lie = mix(LYING, hip=(-0.15, hy))
    side = mix(LEFT_SIDE, root=(0, 90, -85), hip=(-0.25, hy - 0.08),
               thigh_l=dict(flex=45.0, abd=-6.0), calf_l=dict(flex=55.0), thigh_r=dict(flex=15.0), calf_r=dict(flex=20.0),
               upperarm_r=dict(flex=60.0, abd=-45.0), lowerarm_r=dict(flex=20.0),
               upperarm_l=dict(flex=50.0, abd=-58.0), lowerarm_l=dict(flex=40.0),
               neck_01=dict(flex=10.0, side=8.0))
    over = mix(side, root=(0, 90, -122), hip=(-0.50, hy - 0.22),
               thigh_l=dict(flex=55.0, abd=-6.0), calf_l=dict(flex=60.0), thigh_r=dict(flex=25.0), calf_r=dict(flex=30.0),
               upperarm_r=dict(flex=55.0, abd=-52.0), lowerarm_r=dict(flex=10.0), upperarm_l=dict(flex=40.0, abd=-55.0),
               neck_01=dict(flex=0.0, side=0.0))
    # lands half on the right side, half face down, between the bed and the (moved) bedside table: the lower arm
    # flat on the floor in front, the upper arm on the body; shoulders just in front of the table, head beside it
    land = mix(LEFT_SIDE, root=(0, 90, -102), hip=(-0.79, hy - 0.32),
               thigh_l=dict(flex=50.0, abd=-4.0), calf_l=dict(flex=70.0), thigh_r=dict(flex=12.0), calf_r=dict(flex=18.0),
               foot_l=dict(flex=-35.0), foot_r=dict(flex=-35.0),
               upperarm_r=dict(flex=45.0, abd=-62.0), lowerarm_r=dict(flex=-25.0),
               upperarm_l=dict(flex=28.0, abd=-62.0), lowerarm_l=dict(flex=10.0),
               neck_01=dict(flex=-5.0, side=12.0), spine_02=dict(flex=6.0), spine_03=dict(flex=4.0))
    land["root"] = (0, 90, -95)
    land["joints"]["thigh_l"] = dict(flex=30.0, abd=-10.0)
    land["joints"]["thigh_r"] = dict(flex=12.0, abd=-14.0 if dims["shin"] > 0.42 else -6.0)
    if dims["shin"] > 0.42:     # broad shoulders: the waist sags towards the floor so the hip rests on it too
        land["joints"]["spine_01"] = dict(flex=0.0, side=4.0)
        land["joints"]["spine_02"] = dict(flex=6.0, side=3.0)
    rebound = mix(land, root=(0, 90, -90), hip=(-0.80, hy - 0.32))
    rest = mix(land, hip=(-0.80, hy - 0.32))
    keys = [at(0.0, lie), at(1.0, lie, ease="in"), at(1.4, side, ease="linear"),
            at(1.7, over, z="drop", ease="linear"), at(2.0, land, z="drop", ease="out"),
            at(2.12, rebound, z="drop"), at(2.3, rest, z="drop"), at(6.0, rest, z="drop")]
    scripted = {"roll_starts": 1.0, "on_side": 1.4, "over_the_edge_key": 1.7, "landing_key": 2.0, "settled_key": 2.3}
    return dict(keys=keys, dur=6.0, scripted=scripted, env={"nonexit_down": True}, objects={"f3_setup": True},
                start_key="roll_starts", stands=False)


def motion_F4(dims):
    """Sitting on the exit-side edge, slides down slowly, then the legs give way: ends sitting on the floor,
    leaning back against the bed side, legs out."""
    edge = mix(SITTING_EDGE, hip=(0.30, 2.50))
    slow = mix(SITTING_EDGE, root=(90, 0, 0), hip=(0.42, 2.50), thigh_l=dict(flex=76.0, abd=6.0),
               thigh_r=dict(flex=76.0, abd=6.0), calf_l=dict(flex=84.0), calf_r=dict(flex=84.0),
               upperarm_l=dict(abd=-22.0, flex=-12.0), upperarm_r=dict(abd=-22.0, flex=-12.0),
               lowerarm_l=dict(flex=0.0), lowerarm_r=dict(flex=0.0))
    tall = dims["shin"] > 0.42      # longer legs: lift the thighs a little more so the buttocks reach the floor
    floor = mix(SITTING_EDGE, root=(90, 12, 0), hip=(0.74, 2.50), thigh_l=dict(flex=89.0 if tall else 83.0, abd=8.0),
                thigh_r=dict(flex=87.0 if tall else 81.0, abd=8.0), calf_l=dict(flex=8.0), calf_r=dict(flex=14.0),
                foot_l=dict(flex=-20.0), foot_r=dict(flex=-20.0), spine_01=dict(flex=8.0), spine_02=dict(flex=8.0),
                neck_01=dict(flex=14.0), upperarm_l=dict(abd=-10.0, flex=-8.0), upperarm_r=dict(abd=-10.0, flex=-8.0),
                lowerarm_l=dict(flex=0.0), lowerarm_r=dict(flex=0.0))
    rebound = mix(floor, root=(90, 6, 0), spine_01=dict(flex=14.0))
    keys = [at(0.0, edge), at(1.0, edge),
            at(2.6, slow, ease="in"),                       # slides slowly 1.0 to 2.6 s; legs give way at 2.6 s
            at(2.95, floor, z="drop", ease="in"),
            at(3.07, rebound, z="drop"), at(3.25, floor, z="drop"), at(6.5, floor, z="drop")]
    scripted = {"slow_slide_starts": 1.0, "loss_of_balance": 2.6, "landing_key": 2.95, "settled_key": 3.25}
    return dict(keys=keys, dur=6.5, scripted=scripted, env={}, objects={}, start_key="loss_of_balance",
                stands=False)


def motion_F5(dims):
    """Standing beside the bed at its head end on the exit side, collapses straight down and ends curled on the
    right side close to the bed. Root written as (180, tilt, -90): standing facing +X, tilting towards -Y."""
    stand = mix(STANDING, root=(180, 0, -90), hip=(0.85, 3.25), spine_01=dict(flex=4.0), neck_01=dict(flex=6.0))
    kneel = mix(stand, thigh_l=dict(flex=12.0, abd=6.0), thigh_r=dict(flex=12.0, abd=6.0),
                calf_l=dict(flex=104.0), calf_r=dict(flex=104.0), foot_l=dict(flex=-35.0), foot_r=dict(flex=-35.0),
                spine_01=dict(flex=14.0), spine_02=dict(flex=10.0), neck_01=dict(flex=30.0),
                upperarm_l=dict(abd=-34.0, flex=10.0), upperarm_r=dict(abd=-34.0, flex=10.0))
    curled = mix(stand, root=(180, 86, -90), thigh_l=dict(flex=80.0, abd=2.0), thigh_r=dict(flex=72.0, abd=2.0),
                 calf_l=dict(flex=105.0), calf_r=dict(flex=100.0), foot_l=dict(flex=-30.0), foot_r=dict(flex=-30.0),
                 spine_01=dict(flex=12.0), spine_02=dict(flex=12.0), spine_03=dict(flex=8.0),
                 neck_01=dict(flex=18.0, side=-12.0), upperarm_l=dict(flex=60.0, abd=-40.0),
                 lowerarm_l=dict(flex=70.0), upperarm_r=dict(flex=85.0, abd=-46.0), lowerarm_r=dict(flex=55.0))
    curled["joints"]["thigh_r"] = dict(flex=72.0, abd=-6.0)
    if dims["shin"] > 0.42:     # broad shoulders: the waist sags towards the floor (right side down)
        curled["joints"]["spine_01"] = dict(flex=12.0, side=3.0)
        curled["joints"]["spine_02"] = dict(flex=12.0, side=2.0)
    rebound = mix(curled, root=(180, 80, -90))
    keys = [at(0.0, stand), at(1.0, stand, xy="feet", ease="in"),   # collapses at 1.0 s
            at(1.32, kneel, xy="feet", z="drop", ease="in"),
            at(1.82, curled, xy="feet", z="drop", ease="in"),
            at(1.94, rebound, xy="feet", z="drop"), at(2.12, curled, xy="feet", z="drop"),
            at(6.0, curled, xy="feet", z="drop")]
    scripted = {"loss_of_balance": 1.0, "knees_down_key": 1.32, "side_impact_key": 1.82, "settled_key": 2.12}
    return dict(keys=keys, dur=6.0, scripted=scripted, env={}, objects={}, start_key="loss_of_balance",
                stands=False)


# ====================================================================== look-alikes

def lying_still(dims, dur, x=0.0):
    hy = _hip_y_lying(dims)
    lie = mix(LYING, hip=(x, hy))
    return [at(0.0, lie), at(dur, lie)]


def motion_L10(dims):
    """Patient in bed under a blanket moves her legs; the blanket slides off the exit side onto the floor."""
    hy = _hip_y_lying(dims)
    lie = mix(LYING, hip=(0.0, hy))
    knees = mix(lie, thigh_l=dict(flex=22.0, abd=4.0), thigh_r=dict(flex=16.0, abd=2.0),
                calf_l=dict(flex=40.0), calf_r=dict(flex=30.0), foot_l=dict(flex=-10.0), foot_r=dict(flex=-10.0))
    keys = [at(0.0, lie), at(1.0, lie), at(1.5, knees), at(2.1, lie), at(7.0, lie)]
    scripted = {"legs_move": [1.0, 2.1], "blanket_slides": [1.3, 3.0]}
    return dict(keys=keys, dur=7.0, scripted=scripted, env={}, objects={"blanket": (1.3, 3.0)},
                start_key=None, stands=False)


def _visitor_path(dims, kneel=False):
    """Second person (body A) walks in from the door side (out of view), stops beside the bed on the exit side,
    faces the bed, then (bag or kneel) and walks out the way it came."""
    start = (3.45, 0.35)        # in the door corner: outside both cameras' views at 1.8 m and 2.2 m
    target = (1.22, 2.20) if not kneel else (1.25, 2.55)
    yaw_in = yaw_towards(target[0] - start[0], target[1] - start[1])
    yaw_out = yaw_towards(start[0] - target[0], start[1] - target[1])
    return start, target, yaw_in, yaw_out


def motion_L11(dims_patient, dims_visitor):
    """Visitor (body A) walks in, puts a bag on the floor beside the bed (exit side), walks out. Patient lies still."""
    start, target, yaw_in, yaw_out = _visitor_path(dims_visitor)
    carry = dict(upperarm_r=dict(abd=-30.0, flex=0.0), lowerarm_r=dict(flex=-25.0))
    st = stand_at(yaw_in, hip=start, **carry)
    k = [at(0.0, st), at(0.4, st, xy="stance_l", ease="in")]
    wk, t, leg = walk(0.4, [yaw_in] * 5, first="r", dt=0.25, amp=1.6, upper=carry)
    k += wk
    face = stand_at(-90.0, **carry)
    crouch = mix(face, root=(-90, -32, 0), thigh_l=dict(flex=75.0, abd=8.0), thigh_r=dict(flex=70.0, abd=8.0),
                 calf_l=dict(flex=80.0), calf_r=dict(flex=75.0), foot_l=dict(flex=10.0), foot_r=dict(flex=10.0),
                 spine_01=dict(flex=12.0), upperarm_r=dict(abd=-24.0, flex=25.0), lowerarm_r=dict(flex=0.0),
                 upperarm_l=dict(abd=-30.0, flex=30.0), neck_01=dict(flex=10.0))
    t1 = t + 0.1
    k += [at(t1, face, xy="feet"), at(t1 + 0.5, face, xy="feet"),            # turns to the bed
          at(t1 + 1.3, crouch, xy="feet"), at(t1 + 1.6, crouch, xy="feet"),   # bag put down
          at(t1 + 2.4, stand_at(-90.0), xy="feet"), at(t1 + 3.0, stand_at(yaw_out), xy="stance_l", ease="in")]
    wk2, t2, _ = walk(t1 + 3.0, [yaw_out] * 5, first="r", dt=0.25, amp=1.42)
    k += wk2
    k += [at(t2 + 1.4, stand_at(yaw_out), xy="feet")]
    dur = round(t2 + 1.4, 2)
    patient = lying_still(dims_patient, dur)
    scripted = {"visitor_walks_in": [0.4, t], "visitor_turns": [t1, t1 + 0.5], "bag_put_down": [t1 + 0.5, t1 + 1.6],
                "visitor_walks_out": [t1 + 3.0, t2]}
    return dict(keys=patient, keys2=k, dur=dur, scripted=scripted, env={},
                objects={"bag": dict(carry_until=t1 + 1.6)}, start_key=None, stands=False)


def motion_L13(dims_patient, dims_nurse):
    """Nurse (body A) walks to the exit side of the bed, kneels on the floor beside it for about 3 s (as if picking
    something up), stands and leaves. Patient lies still."""
    start, target, yaw_in, yaw_out = _visitor_path(dims_nurse, kneel=True)
    st = stand_at(yaw_in, hip=start)
    k = [at(0.0, st), at(0.4, st, xy="stance_l", ease="in")]
    wk, t, leg = walk(0.4, [yaw_in] * 5, first="r", dt=0.25, amp=1.6)
    k += wk
    face = stand_at(-90.0)
    # kneeling with both knees on the floor: shins lie back, tops of the feet on the floor
    kneel = mix(face, root=(-90, -24, 0), thigh_l=dict(flex=20.0, abd=8.0), thigh_r=dict(flex=20.0, abd=8.0),
                calf_l=dict(flex=114.0), calf_r=dict(flex=114.0), foot_l=dict(flex=-60.0), foot_r=dict(flex=-60.0),
                spine_01=dict(flex=14.0), spine_02=dict(flex=8.0), neck_01=dict(flex=20.0),
                upperarm_l=dict(abd=-30.0, flex=22.0), upperarm_r=dict(abd=-30.0, flex=28.0),
                lowerarm_l=dict(flex=10.0), lowerarm_r=dict(flex=5.0))
    # reaches down towards the floor in front of the knees (not onto the bed)
    reach = mix(kneel, upperarm_r=dict(abd=-26.0, flex=38.0), lowerarm_r=dict(flex=-12.0), spine_01=dict(flex=22.0))
    t1 = t + 0.1
    k += [at(t1, face, xy="feet"), at(t1 + 0.5, face, xy="feet"),
          at(t1 + 1.5, kneel, xy="feet"), at(t1 + 2.5, reach, xy="feet"), at(t1 + 3.5, kneel, xy="feet"),
          at(t1 + 4.5, kneel, xy="feet"),                                   # kneels about 3 s
          at(t1 + 5.6, face, xy="feet"), at(t1 + 6.2, stand_at(yaw_out), xy="stance_l", ease="in")]
    wk2, t2, _ = walk(t1 + 6.2, [yaw_out] * 5, first="r", dt=0.25, amp=1.42)
    k += wk2
    k += [at(t2 + 1.2, stand_at(yaw_out), xy="feet")]
    dur = round(t2 + 1.2, 2)
    patient = lying_still(dims_patient, dur)
    scripted = {"nurse_walks_in": [0.4, t], "nurse_kneels_down": [t1 + 0.5, t1 + 1.5],
                "nurse_kneeling": [t1 + 1.5, t1 + 4.5], "nurse_stands_up": [t1 + 4.5, t1 + 5.6],
                "nurse_walks_out": [t1 + 6.2, t2]}
    return dict(keys=patient, keys2=k, dur=dur, scripted=scripted, env={}, objects={}, start_key=None, stands=False)


def motion_L12(dims, chair_final=None):
    """Gets out of bed (from sitting on the edge), pulls the chair from the head end to beside the bed, sits on it.
    chair_final: where the chair ends (set by a first solve; see render_clips_v3)."""
    cf = chair_final or (C.CHAIR["x"], C.CHAIR["y"])
    edge = mix(SITTING_EDGE, hip=(0.30, 2.05))
    scoot, lean, rise, stand = _stand_up_from_edge()
    scoot = mix(scoot, hip=(0.45, 2.05))     # a little further forward than in E4, to stand clear of the rail
    yaw_go = yaw_towards(0.45, 0.90)
    keys = [at(0.0, edge), at(1.0, edge), at(1.4, scoot, xy="feet"), at(2.0, lean, xy="feet"),
            at(2.8, rise, xy="feet"), at(3.4, stand, xy="feet"),
            at(3.9, stand_at(yaw_go), xy="stance_l", ease="in")]
    wk, t, _ = walk(3.9, [yaw_go, yaw_go], first="r", dt=0.3, amp=1.3)
    keys += wk
    bend_upper = dict(spine_01=dict(flex=14.0), spine_02=dict(flex=10.0), neck_01=dict(flex=-5.0),
                      upperarm_l=dict(abd=-30.0, flex=62.0), upperarm_r=dict(abd=-30.0, flex=62.0),
                      lowerarm_l=dict(flex=-5.0), lowerarm_r=dict(flex=-5.0))
    face = stand_at(180.0)
    bend = mix(face, root=(180, -30, 0), thigh_l=dict(flex=48.0, abd=4.0), thigh_r=dict(flex=48.0, abd=4.0),
               calf_l=dict(flex=40.0), calf_r=dict(flex=40.0), **bend_upper)
    t1 = t + 0.1
    keys += [at(t1, face, xy="feet"), at(t1 + 0.4, face, xy="feet"),
             at(t1 + 1.0, bend, xy="stance_l", ease="in")]                   # grabs the seat front at t1 + 1.0
    wk2, t2, _ = walk(t1 + 1.0, [180.0, 180.0, 180.0], first="r", dt=0.3, amp=1.1, backward=True,
                      upper=bend_upper, root_back=-30.0)
    # walking backwards bent over: the knees stay bent
    for _, p, _o in wk2:
        for s in ("l", "r"):
            p["joints"][f"calf_{s}"] = dict(flex=max(p["joints"].get(f"calf_{s}", {}).get("flex", 0.0), 30.0))
            th = p["joints"].get(f"thigh_{s}", {"flex": 0.0})
            p["joints"][f"thigh_{s}"] = dict(flex=th.get("flex", 0.0) + 40.0, abd=4.0)
    keys += wk2
    t_rel = t2
    keys += [at(t_rel + 0.5, face, xy="feet"),                              # lets go and straightens up
             at(t_rel + 1.3, stand_at(360.0), xy="feet"),                     # turns round to face the camera
             at(t_rel + 1.5, stand_at(360.0, hip=(cf[0], cf[1] - 0.03 - dims["thigh"])), xy="glide"),
             at(t_rel + 2.3, stand_at(360.0, hip=(cf[0], cf[1] - 0.03 - dims["thigh"])), xy="feet", ease="in")]
    crouch = mix(stand_at(360.0), root=(360, -24, 0), thigh_l=dict(flex=50.0, abd=3.0), thigh_r=dict(flex=50.0, abd=3.0),
                 calf_l=dict(flex=48.0), calf_r=dict(flex=48.0), foot_l=dict(flex=8.0), foot_r=dict(flex=8.0),
                 spine_01=dict(flex=8.0), upperarm_l=dict(abd=-30.0, flex=30.0), upperarm_r=dict(abd=-30.0, flex=30.0))
    seated = mix(stand_at(360.0), root=(360, 6, 0), thigh_l=dict(flex=86.0, abd=4.0), thigh_r=dict(flex=86.0, abd=4.0),
                 calf_l=dict(flex=90.0), calf_r=dict(flex=90.0), foot_l=dict(flex=0.0), foot_r=dict(flex=0.0),
                 spine_01=dict(flex=6.0), spine_02=dict(flex=4.0),
                 upperarm_l=dict(abd=-34.0, flex=8.0), upperarm_r=dict(abd=-34.0, flex=8.0),
                 lowerarm_l=dict(flex=22.0), lowerarm_r=dict(flex=22.0))
    ts = t_rel + 2.3
    keys += [at(ts + 0.45, crouch, xy="feet", z="drop", ease="linear"), at(ts + 0.9, seated, xy="feet", z="drop", ease="out"),
             at(ts + 1.2, seated, xy="feet", z="drop"), at(ts + 3.2, seated, xy="feet", z="drop")]
    dur = round(ts + 3.2, 2)
    scripted = {"standing_up_starts": 1.4, "standing_upright_reached": 3.4, "walks_to_chair": [3.9, t],
                "grabs_chair": t1 + 1.0, "pulls_chair": [t1 + 1.0, t_rel], "lets_go": t_rel,
                "turns": [t_rel + 0.5, t_rel + 1.3], "sits_down": [ts, ts + 0.9]}
    return dict(keys=keys, dur=dur, scripted=scripted, env={"chair_xy": cf, "chair_from_s": t_rel},
                objects={"chair": dict(grab=t1 + 1.0, release=t_rel, final=cf)}, start_key=None, stands=True)


def motion_L14(dims):
    """Sitting on the exit-side edge, bends down to put on slippers (feet on or near the floor) for about 3 s,
    then sits up again. Never leaves the bed."""
    edge = mix(SITTING_EDGE, hip=(0.30, 2.50))
    near = mix(SITTING_EDGE, root=(90, -4, 0), hip=(0.40, 2.50), thigh_l=dict(flex=78.0, abd=6.0),
               thigh_r=dict(flex=78.0, abd=6.0), calf_l=dict(flex=82.0), calf_r=dict(flex=82.0))
    bend = mix(near, root=(90, -42, 0), thigh_l=dict(flex=118.0, abd=8.0), thigh_r=dict(flex=118.0, abd=8.0),
               spine_01=dict(flex=16.0), spine_02=dict(flex=16.0), spine_03=dict(flex=8.0), neck_01=dict(flex=10.0),
               upperarm_l=dict(abd=-20.0, flex=72.0), upperarm_r=dict(abd=-20.0, flex=72.0),
               lowerarm_l=dict(flex=12.0), lowerarm_r=dict(flex=12.0))
    bend2 = mix(bend, upperarm_r=dict(abd=-14.0, flex=78.0), lowerarm_r=dict(flex=20.0), foot_r=dict(flex=12.0))
    bend3 = mix(bend, upperarm_l=dict(abd=-14.0, flex=78.0), lowerarm_l=dict(flex=20.0), foot_l=dict(flex=12.0))
    keys = [at(0.0, edge), at(1.0, edge), at(1.6, near), at(2.4, bend), at(3.2, bend2), at(4.2, bend3),
            at(5.4, bend), at(6.3, near), at(8.0, near)]
    scripted = {"moves_forward": [1.0, 1.6], "bends_down": [1.6, 2.4], "bent_over": [2.4, 5.4], "sits_up": [5.4, 6.3],
                "slipper_on_right": [2.6, 3.2], "slipper_on_left": [3.6, 4.2]}
    return dict(keys=keys, dur=8.0, scripted=scripted, env={},
                objects={"slippers": dict(r=(2.6, 3.2), l=(3.6, 4.2))}, start_key=None, stands=False)


def motion_L15(dims):
    """Gets out of bed (from lying) and walks out of view towards the door. Bed empty, nothing on the floor."""
    hy = _hip_y_lying(dims)
    a, b, c = sit_up_phases(0.05)
    a, b, c = (mix(p, hip=(0.05, hy)) for p in (a, b, c))
    turn_mid = mix(SITTING_IN_BED, root=(45, 12, 0), hip=(0.18, (2.62 + hy) / 2),
                   thigh_l=dict(flex=96.0), thigh_r=dict(flex=96.0), calf_l=dict(flex=22.0), calf_r=dict(flex=22.0),
                   upperarm_l=dict(abd=-18.0, flex=-12.0), upperarm_r=dict(abd=-18.0, flex=-12.0),
                   lowerarm_l=dict(flex=20.0), lowerarm_r=dict(flex=20.0))
    scoot, lean, rise, stand = _stand_up_from_edge()
    yaw_out = yaw_towards(3.45 - 0.8, 0.35 - 2.62)    # towards the door corner, out of both cameras' views
    keys = [at(0.0, mix(LYING, hip=(0.05, hy))), at(0.6, mix(LYING, hip=(0.05, hy))),
            at(1.1, a), at(1.6, b), at(2.2, c), at(2.4, c), at(3.1, turn_mid), at(3.8, SITTING_EDGE),
            at(4.2, scoot, xy="feet"), at(4.8, lean, xy="feet"), at(5.6, rise, xy="feet"), at(6.2, stand, xy="feet"),
            at(6.4, stand, xy="feet"), at(6.9, stand_at(yaw_out), xy="stance_l", ease="in")]
    tall = dims["shin"] > 0.42      # longer legs, longer steps: fewer of them to reach the door corner
    wk, t, _ = walk(6.9, [yaw_out] * (7 if tall else 8), first="r", dt=0.25, amp=1.42 if tall else 1.5)
    keys += wk
    # a last shuffle into the door corner, which is outside both cameras' views at both heights
    keys += [at(t + 0.2, stand_at(yaw_out), xy="glide"),
             at(t + 1.0, stand_at(yaw_out, hip=(3.42, 0.36)), xy="feet"), at(t + 2.0, stand_at(yaw_out), xy="feet")]
    dur = round(t + 2.0, 2)
    scripted = {"sit_up": [0.6, 2.2], "legs_over_edge": [2.4, 3.8], "standing_up_starts": 4.2,
                "standing_upright_reached": 6.2, "turns_to_door": [6.4, 6.9], "walks_out": [6.9, t]}
    return dict(keys=keys, dur=dur, scripted=scripted, env={}, objects={}, start_key=None, stands=True)


MOTIONS3 = {"F1": motion_F1, "F2": motion_F2, "F3": motion_F3, "F4": motion_F4, "F5": motion_F5,
            "L10": motion_L10, "L11": motion_L11, "L12": motion_L12, "L13": motion_L13, "L14": motion_L14,
            "L15": motion_L15}
TWO_PERSON = {"L11", "L13"}
CLOSEST_SCENARIO = {"F1": "E5", "F2": "none (fall while walking)", "F3": "E6", "F4": "E7",
                    "F5": "none (collapse while standing beside the bed)", "L10": "none", "L11": "L6 (second person)",
                    "L12": "none (similar to L9)", "L13": "L5 (staff present)", "L14": "L2 (reach to the floor from bed)",
                    "L15": "E4 (full bed exit; here a look-alike for the floor check: nobody on the floor)"}
