"""The four pilot motions (E1, E4, E6, L1) as keyframed poses, and their scripted event times.

All angles in degrees, relative to MPFB's rest pose (an A-pose with the elbows
bent about 43 degrees). See animate.py for what each value means.
"""
import copy

import config as C

HIP_Y = 2.74          # hip centre along the bed when lying (head on the pillow, heels on the mattress)


def _j(**kw):
    """joints helper: _j(thigh_l=dict(flex=10), ...)"""
    return {k: dict(v) for k, v in kw.items()}


def both(d, **kw):
    """Same angles on both sides: both(d, thigh=dict(flex=10)) -> thigh_l and thigh_r."""
    for k, v in kw.items():
        d[k + "_l"] = dict(v)
        d[k + "_r"] = dict(v)
    return d


def pose(root, hip=None, joints=None):
    p = {"root": tuple(root), "joints": copy.deepcopy(joints or {})}
    if hip is not None:
        p["hip"] = tuple(hip)
    return p


def mix(p, **over):
    """Copy of pose p with some joints replaced or extended."""
    q = copy.deepcopy(p)
    for k, v in over.items():
        if k == "root":
            q["root"] = tuple(v)
        elif k == "hip":
            q["hip"] = tuple(v)
        else:
            q["joints"].setdefault(k, {}).update(v)
    return q


# ------------------------------------------------------------------ basic poses
ARMS_SIDE = both({}, upperarm=dict(abd=-34.0, flex=4.0), lowerarm=dict(flex=-30.0))

LYING = pose((0, 90, 0), (0.0, HIP_Y), both(dict(copy.deepcopy(ARMS_SIDE), neck_01=dict(flex=14.0), head=dict(flex=6.0)),
                                             thigh=dict(flex=2.0, abd=-1.0), calf=dict(flex=4.0), foot=dict(flex=-28.0)))

SITTING_IN_BED = pose((0, 8, 0), (0.0, HIP_Y),
                      both(dict(spine_01=dict(flex=6.0), spine_02=dict(flex=6.0), spine_03=dict(flex=4.0),
                                neck_01=dict(flex=4.0)),
                           thigh=dict(flex=84.0, abd=-2.0), calf=dict(flex=3.0), foot=dict(flex=-20.0),
                           upperarm=dict(abd=-36.0, flex=22.0), lowerarm=dict(flex=38.0)))   # hands in the lap

STANDING = pose((90, 0, 0), None, both(copy.deepcopy(ARMS_SIDE), thigh=dict(flex=0.0, abd=1.0), calf=dict(flex=2.0)))

SITTING_EDGE = pose((90, 4, 0), (0.30, 2.62),
                    both(dict(spine_01=dict(flex=6.0), spine_02=dict(flex=6.0), neck_01=dict(flex=6.0)),
                         thigh=dict(flex=88.0, abd=6.0), calf=dict(flex=88.0), foot=dict(flex=0.0),
                         upperarm=dict(abd=-24.0, flex=10.0), lowerarm=dict(flex=-10.0)))

LEFT_SIDE = pose((0, 90, 85), (0.06, HIP_Y),
                 dict(neck_01=dict(flex=10.0, side=-8.0), head=dict(flex=6.0),
                      spine_02=dict(flex=8.0), spine_03=dict(flex=6.0),
                      thigh_l=dict(flex=25.0), calf_l=dict(flex=35.0), foot_l=dict(flex=-20.0),
                      thigh_r=dict(flex=50.0, abd=-6.0), calf_r=dict(flex=65.0), foot_r=dict(flex=-20.0),
                      upperarm_l=dict(flex=70.0, abd=-30.0), lowerarm_l=dict(flex=20.0),
                      upperarm_r=dict(flex=30.0, abd=-52.0), lowerarm_r=dict(flex=25.0)))


def at(t, p, **opts):
    return (float(t), p, opts)


def lying_at(x):
    return mix(LYING, hip=(x, HIP_Y))


