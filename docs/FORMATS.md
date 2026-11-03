# File formats and conventions

Everything a user needs to read the files correctly. Every clip folder `data/<clip>/` has the same layout; `<clip>` is R01 to R62.

## Coordinates and time

- **Room (world) coordinates:** metres; X to the right as seen from the camera on the foot wall, Y towards the head of the bed, Z up, floor at z = 0. The camera wall is y = 0.
- **Camera coordinates** (`cam_xyz_m`): metres, OpenCV axes: x right, y down, z forward along the optical axis.
- **Pixels** (`uv_px`): OpenCV convention: the centre of the top-left pixel is (0, 0).
- **Time:** frame i (counting from 0) is shown at t = i / fps seconds. All clips run at 15 frames per second. Every time in the metadata is a frame number divided by 15.
- **The bed:** mattress 0.90 x 2.00 m, top 0.58 m above the floor, foot end 1.65 m from the camera wall. The bed's outer footprint seen from above is x -0.53 to 0.53 m, y 1.60 to 3.80 m (`bed_rect_m` in the metadata of R41 to R62). The exit side is +X (rails lowered); the bedside table is on the -X side.

## The two cameras

Each clip is seen by two virtual cameras at the same point, matching the two image streams of a Luxonis OAK-D Pro W:

| | Colour camera | Mono camera |
|:--|:--|:--|
| Gives | `<clip>_colour.mp4` | `<clip>_grey.mp4` and the depth PNGs (same pixels) |
| Image size | 640 x 480 | 640 x 400 |
| Horizontal field of view | 95° (published value) | 127° (published value) |
| Vertical field of view | 78.6° (published: 72°) | 102.8° (published: 79.5°) |
| Lens model | pinhole, square pixels, no distortion | the same |

A pinhole with square pixels cannot match both published fields of view at these image sizes, so the horizontal value was kept. The real lenses are strongly distorted; see `KNOWN_ISSUES.md`.

Each camera's calibration is in `<clip>_meta.json` under `camera.colour` and `camera.mono`:

- `intrinsics_opencv`: fx, fy, cx, cy in pixels;
- `world_to_camera_opencv_4x4`: the 4 x 4 matrix taking room coordinates to that camera's OpenCV coordinates.

Camera placement is under `camera`: `position_m`, `aim_point_m`, `yaw_deg`, `pitch_down_deg`, `roll_deg` (always 0). The aim rule: the optical axis passes through the centre of the mattress top, (0, 2.70, 0.58) m. The side view (R13, R17, R21) is level instead.

## Videos

- `<clip>_colour.mp4`: H.264, 640 x 480, 15 frames per second. The room lit by two ceiling panels and a dim sky.
- `<clip>_grey.mp4`: H.264, 640 x 400, 15 frames per second, stored as YUV 4:2:0 with neutral colour. It shows the scene lit only by a spot light at the camera, standing in for the camera's infrared flood light, sRGB-encoded. It does not model how materials reflect at 940 nm, the dot pattern, sensor noise or auto exposure.

Decode every frame as stored. Some decoders duplicate or drop frames when they convert the frame rate. With ffmpeg, use `-fps_mode passthrough` (or `-vsync 0` in older versions) and check that the number of decoded frames equals `frame_count` in the metadata.

## Depth

- `depth/<clip>_depth_NNNNNN.png`: one PNG per frame, NNNNNN = frame number from 000000.
- 16-bit unsigned, one channel, 640 x 400, the same pixels as the grey video.
- Value: millimetres of **planar depth**, the distance along the mono camera's optical axis (not along the ray). 0 means no surface.
- **Seen from the camera,** like the OAK-D's own depth map, which "contains the Z distance" (Luxonis documentation, "Configuring Stereo Depth"). It is not a height map seen from above. In R45, the floor spans depths from 1.4 to 4.5 m, yet comes out at the same height (z = 0) once back-projected. Anything the bed or a person hides from the camera has no depth.
- **Ideal:** no noise, no holes, no minimum range, no dot pattern.
- Each clip's metadata records a check of the depth against ray casts through 40 random pixel centres (`depth.check_against_ray_casts`). The median error is 1.5 to 3 mm.

To turn a depth pixel (u, v) with depth z (in metres) into room coordinates:

1. Camera coordinates: x = (u - cx) z / fx, y = (v - cy) z / fy, z = z.
2. Multiply [x, y, z, 1] by the inverse of `world_to_camera_opencv_4x4` (mono camera).

`code/load_clip.py` does this (`room_points`).

**Empty-room depth** (R41 to R62 only): `<clip>_background_depth.png`, in the same format. It is the mono camera's depth at frame 0 with every person hidden and every object at its frame-0 position. Points to note:

- In L10 the blanket still has the shape of the hidden patient.
- In L11 and L13 the visitor or nurse is out of view at frame 0, and so is the bag.
- In L12 the chair is at its start position.
- In L14 the slippers are on the floor.

