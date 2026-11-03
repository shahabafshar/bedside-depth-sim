# Rules version 3: posture in 3D from the depth camera, frozen before any render was scored

**Written and frozen:** 2026-10-19, after the synthetic pilot showed that v1 and v2 cannot see lying from the wall in front of the bed (`research/synthetic_video/pilot/results/SUMMARY.md`: median trunk angle 2 degrees in the image while lying), and **before any rendered clip's depth was read or any v1, v2 or v3 result on the renders was seen**. Checksums in `FROZEN_v3.json`.

## Why

v1 and v2 judge posture from the trunk's angle in the picture. From the product's camera position, on the wall in front of the bed, a patient lying on their back has the head above the hips in the picture, as if upright. The first test found the same with AURA's overhead camera. The OAK-D Pro W measures depth and has a motion sensor, so the body points can be placed in the room.

## What v3 does

The same body points from the same pose model (on the image the depth is aligned to: the mono cameras on the OAK-D Pro W, the grey video in the renders).

1. **Depth at each point:** the 30th percentile of the valid depth values in a 7 x 7 pixel window around the point (a low percentile, so a point on the body's edge takes the body, not the wall behind it). Valid: 0.3 to 12 m.
2. **Room coordinates:** back-projected with the camera's intrinsics, then turned into room coordinates with z up and the floor at 0. On the product, gravity comes from the camera's motion sensor (BNO086) and the floor from a plane fitted to the depth; in the renders, from the scene file.
3. **Measures per frame:** trunk angle to vertical (shoulder centre minus hip centre; 0 upright, 90 lying), thigh angle to straight down (hip centre to knee centre; 0 standing, about 90 sitting), hip height above the floor.
4. **Posture:** lying if the trunk is at least 60 degrees from vertical; if it is within 35 degrees: standing if the thigh is within 35 degrees of straight down and the hips are at least 0.65 m up; sitting if the thigh is at least 50 degrees from straight down, or, with the knees hidden (a blanket), if the hips are below 0.65 m; otherwise upright. Between 35 and 60 degrees: unknown. Smoothing, stable runs (0.8 s), tracking of the main person and the staff rule are v1's, unchanged.
5. **Sit-up and stand-up:** as v1, on these postures (stand-up through an upright run needs the hips to rise 0.2 m).
6. **Fall (on the floor):** the hips come down to at most 0.30 m above the floor within 1 s of being at least 0.45 m up, and stay below 0.45 m for 1.5 s (at least 60% of those frames with a known hip height). A slow, deliberate lowering to the floor is not called a fall; touching the floor and getting up within 1.5 s is not either. This is an "on the floor after a fast descent" alert: a patient who ends on the floor is an emergency whether or not the descent looked like a classic fall.

Thresholds: `rules_v3.json`. Code: `posture_rules_v3.py` (imports the frozen `posture_rules.py`). Tests: `test_posture_rules_v3.py`, 9 made-up movements seen by a camera like the renders' (2.2 m, aimed at the mattress centre), all as specified, including that v1 calls the same lying patient upright.

## How it is scored (first on the renders)

On the 22 Blender renders (`research/synthetic_video/pilot/clips/render/`): pose on the grey video (the depth camera's pixels), v3 with the scene's camera pose, against the renders' exact event times (E1 sit-up, E4 leaving the bed, E6 slide out of bed to the floor, L1 turning onto the side with no event). Reported for each camera position: did v3 raise the expected alert and nothing else, and how late; side by side with v1 and v2 on the same clips (colour and grey). The renders' depth is ideal (no noise or holes) and their motion is hand-keyed, so this shows whether the idea works, not how well it will work on the OAK-D: that needs the real camera.