def sit_up_phases(x):
    """Lying -> sitting in bed: head and shoulders lift, elbows push, trunk comes up. Hip flexion keeps the legs flat."""
    a = mix(LYING, root=(0, 68, 0), hip=(x, HIP_Y),
            neck_01=dict(flex=32.0), head=dict(flex=8.0), spine_02=dict(flex=10.0), spine_03=dict(flex=10.0),
            thigh_l=dict(flex=22.0), thigh_r=dict(flex=22.0),
            upperarm_l=dict(flex=-22.0, abd=-28.0), upperarm_r=dict(flex=-22.0, abd=-28.0),
            lowerarm_l=dict(flex=25.0), lowerarm_r=dict(flex=25.0))
    b = mix(LYING, root=(0, 34, 0), hip=(x, HIP_Y),
            neck_01=dict(flex=18.0), head=dict(flex=4.0), spine_01=dict(flex=12.0), spine_02=dict(flex=14.0),
            spine_03=dict(flex=8.0),
            thigh_l=dict(flex=56.0, abd=-1.0), thigh_r=dict(flex=56.0, abd=-1.0), calf_l=dict(flex=8.0),
            calf_r=dict(flex=8.0),
            upperarm_l=dict(flex=-8.0, abd=-24.0), upperarm_r=dict(flex=-8.0, abd=-24.0),
            lowerarm_l=dict(flex=-5.0), lowerarm_r=dict(flex=-5.0))
    c = mix(SITTING_IN_BED, hip=(x, HIP_Y))
    return a, b, c


# ------------------------------------------------------------------ E1: sit up in bed
def motion_E1():
    a, b, c = sit_up_phases(0.0)
    keys = [at(0.0, lying_at(0.0)), at(1.0, lying_at(0.0)),
            at(1.6, a), at(2.3, b), at(3.0, c), at(6.0, c)]
    scripted = {"sit_up_motion_starts": 1.0, "trunk_upright_reached": 3.0}
    return keys, 6.0, scripted


# ------------------------------------------------------------------ E4: leave the bed and walk away
def _walk_pose(front, back, pass_leg=None):
    """Walking pose facing +X. front/back: leg ahead/behind at foot contact; or pass_leg: the swinging leg passing."""
    j = copy.deepcopy(STANDING["joints"])
    if pass_leg is None:
        j[f"thigh_{front}"] = dict(flex=17.0, abd=1.0)
        j[f"calf_{front}"] = dict(flex=5.0)
        j[f"foot_{front}"] = dict(flex=6.0)
        j[f"thigh_{back}"] = dict(flex=-9.0, abd=1.0)
        j[f"calf_{back}"] = dict(flex=14.0)
        j[f"foot_{back}"] = dict(flex=-12.0)
        # the opposite arm swings forward
        j[f"upperarm_{back}"] = dict(abd=-34.0, flex=14.0)
        j[f"upperarm_{front}"] = dict(abd=-34.0, flex=-8.0)
        j["spine_02"] = dict(twist=4.0 if front == "r" else -4.0)
    else:
        stance = "l" if pass_leg == "r" else "r"
        j[f"thigh_{pass_leg}"] = dict(flex=14.0, abd=1.0)
        j[f"calf_{pass_leg}"] = dict(flex=42.0)
        j[f"foot_{pass_leg}"] = dict(flex=4.0)
        j[f"thigh_{stance}"] = dict(flex=1.0, abd=1.0)
        j[f"calf_{stance}"] = dict(flex=4.0)
    j["spine_01"] = dict(flex=5.0)
    j["neck_01"] = dict(flex=8.0)
    return pose((90, 0, 0), None, j)


