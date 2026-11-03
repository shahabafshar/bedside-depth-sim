"""Shared settings for the rendered-3D bedside dataset (Blender + MPFB).

Every number that shapes a clip lives here, so the scene, the motions and the
renders all read the same values. Units: metres, seconds, degrees.

World axes: X to the right as seen from the camera, Y away from the camera
(towards the head of the bed), Z up. The floor is z = 0. The camera wall is
y = 0. The patient's head lies at the far end of the bed (large y).
"""
import math

# ---------------------------------------------------------------- timing
FPS = 15                      # the detector's frame rate
# Frame i (counting from 0) is shown at t = i / FPS seconds.

# ---------------------------------------------------------------- room
ROOM_X_MIN, ROOM_X_MAX = -2.1, 3.75  # side walls (5.85 m wide; the exit side is wide enough
                                     # for the side-view camera 3 m from the bed, clips R13, R17, R21)
ROOM_Y_MIN, ROOM_Y_MAX = 0.0, 3.95   # camera wall, back wall
ROOM_Z_MAX = 3.0                     # ceiling

# ---------------------------------------------------------------- bed
MATTRESS_W = 0.90                    # x size
MATTRESS_L = 2.00                    # y size
MATTRESS_T = 0.15                    # thickness
MATTRESS_TOP = 0.58                  # top surface height ("about 0.6 m")
MATTRESS_Y0 = 1.70                   # foot end of the mattress
MATTRESS_Y1 = MATTRESS_Y0 + MATTRESS_L   # head end (3.70)
MATTRESS_CENTRE = (0.0, (MATTRESS_Y0 + MATTRESS_Y1) / 2.0, MATTRESS_TOP)
BED_FRAME_X = 0.50                   # half width of the bed frame
BED_FOOTBOARD_Y = (1.60, 1.66)       # footboard thickness range in y
BED_HEADBOARD_Y = (3.74, 3.80)
FOOTBOARD_TOP = 0.76                 # 0.18 m above the mattress
HEADBOARD_TOP = 1.05
PILLOW = dict(x=(-0.30, 0.30), y=(3.30, 3.68), top=0.66, compressed_top=0.60)   # soft: a head presses it to 2 cm
EXIT_SIDE = +1                       # the patient leaves the bed on the +X side
# Side rails: up on the -X side, lowered (below the mattress top) on the exit side.
RAIL_UP_Z = (0.63, 0.95)
RAIL_DOWN_Z = (0.18, 0.42)
RAIL_SEGMENTS_Y = [(1.90, 2.70), (2.80, 3.60)]
BEDSIDE_TABLE = dict(x=-0.88, y=3.25, w=0.45, d=0.45, h=0.75)
DOOR = dict(x=ROOM_X_MAX, y=(0.35, 1.30), h=2.10)

# Bed area used for the end of event E4 ("person leaves the bed area"):
# the bed's outline (frame width, footboard to headboard) enlarged by
# BED_AREA_MARGIN on every side. A person has left the bed area when none of
# the 17 COCO ground-truth points is inside this rectangle (seen from above).
BED_AREA_MARGIN = 0.50
BED_AREA = dict(x=(-BED_FRAME_X - BED_AREA_MARGIN, BED_FRAME_X + BED_AREA_MARGIN),
                y=(BED_FOOTBOARD_Y[0] - BED_AREA_MARGIN, BED_HEADBOARD_Y[1] + BED_AREA_MARGIN))

# ---------------------------------------------------------------- person (MPFB macro sliders, 0..1)
PERSON_MACRO = dict(gender=1.0, age=0.875, muscle=0.5, weight=0.55, proportions=0.5,
                    height=0.5, cupsize=0.5, firmness=0.5,
                    race=dict(asian=0.0, caucasian=1.0, african=0.0))
# MakeHuman's age slider: 0.5 = 25 years, 1.0 = 90 years, so 0.875 is about 74 years.
PERSON_SKIN = "old_caucasian_male"
PERSON_EYES = "low-poly"
PERSON_EYEBROWS = "eyebrow001"
PERSON_HAIR = "short02"
PERSON_CLOTHES = ["male_casualsuit06"]   # recoloured to pale blue "hospital pyjamas"
CLOTHES_COLOUR = (0.55, 0.70, 0.82)      # linear RGB, pale blue