## Ground truth: `<clip>_ground_truth.json`

| Key | What |
|:--|:--|
| `point_names` | 24 points: the 17 COCO points (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles), then head top, neck, pelvis, hip centre, shoulder centre, left toe, right toe |
| `coordinates` | the conventions above, as text |
| `person` | body (A or B) and role |
| `frames` | one entry per frame (below) |
| `second_person` | R53, R54, R57, R58 only: the visitor or nurse, with their own `frames` |

Each entry of `frames`:

| Key | What |
|:--|:--|
| `frame`, `t_s` | frame number and time |
| `world` | each point's room coordinates (m) |
| `hip_height_m` | height of the hip centre above the floor |
| `trunk_angle_deg` | angle of the line from hip centre to shoulder centre against vertical (0 = upright, 90 = lying) |
| `hips_on_mattress` | whether the body touches the mattress near the hips |
| `hips_on_chair` | the same for the chair (R23 to R62) |
| `lowest_z` | height of the body's lowest point |
| `lowest_non_foot_z` | height of its lowest point away from the feet (R23 to R62) |
| `colour`, `mono` | per camera: `points` (each with `cam_xyz_m`, `uv_px`, `in_image`, `hidden_by_object`, `hidden_by_other_person`, `hidden_by_body`) and `image_trunk_angle_deg` (the trunk angle as it looks in that picture) |

**Joints are not surfaces.**
- **Ground truth:** the points are joint centres inside the body, from the 3D model, and `hip_height_m` is the height of the hip joint.
- **Depth:** depth at a point's pixel measures the surface the camera sees, which lies between the camera and the joint, so back-projected it reads higher.
- **Size of the gap:** at the true hip-centre pixel, the surface read 6 to 14 cm above the hip joint in six clips we checked:
  - lying in bed, R02: +8 cm;
  - standing, R05: +6 cm;
  - lying on the floor, R45 and R46: +8 and +11 cm;
  - a propped fall ending, R08: +7 cm;
  - sitting on the floor, R48: +14 cm.
- **Compare like with like:** a method that measures heights from depth should allow for this gap before it is scored against these joint heights.

Visibility flags:

- `hidden_by_object`: a ray from the camera to the point first hits the room, the bed, the table or a moving object (blanket, bag, slippers, chair).
- `hidden_by_other_person`: the ray first hits the other person (two-person clips).
- `hidden_by_body`: the ray hits the person's own body more than 15 cm before the point. This is approximate: ankles seen end-on from the foot of the bed can be flagged although the foot is visible.

## Events: `<clip>_meta.json`

`events` lists each event in the clip. Look-alike clips have none. Each event gives:

- `scenario`, `start_frame`, `start_s`, `end_frame`, `end_s`;
- the definition of its start and end (`start_definition`, `end_definition`);
- the exact rule used to find each frame on the rendered body (`start_rule`, `end_rule`).

Falls of R41 to R62 also give `first_floor_touch_frame` and `first_floor_touch_s`.

Event codes:

| Code | Event | Inside |
|:--|:--|:--|
| E1 | sit up in bed | E1 clips, and the start of E4 |
| E2 | legs over the edge | E4 |
| E3 | stand up (hips leave the mattress) | E4, E5 |
| E4 | leave the bed and walk away | |
| E5 | fall while getting out of bed | |
| E6 | slide or roll out of bed to the floor | |
| E7 | fall from sitting on the edge | |
| F1 to F5 | five kinds of fall (see `metadata/scenarios.csv`) | |

For look-alikes, `phases` gives the first and last frame of movement (any point moving more than 5 mm per frame), and `first_stands` gives when the hips leave the mattress, where that happens.

The rest of the metadata:

- `scripted_keyframe_times_s`: the key moments as scripted;
- `person` and `second_person`: each body's description and MakeHuman settings;
- `objects`: when and where the bag, blanket or slippers land;
- `render`: engine, samples, times and machine;
- `solver_checks`;
- `motion_sha256`: the checksum of the motion, identical for all clips of one motion.

## Other files per clip

- `<clip>_motion.json`: the solved motion. For every frame it gives the rig's location and rotation and every bone's rotation (quaternions, w x y z), with the motion's SHA-256.
- `<clip>_contact_sheet.png`: five frames side by side: colour, grey, and depth (shown 0.5 to 6 m, near = bright).
- `keyframes/<clip>_colour_fNNN.png`, `keyframes/<clip>_grey_fNNN.png`: full-size frames at event starts, floor touches and ends. For look-alikes, they show the movement's start and end. NNN = frame number.

## Metadata tables

`metadata/clips.csv`, one row per clip:

| Column | What |
|:--|:--|
| `clip_id` | R01 to R62 |
| `set` | design, fresh or floor_check (see the README) |
| `scenario_id` | E1 to E7, F1 to F5, L1 to L15 |
| `kind` | event or look-alike |
| `expected_alerts` | the alerts a detector should raise (`sit_up`, `stand_up`, `fall`, or `none`), as used in the baseline scoring |
| `alerts_judged` | which alerts the set was made to test. In the floor-check set only the fall alert was judged, so there `expected_alerts` is the fall label: in L12 and L15 the patient does stand up, and in L15 also sits up |
| `body`, `second_person_body` | A (male, about 74 years, 1.71 m) or B (female, about 79 years, 1.55 m, heavier build) |
| `camera_position`, `camera_label` | camera key and description |
| `camera_height_m`, `camera_pitch_down_deg` | camera height and downward tilt |
| `fps`, `frames`, `duration_s` | 15, frame count, length |
| `events` | each event's code and start and end times |
| `has_background_depth` | 1 for R41 to R62 |

`metadata/scenarios.csv`, one row per scenario:

- `scenario_id`, `kind`, `name`;
- the start and end definitions;
- `clips`: which clips use it.

For F1 to F5 and L9 to L15, the `event_start` column holds the scripted description instead.

`metadata/SHA256SUMS.txt`: the SHA-256 of every file under `data/`. Check with `sha256sum -c metadata/SHA256SUMS.txt` from the folder that holds `data/`.

## The AI-generated part

Files:
- `data/generated/videos/<batch>_<clip>.mp4`: H.264, 1280 x 720, 5 to 8 s. Wan videos run at 16 frames per second; Veo and Seedance at 24. Veo videos also carry AAC sound made by the model.
- `data/generated/start_pictures/SF<n>.png`: the 12 start pictures, 1440 x 810.

Every file is exactly as the service returned it, with the makers' provenance marks (C2PA manifests; SynthID in the Veo videos). Decode with frame-rate passthrough, as for the simulations: without it, ffmpeg can repeat frames of the 16 frames-per-second Wan videos.

Naming:
- **`b1`**: the first batch, 8 Wan videos, with a short prompt.
- **`b2`**: the second batch, 44 videos (24 Wan, 16 Veo, 4 Seedance). The prompt starts with a long instruction to keep the camera still; Wan and Veo also got a negative prompt against camera movement.
- **Clip prefixes:** SW is Wan, SV is Veo and SS is Seedance. The number is the start picture it animates: SW3, SV3 and SS3 all start from SF3. `_a1` and `_a2` are two attempts with different seeds.

`metadata/generated_videos.csv`, one row per video:

| Column | What |
|:--|:--|
| `file`, `batch`, `clip_id` | where it is, and its name in the generation record |
| `generator`, `maker`, `service`, `endpoint` | the model, who made it, and the service and model address it was called through |
| `scenario_id`, `scenario_name`, `kind` | the scenario the prompt asked for (codes as in `metadata/scenarios.csv`, plus E2, E3, L2 and L5) |
| `requested_alert` | the alert that scenario should raise: `sit_up`, `stand_up`, `fall`, `staff` (a nurse with the patient) or `none`. Not checked against the video |
| `start_picture` | the start picture it animates |
| `prompt`, `parameters` | the prompt and the other settings sent, as JSON |
| `seed_sent`, `seed_reported` | the seed sent, and the one the service reported (empty if it reported none) |
| `generated_utc` | when the request finished |
| `frames`, `fps`, `width`, `height`, `duration_s`, `has_audio` | as read from the file |
| `camera_zoom_max_pct`, `camera_shift_max_pct`, `camera_moved` | the largest zoom and shift of the view against the first frame, in percent; `camera_moved` is True above 1.5%. Fixed real cameras measured at most 0.36% |
| `sha256` | the file's checksum, the same as recorded when it was made |

`metadata/generated_start_pictures.csv`, one row per start picture:
- `scenario_id`, `prompt`, `parameters`;
- `candidate_chosen`: which of the four candidates drawn was kept;
- `used_by_videos`;
- `sha256`.

`baseline/results/generated_picture_rule.csv`, for the second batch: `person_found_share` (the share of frames in which the pose model found a person) and the alerts of picture rules v1 and v2 (`baseline/rules/posture_rules.py`, `posture_rules_v2.py`), which judge posture from the trunk's angle in the picture without depth.

## Baseline body points: `baseline/body_points/<clip>_<grey|colour>.npz`

Body points found by an off-the-shelf pose model, as read by the baseline rules. The model is RTMPose-m with the YOLOX-m person finder, through rtmlib 0.0.16 in "balanced" mode, run on every frame of each video.

| Array | Shape | What |
|:--|:--|:--|
| `t` | (frames,) | time of each frame, s |
| `kpts` | (frames, 4, 17, 2) | up to 4 people per frame, 17 COCO points, pixel x and y |
| `scores` | (frames, 4, 17) | each point's confidence |
| `boxes` | (frames, 4, 4) | each person's box, x0 y0 x1 y1 (NaN where fewer than 4 people were found) |
| `size` | (2,) | image width and height |
| `native_fps`, `seconds` | | the video's frame rate and length |

These are model outputs, not ground truth. They can be wrong, and on the floor they often are.