def motion_E4():
    x0 = 0.05
    a, b, c = sit_up_phases(x0)
    # pivots on the buttocks with the legs lifted a little, knees bending as the feet pass the edge
    turn_mid = mix(SITTING_IN_BED, root=(45, 12, 0), hip=(0.18, 2.68),
                   thigh_l=dict(flex=96.0), thigh_r=dict(flex=96.0), calf_l=dict(flex=22.0), calf_r=dict(flex=22.0),
                   upperarm_l=dict(abd=-18.0, flex=-12.0), upperarm_r=dict(abd=-18.0, flex=-12.0),
                   lowerarm_l=dict(flex=20.0), lowerarm_r=dict(flex=20.0))
    edge = SITTING_EDGE
    scoot = mix(SITTING_EDGE, root=(90, -4, 0), hip=(0.40, 2.62), thigh_l=dict(flex=86.0, abd=6.0),
                thigh_r=dict(flex=86.0, abd=6.0), calf_l=dict(flex=80.0), calf_r=dict(flex=80.0),
                spine_01=dict(flex=8.0), spine_02=dict(flex=8.0))
    lean = mix(scoot, root=(90, -34, 0), thigh_l=dict(flex=116.0, abd=6.0), thigh_r=dict(flex=116.0, abd=6.0),
               calf_l=dict(flex=84.0), calf_r=dict(flex=84.0), spine_01=dict(flex=10.0), spine_02=dict(flex=10.0),
               neck_01=dict(flex=-8.0), upperarm_l=dict(abd=-28.0, flex=30.0), upperarm_r=dict(abd=-28.0, flex=30.0),
               lowerarm_l=dict(flex=-10.0), lowerarm_r=dict(flex=-10.0))
    rise = mix(STANDING, root=(90, -18, 0), thigh_l=dict(flex=46.0, abd=3.0), thigh_r=dict(flex=46.0, abd=3.0),
               calf_l=dict(flex=34.0), calf_r=dict(flex=34.0), foot_l=dict(flex=6.0), foot_r=dict(flex=6.0),
               spine_01=dict(flex=6.0), spine_02=dict(flex=6.0), upperarm_l=dict(abd=-30.0, flex=12.0),
               upperarm_r=dict(abd=-30.0, flex=12.0))
    stand = mix(STANDING, spine_01=dict(flex=4.0), neck_01=dict(flex=6.0))
    keys = [at(0.0, lying_at(x0)), at(0.6, lying_at(x0)),
            at(1.1, a), at(1.6, b), at(2.2, c),
            at(2.5, c), at(3.25, turn_mid), at(4.0, edge),
            at(4.4, scoot, xy="feet"), at(5.0, lean, xy="feet"), at(5.8, rise, xy="feet"),
            at(6.6, stand, xy="feet"),
            # stands still for 1 s, then walks away: four short steps towards the exit side (+X)
            at(7.6, stand, xy="stance_l", ease="in"),
            at(7.9, _walk_pose(None, None, pass_leg="r"), xy="stance_l", ease="linear"),
            at(8.2, _walk_pose("r", "l"), xy="stance_r", ease="linear"),
            at(8.5, _walk_pose(None, None, pass_leg="l"), xy="stance_r", ease="linear"),
            at(8.8, _walk_pose("l", "r"), xy="stance_l", ease="linear"),
            at(9.1, _walk_pose(None, None, pass_leg="r"), xy="stance_l", ease="linear"),
            at(9.4, _walk_pose("r", "l"), xy="stance_r", ease="out"),
            at(10.0, mix(stand, thigh_l=dict(flex=-4.0), calf_l=dict(flex=8.0)), xy="stance_r")]
    scripted = {"sit_up_motion_starts": 0.6, "trunk_upright_reached": 2.2, "legs_start_turning": 2.5,
                "sitting_on_edge": 4.0, "standing_up_starts": 4.4, "standing_upright_reached": 6.6,
                "walking_starts": 7.6}
    return keys, 10.0, scripted