# ---------------------------------------------------------------- camera (Luxonis OAK-D Pro W)
CAMERA_X = 0.0
CAMERA_Y = 0.05          # lens 5 cm in front of the camera wall
CAMERA_HEIGHTS = [1.8, 2.2, 2.6]
# Published fields of view (docs.luxonis.com, OAK-D Pro W): stereo/mono OV9282
# 127 deg wide x 79.5 deg tall; colour IMX378 95 deg wide x 72 deg tall.
MONO_HFOV_PUBLISHED, MONO_VFOV_PUBLISHED = 127.0, 79.5
COLOUR_HFOV_PUBLISHED, COLOUR_VFOV_PUBLISHED = 95.0, 72.0
MONO_RES = (640, 400)
COLOUR_RES = (640, 480)
# Pilot simplification: pinhole cameras with square pixels. The horizontal
# field of view is set to the published value; the vertical one then follows
# from the image shape (see README).
def pinhole_vfov_deg(hfov_deg, res):
    w, h = res
    return math.degrees(2.0 * math.atan(math.tan(math.radians(hfov_deg) / 2.0) * h / w))


def intrinsics(hfov_deg, res):
    """Pinhole intrinsics (pixels) for square pixels; principal point at the image centre."""
    w, h = res
    fx = (w / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    return dict(fx=fx, fy=fx, cx=w / 2.0, cy=h / 2.0, width=w, height=h)


# ---------------------------------------------------------------- infrared-like image
IR_LIGHT_POWER_W = 120.0     # spot light at the camera; tuned once by eye, same for all clips
IR_SPOT_DEG = 150.0          # wide cone so the whole view is lit (flood light)
IR_EXPOSURE = 1.0            # linear gain before sRGB encoding of the grey image

# ---------------------------------------------------------------- camera positions
# Every camera is placed by a position and an aim point; roll is always zero
# (image horizon level). Colour and mono cameras share the position and aim
# (the real camera's few centimetres between its lenses are ignored).
AIM_BED = MATTRESS_CENTRE


def foot_wall(height, x=0.0):
    return dict(position=(x, CAMERA_Y, height), aim=AIM_BED,
                rule="optical axis through the centre of the mattress top")


SIDE_VIEW = dict(position=(BED_FRAME_X + 3.0, MATTRESS_CENTRE[1], 1.0),
                 aim=(0.0, MATTRESS_CENTRE[1], 1.0),
                 rule="level (zero pitch), optical axis horizontal and across the bed's centre; "
                      "on the exit side, 3.0 m from the bed frame's long side")
CORNER_VIEW = dict(position=(ROOM_X_MIN + 0.10, 0.10, 2.6), aim=AIM_BED,
                   rule="high corner of the foot-end wall on the side away from the exit; "
                        "optical axis through the centre of the mattress top")

CAMERAS = {
    "foot_centre_1.8": dict(foot_wall(1.8), label="foot wall, centred, 1.8 m"),
    "foot_centre_2.2": dict(foot_wall(2.2), label="foot wall, centred, 2.2 m"),
    "foot_centre_2.6": dict(foot_wall(2.6), label="foot wall, centred, 2.6 m"),
    "foot_left_0.5_2.2": dict(foot_wall(2.2, -0.5), label="foot wall, 0.5 m left of the bed's centre line (as seen from the camera), 2.2 m"),
    "foot_right_0.5_2.2": dict(foot_wall(2.2, +0.5), label="foot wall, 0.5 m right of the bed's centre line (as seen from the camera), 2.2 m"),
    "side_1.0": dict(SIDE_VIEW, label="side view like GMDCSA-24: 1.0 m high, 3 m from the bed's long side, level"),
    "corner_2.6": dict(CORNER_VIEW, label="high room corner like CAUCAFall: 2.6 m, foot-end corner away from the exit side"),
}

# ---------------------------------------------------------------- clips
# R01 to R10 were planned first. R11 to R22 were added before any render existed:
# the same E1, E4 and E6 animations as the 2.2 m
# clips, seen from four more positions.
CLIPS = {
    "R01": ("E1", "foot_centre_1.8"), "R02": ("E1", "foot_centre_2.2"), "R03": ("E1", "foot_centre_2.6"),
    "R04": ("E4", "foot_centre_1.8"), "R05": ("E4", "foot_centre_2.2"), "R06": ("E4", "foot_centre_2.6"),
    "R07": ("E6", "foot_centre_1.8"), "R08": ("E6", "foot_centre_2.2"), "R09": ("E6", "foot_centre_2.6"),
    "R10": ("L1", "foot_centre_2.2"),
    "R11": ("E1", "foot_left_0.5_2.2"), "R12": ("E1", "foot_right_0.5_2.2"), "R13": ("E1", "side_1.0"), "R14": ("E1", "corner_2.6"),
    "R15": ("E4", "foot_left_0.5_2.2"), "R16": ("E4", "foot_right_0.5_2.2"), "R17": ("E4", "side_1.0"), "R18": ("E4", "corner_2.6"),
    "R19": ("E6", "foot_left_0.5_2.2"), "R20": ("E6", "foot_right_0.5_2.2"), "R21": ("E6", "side_1.0"), "R22": ("E6", "corner_2.6"),
}

# ---------------------------------------------------------------- second batch (R23 to R40)
# Requested on 2026-10-19 as fresh test clips for a fall rule frozen at 21:23 UTC
# (v4); rendered after that time. They use scene_v2.blend: scene_base.blend
# (unchanged) plus body B and a chair. Body A is the same person as in R01 to R22.
# Entries are (body, motion, camera).
CLIPS.update({
    "R23": ("A", "E5", "foot_centre_2.2"), "R24": ("A", "E5", "foot_centre_1.8"),
    "R25": ("A", "E7", "foot_centre_2.2"), "R26": ("A", "E7", "foot_centre_1.8"),
    "R27": ("A", "L7", "foot_centre_2.2"), "R28": ("A", "L7", "foot_centre_1.8"),
    "R29": ("A", "L9", "foot_centre_2.2"), "R30": ("A", "L9", "foot_centre_1.8"),
    "R31": ("B", "E5", "foot_centre_2.2"), "R32": ("B", "E5", "foot_centre_1.8"),
    "R33": ("B", "E7", "foot_centre_2.2"), "R34": ("B", "E7", "foot_centre_1.8"),
    "R35": ("B", "E6b", "foot_centre_2.2"), "R36": ("B", "E6b", "foot_centre_1.8"),
    "R37": ("B", "L7", "foot_centre_2.2"), "R38": ("B", "L7", "foot_centre_1.8"),
    "R39": ("B", "L9", "foot_centre_2.2"), "R40": ("B", "L9", "foot_centre_1.8"),
})


def clip_spec(clip):
    """(body, motion, camera) for any clip id; R01 to R22 use body A."""
    v = CLIPS[clip]
    return ("A",) + tuple(v) if len(v) == 2 else tuple(v)


# Body B: an older woman of heavier build (MPFB macro sliders; CC0 system assets).
PERSON_B_MACRO = dict(gender=0.0, age=0.92, muscle=0.35, weight=0.85, proportions=0.5,
                      height=0.42, cupsize=0.5, firmness=0.3,
                      race=dict(asian=0.0, caucasian=1.0, african=0.0))
# MakeHuman's age slider: 0.92 is about 79 years.
PERSON_B_SKIN = "old_caucasian_female"
PERSON_B_EYEBROWS = "eyebrow002"
PERSON_B_HAIR = "bob02"
PERSON_B_CLOTHES = "toigo_shift_dress"     # from the CC0 "Dress 01" pack; recoloured as a pale gown
PERSON_B_CLOTHES_COLOUR = (0.62, 0.75, 0.74)   # linear RGB, pale green-blue

BODIES = {
    "A": dict(prefix="PERSON", eyes="Human.low-poly", collection="PERSON",
              label="male, about 74 years (MakeHuman age 0.875), weight 0.55, 1.71 m; pale blue t-shirt and trousers"),
    "B": dict(prefix="PERSON_B", eyes="PERSON_B_EYES", collection="PERSON_B",
              label="female, about 79 years (MakeHuman age 0.92), heavier build (weight 0.85), pale sleeveless gown"),
}

# A plain chair beside the bed on the exit side, used only in L9 clips (hidden otherwise).
# The seat faces the camera (-Y); the backrest is on its +Y side.
CHAIR = dict(x=0.98, y=2.45, seat_top=0.45, w=0.46, d=0.46, back_top=0.90)
CHAIR_SINK = 0.015       # a seat cushion pressed 1.5 cm (pelvis: PELVIS_SINK_CHAIR)
PELVIS_SINK_CHAIR = 0.025
PILLOW_CENTRE_Y = (PILLOW["y"][0] + PILLOW["y"][1]) / 2.0

# ---------------------------------------------------------------- third batch (R41 to R62, plan step S4)
# Test clips for rules v5 (a depth-only floor check), frozen at 2026-10-20 01:19 UTC; rendered after that.
# Scene: scene_v3.blend = scene_v2.blend plus a blanket, a bag and slippers (each hidden unless a clip uses it).
# Entries are (people, motion, camera). "B+A" = body B is the patient in bed, body A the second person
# (visitor or nurse).
CLIPS.update({
    "R41": ("A", "F1", "foot_centre_2.2"), "R42": ("B", "F1", "foot_centre_1.8"),
    "R43": ("A", "F2", "foot_centre_1.8"), "R44": ("B", "F2", "foot_centre_2.2"),
    "R45": ("A", "F3", "foot_centre_2.2"), "R46": ("B", "F3", "foot_centre_1.8"),
    "R47": ("A", "F4", "foot_centre_1.8"), "R48": ("B", "F4", "foot_centre_2.2"),
    "R49": ("A", "F5", "foot_centre_2.2"), "R50": ("B", "F5", "foot_centre_1.8"),
    "R51": ("B", "L10", "foot_centre_2.2"), "R52": ("B", "L10", "foot_centre_1.8"),
    "R53": ("B+A", "L11", "foot_centre_2.2"), "R54": ("B+A", "L11", "foot_centre_1.8"),
    "R55": ("A", "L12", "foot_centre_2.2"), "R56": ("B", "L12", "foot_centre_1.8"),
    "R57": ("B+A", "L13", "foot_centre_2.2"), "R58": ("B+A", "L13", "foot_centre_1.8"),
    "R59": ("A", "L14", "foot_centre_2.2"), "R60": ("B", "L14", "foot_centre_1.8"),
    "R61": ("A", "L15", "foot_centre_2.2"), "R62": ("B", "L15", "foot_centre_1.8"),
})

# The bed's true outer footprint seen from above (room coordinates, metres): side rails at x +/-0.53
# (the frame and boards end at +/-0.50), footboard front at y 1.60, headboard back at y 3.80.
# Measured from the scene geometry (all bed parts, rails, wheels; not the bedside table).
BED_RECT_M = [-0.53, 0.53, 1.60, 3.80]

# F3 (roll out on the non-exit side): the -X rails are lowered like the exit-side ones, and the bedside
# table is moved 0.40 m away from the bed so that a body fits between them (0.525 m gap instead of 0.125 m).
TABLE_SHIFT_F3 = -0.40
BLANKET = dict(w=1.30, l=1.50, y0=1.78, thickness=0.012, colour=(0.80, 0.80, 0.74))
BAG = dict(lx=0.25, ly=0.35, h=0.30, floor_xy=(0.78, 2.15), colour=(0.30, 0.16, 0.10))
SLIPPER = dict(l=0.27, w=0.10, h=0.05, colour=(0.15, 0.25, 0.45))
CHAIR_L12_START = (0.98, 3.30)      # chair against the bed side near the head end; pulled to CHAIR (x, y)
