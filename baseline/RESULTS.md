# Baseline results

The locked rules in `rules/`, run by `evaluate.py` on this dataset with the body points in `body_points/`. These are the results the build reproduces exactly (`results/reproduced.csv`). In the design and fresh sets a clip counts as correct when the rule raises exactly its expected alerts. The floor-check set was made to test the fall alert only, so there only the fall alert is judged: its expected column is the fall label, and sit-up or stand-up alerts are not scored (in L12 and L15 the patient does stand up). Clips of one motion seen from several cameras are one event, not several.

## Design set R01 to R22 (seen while v4 was designed)

| Clip | Scenario | Camera | Expected | Rules v3 | Rules v4 | Rules v5 fall |
|---|---|---|---|---|---|---|
| R01 | E1 | foot wall, centred, 1.8 m | sit_up | sit_up | sit_up | n/a |
| R02 | E1 | foot wall, centred, 2.2 m | sit_up | sit_up | sit_up | n/a |
| R03 | E1 | foot wall, centred, 2.6 m | sit_up | sit_up | sit_up | n/a |
| R04 | E4 | foot wall, centred, 1.8 m | sit_up stand_up | sit_up stand_up | sit_up stand_up | n/a |
| R05 | E4 | foot wall, centred, 2.2 m | sit_up stand_up | sit_up stand_up | sit_up stand_up | n/a |
| R06 | E4 | foot wall, centred, 2.6 m | sit_up stand_up | sit_up stand_up | sit_up stand_up | n/a |
| R07 | E6 | foot wall, centred, 1.8 m | fall | none | fall | n/a |
| R08 | E6 | foot wall, centred, 2.2 m | fall | none | fall | n/a |
| R09 | E6 | foot wall, centred, 2.6 m | fall | none | fall | n/a |
| R10 | L1 | foot wall, centred, 2.2 m | none | none | none | n/a |
| R11 | E1 | foot wall, 0.5 m left of the bed's centre line (as seen from the camera), 2.2 m | sit_up | sit_up | sit_up | n/a |
| R12 | E1 | foot wall, 0.5 m right of the bed's centre line (as seen from the camera), 2.2 m | sit_up | sit_up | sit_up | n/a |
| R13 | E1 | side view like GMDCSA-24: 1.0 m high, 3 m from the bed's long side, level | sit_up | none | none | n/a |
| R14 | E1 | high room corner like CAUCAFall: 2.6 m, foot-end corner away from the exit side | sit_up | none | none | n/a |
| R15 | E4 | foot wall, 0.5 m left of the bed's centre line (as seen from the camera), 2.2 m | sit_up stand_up | sit_up stand_up | sit_up stand_up | n/a |
| R16 | E4 | foot wall, 0.5 m right of the bed's centre line (as seen from the camera), 2.2 m | sit_up stand_up | sit_up stand_up | sit_up stand_up | n/a |
| R17 | E4 | side view like GMDCSA-24: 1.0 m high, 3 m from the bed's long side, level | sit_up stand_up | stand_up | stand_up | n/a |
| R18 | E4 | high room corner like CAUCAFall: 2.6 m, foot-end corner away from the exit side | sit_up stand_up | none | none | n/a |
| R19 | E6 | foot wall, 0.5 m left of the bed's centre line (as seen from the camera), 2.2 m | fall | none | fall | n/a |
| R20 | E6 | foot wall, 0.5 m right of the bed's centre line (as seen from the camera), 2.2 m | fall | none | fall | n/a |
| R21 | E6 | side view like GMDCSA-24: 1.0 m high, 3 m from the bed's long side, level | fall | none | none | n/a |
| R22 | E6 | high room corner like CAUCAFall: 2.6 m, foot-end corner away from the exit side | fall | none | none | n/a |

Rules v3: exactly the expected alerts in 11 of 22 clips.

## Fresh set R23 to R40 (made after v4 was locked)