# ------------------------------------------------------------------ E6: slide or roll out of bed to the floor
def motion_E6():
    x0 = 0.13
    lie = lying_at(x0)
    roll_mid = mix(LYING, root=(0, 90, 40), hip=(0.16, HIP_Y),
                   thigh_r=dict(flex=30.0, abd=-4.0), calf_r=dict(flex=40.0),
                   upperarm_r=dict(flex=55.0, abd=-62.0), lowerarm_r=dict(flex=55.0),
                   upperarm_l=dict(flex=25.0, abd=-30.0), neck_01=dict(flex=12.0, side=-4.0))
    side = mix(LEFT_SIDE, hip=(0.22, HIP_Y))
    over = mix(LEFT_SIDE, root=(0, 90, 100), hip=(0.47, HIP_Y - 0.04),
               thigh_r=dict(flex=50.0, abd=-6.0), calf_r=dict(flex=60.0), thigh_l=dict(flex=25.0),
               calf_l=dict(flex=35.0), upperarm_l=dict(flex=80.0, abd=-35.0), lowerarm_l=dict(flex=10.0),
               upperarm_r=dict(flex=50.0, abd=-50.0), lowerarm_r=dict(flex=30.0), neck_01=dict(flex=0.0, side=0.0))
    # lands on the left side, facing away from the bed, then lies still (recovery-position-like)
    landing = mix(LEFT_SIDE, root=(0, 90, 112), hip=(0.80, HIP_Y - 0.08),
                  thigh_r=dict(flex=45.0, abd=-4.0), calf_r=dict(flex=60.0), thigh_l=dict(flex=20.0),
                  calf_l=dict(flex=30.0), foot_l=dict(flex=-30.0), foot_r=dict(flex=-30.0),
                  upperarm_l=dict(flex=95.0, abd=-38.0), lowerarm_l=dict(flex=25.0),
                  upperarm_r=dict(flex=55.0, abd=-55.0), lowerarm_r=dict(flex=40.0),
                  neck_01=dict(flex=0.0, side=8.0), head=dict(flex=0.0))
    rest = mix(landing, root=(0, 90, 106), hip=(0.81, HIP_Y - 0.08), neck_01=dict(flex=2.0, side=12.0),
               upperarm_l=dict(flex=100.0, abd=-38.0), lowerarm_l=dict(flex=30.0))
    keys = [at(0.0, lie), at(1.0, lie),
            at(1.5, roll_mid), at(2.0, side),
            at(2.65, over, z="fall", ease="linear"),
            at(3.05, landing, ease="out"),
            at(3.45, rest), at(7.0, rest)]
    scripted = {"roll_starts": 1.0, "on_side_at_edge": 2.0, "slide_off_starts": 2.0, "free_fall_allowed_from": 2.65,
                "settled_on_floor": 3.45}
    return keys, 7.0, scripted


# ------------------------------------------------------------------ L1: turn onto the side in bed (look-alike)
def motion_L1():
    lie = lying_at(0.0)
    roll_mid = mix(LYING, root=(0, 90, 40), hip=(0.03, HIP_Y),
                   thigh_r=dict(flex=30.0, abd=-4.0), calf_r=dict(flex=40.0),
                   upperarm_r=dict(flex=55.0, abd=-62.0), lowerarm_r=dict(flex=55.0),
                   upperarm_l=dict(flex=25.0, abd=-30.0), neck_01=dict(flex=12.0, side=-4.0))
    side = mix(LEFT_SIDE, hip=(0.06, HIP_Y))
    keys = [at(0.0, lie), at(1.0, lie), at(1.8, roll_mid), at(2.6, side), at(6.0, side)]
    scripted = {"turn_starts": 1.0, "on_side": 2.6}
    return keys, 6.0, scripted


MOTIONS = {"E1": motion_E1, "E4": motion_E4, "E6": motion_E6, "L1": motion_L1}
POSES = dict(lying=LYING, sitting_in_bed=SITTING_IN_BED, standing=STANDING, sitting_edge=SITTING_EDGE,
             left_side=LEFT_SIDE)


# ====================================================================== second batch (R23 to R40)
# Motions for the fresh fall-rule test clips. Each takes the body's dimensions
# (animate.Body.dims) so the same script fits body A and body B, and returns
# (keys, duration, scripted times, extras). Falls: loss of balance, a drop under
# gravity (z="drop": free fall stopped only by contact), an impact with a small
# rebound, then stillness on the floor for more than 2 s.

