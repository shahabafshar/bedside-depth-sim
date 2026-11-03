# Baseline

Simple detection rules, locked before the clips that test them were made or scored, and their results on this dataset. They are a reference point for other methods, not a recommended detector.

## Run

```
pip install numpy pillow scipy
python baseline/evaluate.py data                 # writes baseline/results/reproduced.csv
python baseline/rules/test_posture_rules_v5.py   # the rules' own tests on made-up scenes (also v3, v4)
```

`evaluate.py` reads the body points in `body_points/` and the depth images in `data/`. For R41 to R62 it also reads the empty-room depth. It writes one row per clip:
- `v3`, `v4`: the alerts raised;
- `v4_fall`, `v5_fall`: 1 if a fall alert was raised;
- `v5_fall_path`: which part of v5 raised it;
- `v5_alert_s`: when.

## The three versions

| Version | Locked (UTC) | What it adds | Judged on |
|:--|:--|:--|:--|
| v3 | 2026-10-19 21:08 | Posture from depth: the body points are placed in the room using the depth image, then trunk angle, thigh angle and hip height decide lying, sitting and standing. Raises sit-up, stand-up, and a fall when the hips come down to 0.30 m or less and stay low | design set R01 to R22 (rendered before the lock, not yet scored) |
| v4 | 2026-10-19 21:23 | A new fall rule for a fast drop: the hips fall at least 0.30 m within 1 s and stay at or below 0.50 m, allowing for depth measuring the body's surface rather than its joints | fresh set R23 to R40 (rendered after the lock) |
| v5 | 2026-10-20 01:19 | A floor check on depth alone, needing no pose model: pixels closer than the empty room, 0.10 to 0.40 m above the floor beside the bed, forming a person-sized object for most of 2 s while the bed is empty | floor-check set R41 to R62 (rendered after the lock) |

Each lock is recorded in `rules/FROZEN_<version>.json`: the time and the SHA-256 of every file the version uses.
- **Files:** the rule descriptions (`rules_<version>.md`, with each pass mark written before testing), settings (`rules_<version>.json`), code and tests.
- **Copies:** the files here are byte-identical copies. The release build checks every checksum.
- **References:** the descriptions and code comments mention notes and folders of the project that made them; those are not part of this release.

## The picture rules (v1, v2), for the AI-generated videos

Before depth was used, posture was read from the trunk's angle in the picture alone: rules v1 (`rules/posture_rules.py`, `rules/rules_v1.json`) and v2, which adds a 3 s confirmation for falls (`rules/posture_rules_v2.py`, `rules/rules_v2.json`, `rules/rules_v2.md`). Their lock records are `rules/FROZEN_v1.json` and `FROZEN_v2.json`. Some files those records list (v1's description, the project's scoring and labelling scripts) are not released; every listed file that is released matches its checksum.

`results/generated_picture_rule.csv` gives their alerts on the 44 second-batch generated videos. From the wall in front of the bed a lying patient looks upright in the picture, so these rules rarely see a sit-up there; that finding is why v3 to v5 use depth.

## Body points

`body_points/<clip>_grey.npz` and `<clip>_colour.npz` hold the output of an off-the-shelf pose model run on every frame of each video:
- **Pose model:** RTMPose-m (17 COCO points).
- **Person finder:** YOLOX-m.
- **Software:** rtmlib 0.0.16 in "balanced" mode.
- **What the rules use:** the grey files only.

The format is in `docs/FORMATS.md`. These are model outputs, not ground truth.

## Results

`RESULTS.md` lists every clip; `results/` holds the scored tables and the reproduction.

| Version | On | Result |
|:--|:--|:--|
| v3 | design set | exactly the expected alerts in 11 of 22 clips; all 10 sit-up and bed-exit clips from the foot wall right, 0 of 7 falls |
| v4 | fresh set | exactly the expected alerts in 10 of 18 clips; stand-ups 4 of 4, look-alikes quiet 8 of 8, falls 2 of 10 |
| v5 | floor-check set | falls 10 of 10; look-alikes with a fall alert 1 of 12 |

How to read these:
- **Not independent:** clips of one motion from several cameras, or by both bodies, are not independent. The 10 falls of the floor-check set are 5 motions, each by both bodies.
- **The v5 fault:** a fault in v5 was found after scoring (`RESULTS.md`): its check for a patient in bed took the ceiling for the mattress and never acted.
- **The v3 and v4 fall misses:** in several missed falls, the person finder lost the patient on the floor. The pinhole lens, which shows people smaller than the real camera would, and the propped fall endings (`docs/KNOWN_ISSUES.md`) may have made this worse.
