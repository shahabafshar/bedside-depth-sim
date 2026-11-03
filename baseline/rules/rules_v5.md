# Rules version 5: v4 plus a floor check that needs no pose model (plan step S4)

**Written and frozen:** 2026-10-19, before any test clip for it existed (`MASTER_PLAN.md`, step S4). Designed on made-up scenes only; no render was used to set a value. Checksums in `FROZEN_v5.json`.

## Why

On 18 fresh renders, v4 caught 2 of 10 falls: the person detector stopped finding the patient once they lay on the floor, so no rule built on body points could fire (`research/synthetic_video/pilot/results/RENDERS_diagnosis.md`). The OAK-D sees the room's depth all the time, so a patient on the floor can be found without a pose model.

## The floor check

Per frame, on the depth picture alone:
1. **New:** pixels at least 5 cm closer to the camera than the empty room (the room's depth without anyone in it, from the same camera: on the product, captured at installation and refreshed while the room is empty; in renders, the scene at frame 0 without the person).
2. **Low:** placed in the room, between 0.10 and 0.40 m above the floor. Below 0.10 m is a blanket or clothes on the floor; above 0.40 m is a chair seat, a bed, or a standing person's upper body.
3. **Near the bed, not on it:** within 1.5 m of the bed's footprint (marked once at installation), outside the footprint plus 5 cm.
4. **Person-sized and person-long:** the points are put on a 5 cm floor grid and split into separate objects; an object counts if it is at least 0.6 m long (bounding-box diagonal) and covers at least 0.10 m2. Sizes from people and objects, not from data: an adult lying on the floor covers more than 0.25 m2 and is over 1 m long; sitting on the floor with legs out, about 0.13 m2 and about 0.75 m; a typical bag about 0.09 m2 and under 0.5 m.
5. **The bed is empty:** fewer than 0.08 m2 of new points at least 0.12 m above the empty mattress (so a nurse kneeling beside a patient who is still in bed does not count).
6. **Alert:** steps 1 to 5 hold in at least 80% of the frames of a 2 s window; the alert time is the end of that window (about 1.5 to 2 s after the patient reaches the floor).

Every pixel is used (at 3.5 m the camera's pixels are about 2 cm apart, finer than the grid). A fall is raised by v4's drop rule or by the floor check; `fall_path` says which. A patient sitting on the floor raises it too: a patient on the floor is an emergency whether or not the descent looked like a fall.

Not included, to keep v5 simple: the "lost right after a fast drop" signal mentioned in the plan. If the floor check misses, plan step S4b (a person detector that keeps lying people) is next.

Thresholds: `rules_v5.json` (v4's values plus the floor check's). Code: `posture_rules_v5.py` (imports the frozen v4, v3 and v1 modules). Tests: `test_posture_rules_v5.py`, 10 ray-traced scenes from a camera like the renders', all as specified: lying on the floor beside the bed and right against it, and sitting on the floor, raise the alert; lying in bed, a dropped blanket, a blanket or a bag or a chair beside an empty bed, a nurse kneeling beside a patient in bed, and someone standing beside an empty bed do not.

**Known limits, stated before testing:** a large low object brought next to an empty bed (a suitcase over 0.6 m long) would raise it; a patient who ends on the floor hidden behind something taller than 0.40 m, or at the head end behind the bed, would not be seen; depth on the OAK-D has noise and holes the renders do not.

## How it is judged (decision rule in `MASTER_PLAN.md`, S4)

Fresh renders made after this freeze, from the foot wall at 1.8 and 2.2 m, both bodies, each with its empty-room depth picture: 10 falls (new fall motions, including falls where the bed or bedside table hides part of the body) and look-alikes (a blanket sliding to the floor, a bag put down beside the bed, a chair moved beside the bed, a nurse kneeling beside the bed with the patient in it, sitting on the edge putting on slippers, getting up and walking out). **Go to S5 if at least 9 of 10 falls are caught and at most 1 look-alike clip raises a fall alert.** Otherwise as the plan says.