def _hip_y_lying(dims):
    """Hip position along the bed that puts the centre of the head on the pillow."""
    return C.PILLOW_CENTRE_Y - dims["hip_to_head_centre"]


def _stand_up_from_edge():
    """The scoot, lean, rise and stand poses of E4 (sitting on the exit-side edge, facing +X)."""
    scoot = mix(SITTING_EDGE, root=(90, -4, 0), hip=(0.40, 2.62), thigh_l=dict(flex=86.0, abd=6.0),
                thigh_r=dict(flex=86.0, abd=6.0), calf_l=dict(flex=80.0), calf_r=dict(flex=80.0),
                spine_01=dict(flex=8.0), spine_02=dict(flex=8.0))
    lean = mix(scoot, root=(90, -34, 0), thigh_l=dict(flex=116.0, abd=6.0), thigh_r=dict(flex=116.0, abd=6.0),
               calf_l=dict(flex=84.0), calf_r=dict(flex=84.0), spine_01=dict(flex=10.0), spine_02=dict(flex=10.0),
               neck_01=dict(flex=-8.0), upperarm_l=dict(abd=-28.0, flex=30.0), upperarm_r=dict(abd=-28.0, flex=30.0),
               lowerarm_l=dict(flex=-10.0), lowerarm_r=dict(flex=-10.0))
    rise = mix(STANDING, root=(90, -18, 0), thigh_l=dict(flex=46.0, abd=3.0), thigh_r=dict(flex=46.0, abd=3.0),
               calf_l=dict(flex=34.0), calf_r=dict(flex=34.0), foot_l=dict(flex=6.0), foot_r=dict(flex=6.0),
               spine_01=dict(flex=6.0), spine_02=dict(flex=6.0), upperarm_l=dict(abd=-30.0, flex=12.0),
               upperarm_r=dict(abd=-30.0, flex=12.0))
    stand = mix(STANDING, spine_01=dict(flex=4.0), neck_01=dict(flex=6.0))
    return scoot, lean, rise, stand


def _prone(yaw, knees=15.0, head_turn=55.0):
    """Lying face down along the floor (body pitched forward 90 degrees): one arm out to the side on the floor,
    the other along the body, head turned to the side."""
    side = "l" if head_turn > 0 else "r"
    other = "r" if side == "l" else "l"
    j = both(dict(spine_01=dict(flex=0.0), spine_02=dict(flex=0.0),
                  neck_01=dict(flex=-25.0, twist=head_turn), head=dict(flex=-5.0)),
             thigh=dict(flex=4.0, abd=4.0), calf=dict(flex=knees), foot=dict(flex=-40.0))
    j[f"upperarm_{side}"] = dict(abd=50.0, flex=8.0)
    j[f"lowerarm_{side}"] = dict(flex=-20.0)
    j[f"upperarm_{other}"] = dict(abd=-30.0, flex=6.0)
    j[f"lowerarm_{other}"] = dict(flex=-25.0)
    return pose((yaw, -90, 0), None, j)