| Clip | Scenario | Camera | Expected | Rules v3 | Rules v4 | Rules v5 fall |
|---|---|---|---|---|---|---|
| R23 | E5 | foot wall, centred, 2.2 m | fall stand_up | stand_up | fall stand_up | n/a |
| R24 | E5 | foot wall, centred, 1.8 m | fall stand_up | stand_up | stand_up | n/a |
| R25 | E7 | foot wall, centred, 2.2 m | fall | none | none | n/a |
| R26 | E7 | foot wall, centred, 1.8 m | fall | none | none | n/a |
| R27 | L7 | foot wall, centred, 2.2 m | none | none | none | n/a |
| R28 | L7 | foot wall, centred, 1.8 m | none | none | none | n/a |
| R29 | L9 | foot wall, centred, 2.2 m | none | none | none | n/a |
| R30 | L9 | foot wall, centred, 1.8 m | none | none | none | n/a |
| R31 | E5 | foot wall, centred, 2.2 m | fall stand_up | stand_up | stand_up | n/a |
| R32 | E5 | foot wall, centred, 1.8 m | fall stand_up | stand_up | stand_up | n/a |
| R33 | E7 | foot wall, centred, 2.2 m | fall | none | none | n/a |
| R34 | E7 | foot wall, centred, 1.8 m | fall | none | none | n/a |
| R35 | E6 | foot wall, centred, 2.2 m | fall | none | fall | n/a |
| R36 | E6 | foot wall, centred, 1.8 m | fall | none | none | n/a |
| R37 | L7 | foot wall, centred, 2.2 m | none | none | none | n/a |
| R38 | L7 | foot wall, centred, 1.8 m | none | none | none | n/a |
| R39 | L9 | foot wall, centred, 2.2 m | none | none | none | n/a |
| R40 | L9 | foot wall, centred, 1.8 m | none | none | none | n/a |

Rules v4: exactly the expected alerts in 10 of 18 clips.

## Floor-check set R41 to R62 (made after v5 was locked)

| Clip | Scenario | Camera | Expected fall | Rules v3 | Rules v4 | Rules v5 fall |
|---|---|---|---|---|---|---|
| R41 | F1 | foot wall, centred, 2.2 m | fall | stand_up | fall stand_up | 1 |
| R42 | F1 | foot wall, centred, 1.8 m | fall | stand_up | stand_up | 1 |
| R43 | F2 | foot wall, centred, 1.8 m | fall | fall | fall | 1 |
| R44 | F2 | foot wall, centred, 2.2 m | fall | fall | fall | 1 |
| R45 | F3 | foot wall, centred, 2.2 m | fall | none | fall | 1 |
| R46 | F3 | foot wall, centred, 1.8 m | fall | none | none | 1 |
| R47 | F4 | foot wall, centred, 1.8 m | fall | none | fall | 1 |
| R48 | F4 | foot wall, centred, 2.2 m | fall | fall | fall | 1 |
| R49 | F5 | foot wall, centred, 2.2 m | fall | none | none | 1 |
| R50 | F5 | foot wall, centred, 1.8 m | fall | none | none | 1 |
| R51 | L10 | foot wall, centred, 2.2 m | none | none | none | 0 |
| R52 | L10 | foot wall, centred, 1.8 m | none | none | none | 0 |
| R53 | L11 | foot wall, centred, 2.2 m | none | none | none | 0 |
| R54 | L11 | foot wall, centred, 1.8 m | none | none | none | 0 |
| R55 | L12 | foot wall, centred, 2.2 m | none | stand_up | stand_up | 0 |
| R56 | L12 | foot wall, centred, 1.8 m | none | stand_up | stand_up | 0 |
| R57 | L13 | foot wall, centred, 2.2 m | none | none | none | 0 |
| R58 | L13 | foot wall, centred, 1.8 m | none | none | none | 1 |
| R59 | L14 | foot wall, centred, 2.2 m | none | sit_up | sit_up | 0 |
| R60 | L14 | foot wall, centred, 1.8 m | none | none | none | 0 |
| R61 | L15 | foot wall, centred, 2.2 m | none | sit_up stand_up | sit_up stand_up | 0 |
| R62 | L15 | foot wall, centred, 1.8 m | none | sit_up stand_up | sit_up stand_up | 0 |

Rules v5: falls caught 10 of 10; look-alikes with a fall alert 1 of 12.

A fault found after scoring: v5 estimates the mattress top as the 90th percentile height of the empty room's points over the bed, and in every clip the camera also sees the ceiling above the bed, so the estimate reads about 3 m. The guard that should silence the floor check while the patient is in bed therefore never acts, and the two nurse clips (L13) were decided by floor area alone. The result is reported as locked; a fixed version would be a new version, judged on new clips.

## AI-generated videos, second batch (44 clips)

The picture rules (v1, and v2 with a 3 s fall confirmation) read posture from the trunk's angle in the picture, with no depth, using the colour video. `results/generated_picture_rule.csv` gives, per clip, the requested event, whether the camera moved, the share of frames with a person found, and each rule's alerts. The requested event is what the prompt asked for; whether each clip shows it has not been checked by blind labelling.

Sit-up requested: 12 clips; caught by v2 in 0. Seen from the wall in front of the bed, a patient lying down looks upright in the picture, so the picture rules do not see lying; this is why rules v3 to v5 use depth.

