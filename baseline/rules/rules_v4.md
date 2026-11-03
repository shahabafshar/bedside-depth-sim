# Rules version 4: v3 with a fall rule that allows for the depth camera seeing the surface

**Written and frozen:** 2026-10-19, after v3 was scored on the first 22 renders (`research/synthetic_video/pilot/results/RENDERS.md` and `RENDERS_diagnosis.md`) and **before any of the fresh test renders (R23 onwards) existed**. v4 was designed after seeing those 22 renders, so they are not evidence that v4 works; the fresh renders are. Checksums in `FROZEN_v4.json`.

## The change

v3 placed each body point at the depth of the surface the camera sees. A patient lying on the floor measured about 0.4 m up and never reached v3's floor threshold of 0.30 m, so v3 missed all 5 rendered falls.

v4 changes only the fall rule. **A fall: within 1 s the hip height drops by at least 0.30 m and ends at or below 0.50 m (0.40 m if the trunk is upright then, so that sitting down on a chair is not a fall); the hips then stay at or below that limit plus 0.05 m for 1.5 s (60% of those frames with a known height).** Posture, sit-up, stand-up, staff and everything else are v3's.

Thresholds: `rules_v4.json` (v3's values without the two floor-height values, plus `fall_drop_min_m` 0.30, `floor_surface_max_m` 0.50, `floor_surface_upright_max_m` 0.40, `floor_hold_margin_m` 0.05). Code: `posture_rules_v4.py`. Tests: `test_posture_rules_v4.py`, 9 made-up movements with the depth placed 0.12 m in front of each joint (the surface), all as specified: falls from bed and from standing are found; sitting down quickly on a chair, lowering slowly to the floor over 6 s, touching the floor for 0.6 s, and lying in bed are not falls; sit-up and stand-up still found.

## Known limit, stated before testing

A patient dropping quickly onto a very low bed (mattress top below about 0.4 m) could meet the rule. The bed's height can be measured from the depth; that is for a later version if it matters.

## How it is scored

On fresh renders made after this freeze: new falls (after standing, from the edge of the bed), a second body, and look-alikes that come close to the rule (sitting down quickly on a chair beside the bed, sitting on the edge and lying back down), from the foot wall. Reported per clip: expected alerts against v4's (and v1, v2 and v3 alongside), and the delay from the exact event start.