# ------------------------------------------------------------------ E5: fall after standing
def motion_E5(dims):
    scoot, lean, rise, stand = _stand_up_from_edge()
    step_end = _walk_pose("r", "l")            # one step with the right foot, both feet on the floor
    stumble = mix(step_end, root=(90, -24, 0), thigh_r=dict(flex=38.0, abd=1.0), calf_r=dict(flex=32.0),
                  thigh_l=dict(flex=16.0, abd=1.0), calf_l=dict(flex=28.0), spine_01=dict(flex=10.0),
                  spine_02=dict(flex=6.0), upperarm_l=dict(flex=50.0, abd=-20.0), upperarm_r=dict(flex=55.0, abd=-20.0),
                  lowerarm_l=dict(flex=10.0), lowerarm_r=dict(flex=10.0), neck_01=dict(flex=-10.0))
    kneel = mix(step_end, root=(90, -42, 0), thigh_r=dict(flex=48.0, abd=3.0), calf_r=dict(flex=100.0),
                thigh_l=dict(flex=42.0, abd=3.0), calf_l=dict(flex=100.0), foot_l=dict(flex=-35.0),
                foot_r=dict(flex=-35.0), spine_01=dict(flex=14.0), spine_02=dict(flex=8.0),
                upperarm_l=dict(flex=85.0, abd=-15.0), upperarm_r=dict(flex=90.0, abd=-15.0),
                lowerarm_l=dict(flex=5.0), lowerarm_r=dict(flex=5.0), neck_01=dict(flex=-20.0))
    down = _prone(90)
    rebound = mix(down, root=(90, -85, 0), calf_l=dict(flex=24.0), calf_r=dict(flex=24.0))
    rest = down
    keys = [at(0.0, SITTING_EDGE), at(1.0, SITTING_EDGE),
            at(1.4, scoot, xy="feet"), at(2.0, lean, xy="feet"), at(2.8, rise, xy="feet"),
            at(3.4, stand, xy="feet"),
            at(3.7, stand, xy="stance_l", ease="in"),
            at(4.0, _walk_pose(None, None, pass_leg="r"), xy="stance_l", ease="out"),
            at(4.3, step_end, xy="feet"),
            # loss of balance at 4.4 s: trunk pitches forward, knees give way, a drop under gravity onto the
            # knees, then the trunk falls forward onto the floor (impact), a small rebound, stillness
            at(4.4, step_end, xy="feet", ease="in"),
            at(4.65, stumble, xy="feet", z="drop", ease="linear"),
            at(4.95, kneel, xy="feet", z="drop", ease="in"),
            at(5.25, down, xy="feet", z="drop", ease="out"),
            at(5.37, rebound, xy="feet", z="drop"),
            at(5.55, rest, xy="feet", z="drop"), at(8.0, rest, xy="feet", z="drop")]
    scripted = {"standing_up_starts": 1.4, "standing_upright_reached": 3.4, "step_starts": 3.7, "step_lands": 4.3,
                "loss_of_balance": 4.4, "free_fall_allowed_from": 4.65, "knees_down_key": 4.95,
                "trunk_impact_key": 5.25, "settled_key": 5.55}
    return keys, 8.0, scripted, {}


# ------------------------------------------------------------------ E7: fall from sitting on the edge
def motion_E7(dims):
    lean = mix(SITTING_EDGE, root=(90, -28, 0), hip=(0.33, 2.62), thigh_l=dict(flex=112.0, abd=6.0),
               thigh_r=dict(flex=112.0, abd=6.0), calf_l=dict(flex=86.0), calf_r=dict(flex=86.0),
               spine_01=dict(flex=12.0), spine_02=dict(flex=10.0), neck_01=dict(flex=10.0),
               upperarm_l=dict(abd=-24.0, flex=55.0), upperarm_r=dict(abd=-24.0, flex=60.0),
               lowerarm_l=dict(flex=5.0), lowerarm_r=dict(flex=5.0))
    slide = mix(lean, root=(90, -46, 0), hip=(0.70, 2.62), thigh_l=dict(flex=118.0, abd=6.0),
                thigh_r=dict(flex=118.0, abd=6.0), calf_l=dict(flex=96.0), calf_r=dict(flex=96.0),
                upperarm_l=dict(abd=-18.0, flex=85.0), upperarm_r=dict(abd=-18.0, flex=88.0), neck_01=dict(flex=-10.0))
    # the feet were hanging just above the floor at x of about 0.75 m: sliding off forward puts the knees on the
    # floor in front of them, so the shins lie on the floor between knees and feet, clear of the bed
    kneel = mix(lean, root=(90, -36, 0), hip=(1.22, 2.62), thigh_l=dict(flex=40.0, abd=4.0),
                thigh_r=dict(flex=40.0, abd=4.0), calf_l=dict(flex=104.0), calf_r=dict(flex=104.0),
                foot_l=dict(flex=-35.0), foot_r=dict(flex=-35.0), upperarm_l=dict(abd=-15.0, flex=90.0),
                upperarm_r=dict(abd=-15.0, flex=92.0), neck_01=dict(flex=-20.0))
    down = mix(_prone(90, knees=12.0, head_turn=-55.0), hip=(1.70, 2.62))
    rebound = mix(down, root=(90, -85, 0), calf_l=dict(flex=24.0), calf_r=dict(flex=24.0))
    rest = down
    keys = [at(0.0, SITTING_EDGE), at(1.0, SITTING_EDGE),
            at(1.6, lean, z="drop", ease="in"),      # loss of balance at 1.6 s: the buttocks slide off the edge
            at(1.85, slide, z="drop", ease="linear"),
            at(2.1, kneel, z="drop", ease="in"),
            at(2.4, down, z="drop", ease="out"),
            at(2.52, rebound, z="drop"), at(2.7, rest, z="drop"), at(6.0, rest, z="drop")]
    scripted = {"lean_starts": 1.0, "loss_of_balance": 1.6, "knees_down_key": 2.1, "trunk_impact_key": 2.4,
                "settled_key": 2.7}
    return keys, 6.0, scripted, {}


# ------------------------------------------------------------------ E6b: fast roll out of bed (body B)
def motion_E6b(dims):
    hy = _hip_y_lying(dims)
    lie = mix(LYING, hip=(0.15, hy))
    side = mix(LEFT_SIDE, root=(0, 90, 85), hip=(0.25, hy),
               thigh_r=dict(flex=45.0, abd=-6.0), calf_r=dict(flex=55.0), thigh_l=dict(flex=15.0),
               calf_l=dict(flex=20.0), upperarm_l=dict(flex=75.0, abd=-35.0), upperarm_r=dict(flex=50.0, abd=-58.0),
               lowerarm_r=dict(flex=40.0))
    over = mix(side, root=(0, 90, 122), hip=(0.50, hy - 0.04),
               thigh_r=dict(flex=55.0, abd=-6.0), calf_r=dict(flex=60.0), thigh_l=dict(flex=25.0), calf_l=dict(flex=30.0),
               upperarm_l=dict(flex=90.0, abd=-35.0), lowerarm_l=dict(flex=15.0), upperarm_r=dict(flex=70.0, abd=-45.0),
               neck_01=dict(flex=0.0, side=0.0))
    # lands half on the left side, half face down, facing away from the bed; the lower arm reaches forward to the
    # floor (away from the bed), the upper arm and leg fall forward over the body
    land = mix(LEFT_SIDE, root=(0, 90, 135), hip=(0.92, hy - 0.08),
               thigh_r=dict(flex=50.0, abd=-4.0), calf_r=dict(flex=70.0), thigh_l=dict(flex=10.0), calf_l=dict(flex=15.0),
               foot_l=dict(flex=-35.0), foot_r=dict(flex=-35.0),
               upperarm_l=dict(flex=95.0, abd=-40.0), lowerarm_l=dict(flex=25.0),
               upperarm_r=dict(flex=55.0, abd=-55.0), lowerarm_r=dict(flex=40.0),
               neck_01=dict(flex=-5.0, side=10.0), spine_02=dict(flex=0.0), spine_03=dict(flex=0.0))
    rebound = mix(land, root=(0, 90, 129), hip=(0.93, hy - 0.08), lowerarm_r=dict(flex=55.0))
    rest = mix(land, root=(0, 90, 133), hip=(0.93, hy - 0.08))
    keys = [at(0.0, lie), at(1.0, lie, ease="in"),
            at(1.4, side, ease="linear"),
            at(1.7, over, z="drop", ease="linear"),
            at(2.0, land, z="drop", ease="out"),
            at(2.12, rebound, z="drop"), at(2.3, rest, z="drop"), at(6.0, rest, z="drop")]
    scripted = {"roll_starts": 1.0, "on_side": 1.4, "free_fall_allowed_from": 1.7, "landing_key": 2.0,
                "settled_key": 2.3}
    return keys, 6.0, scripted, {}


# ------------------------------------------------------------------ L7: from sitting on the edge, back into bed (look-alike)
def motion_L7(dims):
    hy = _hip_y_lying(dims)
    turn_mid = mix(SITTING_IN_BED, root=(45, 12, 0), hip=(0.18, (2.62 + hy) / 2),
                   thigh_l=dict(flex=96.0), thigh_r=dict(flex=96.0), calf_l=dict(flex=22.0), calf_r=dict(flex=22.0),
                   upperarm_l=dict(abd=-18.0, flex=-12.0), upperarm_r=dict(abd=-18.0, flex=-12.0),
                   lowerarm_l=dict(flex=20.0), lowerarm_r=dict(flex=20.0))
    a, b, c = sit_up_phases(0.05)
    a, b, c = (mix(p, hip=(0.05, hy)) for p in (a, b, c))
    keys = [at(0.0, SITTING_EDGE), at(1.0, SITTING_EDGE),
            at(1.75, turn_mid), at(2.4, c), at(2.6, c),
            at(3.1, b), at(3.6, a), at(4.1, mix(LYING, hip=(0.05, hy))), at(6.0, mix(LYING, hip=(0.05, hy)))]
    scripted = {"legs_start_back": 1.0, "sitting_in_bed": 2.4, "lying_back_starts": 2.6, "lying": 4.1}
    return keys, 6.0, scripted, {}


# ------------------------------------------------------------------ L9: quick sit-down on a chair (look-alike)
def motion_L9(dims):
    ch = C.CHAIR
    hip_y = ch["y"] - 0.03 - dims["thigh"]     # stands so that, sitting, the hips land over the seat
    stand = mix(STANDING, root=(0, 0, 0), hip=(ch["x"], hip_y), spine_01=dict(flex=4.0), neck_01=dict(flex=6.0))
    crouch = mix(stand, root=(0, -26, 0), thigh_l=dict(flex=50.0, abd=3.0), thigh_r=dict(flex=50.0, abd=3.0),
                 calf_l=dict(flex=48.0), calf_r=dict(flex=48.0), foot_l=dict(flex=8.0), foot_r=dict(flex=8.0),
                 spine_01=dict(flex=8.0), upperarm_l=dict(abd=-30.0, flex=30.0), upperarm_r=dict(abd=-30.0, flex=30.0))
    seated = mix(stand, root=(0, 4, 0), thigh_l=dict(flex=86.0, abd=4.0), thigh_r=dict(flex=86.0, abd=4.0),
                 calf_l=dict(flex=90.0), calf_r=dict(flex=90.0), foot_l=dict(flex=0.0), foot_r=dict(flex=0.0),
                 spine_01=dict(flex=6.0), spine_02=dict(flex=4.0),
                 upperarm_l=dict(abd=-34.0, flex=8.0), upperarm_r=dict(abd=-34.0, flex=8.0),
                 lowerarm_l=dict(flex=22.0), lowerarm_r=dict(flex=22.0))       # hands on the thighs
    bounce = mix(seated, root=(0, 0, 0), spine_01=dict(flex=10.0))
    settle = mix(seated, root=(0, 7, 0))
    keys = [at(0.0, stand), at(1.0, stand, xy="feet", ease="in"),
            at(1.3, crouch, xy="feet", z="drop", ease="linear"),     # drops onto the seat
            at(1.62, seated, xy="feet", z="drop", ease="out"),
            at(1.74, bounce, xy="feet", z="drop"), at(1.95, settle, xy="feet", z="drop"),
            at(5.0, settle, xy="feet", z="drop")]
    scripted = {"sit_down_starts": 1.0, "seated_key": 1.62, "settled_key": 1.95}
    return keys, 5.0, scripted, {"chair": True}


MOTIONS2 = {"E5": motion_E5, "E7": motion_E7, "E6b": motion_E6b, "L7": motion_L7, "L9": motion_L9}
