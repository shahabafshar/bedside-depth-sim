# Bedside Depth Simulations

Simulated bed exits, falls and look-alike movements, seen by a depth camera on the wall in front of a hospital bed, with AI-generated hospital videos from the same camera position. Version 1.0.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23926720.svg)](https://doi.org/10.5281/zenodo.23926720)

> **Release status:** prepared, not yet published. The DOI is reserved and becomes active when the Zenodo record is published. Authors and affiliation are marked TO BE CONFIRMED.

## What this is

Two parts:

- **3D simulations** (the main part): 62 rendered clips with depth and exact ground truth, described first below.
- **AI-generated videos** (a second, separate part): 52 short colour videos of hospital scenes, made by video generation models from 12 generated start pictures, all seen from the wall in front of the bed. They have no depth and no verified labels. See "The AI-generated videos" below; they have their own licence.

### The 3D simulations

62 short clips rendered in 3D. Each shows a patient in a hospital room, and in some clips a second person (a nurse or a visitor), seen by a virtual camera placed where a wall-mounted depth camera (a Luxonis OAK-D Pro W) would hang: on the wall at the foot of the bed, looking along it. Six clips of the first set use other camera positions for comparison.

For every clip the dataset gives:

- a colour video and a grey, infrared-like video;
- an ideal depth image for every frame (16-bit, millimetres);
- the exact time each event starts and ends;
- the 3D position of 24 body points in every frame (the 17 COCO points plus head top, neck, pelvis, hip and shoulder centres and toes), with whether each is hidden;
- the camera's position and calibration.

The 22 clips of the third set also give the depth of the empty room.

The clips were made to test rules that detect a patient sitting up, leaving the bed or falling, from this camera position. Of the 53 public datasets we checked, none shows real patients leaving hospital beds from this position.

## At a glance

| | |
|:--|:--|
| Clips | 62 (R01 to R62), 5 to 14 s each, 15 frames per second |
| Depth frames | 7,217, plus 22 empty-room depth images |
| Events | sitting up, leaving the bed, falls (eight kinds) |
| Look-alikes | turning in bed, lying back down, sitting on a chair, a blanket or bag on the floor, a nurse kneeling, putting on slippers, walking away |
| People | two bodies, from the free MakeHuman / MPFB assets (CC0): A, male, about 74 years; B, female, about 79 years |
| Camera positions | wall in front of the bed at 1.8, 2.2 and 2.6 m; the same wall 0.5 m left and right; a low side view; a high room corner |
| Ground truth | event start and end times; per frame, 3D body points, hip height, trunk angle, contact with mattress or chair, visibility |
| Size | 282 MB (a 201 MB zip archive) |
| AI-generated part | 52 videos (32 Wan 2.2, 16 Veo 3.1 Fast, 4 Seedance 2.0), 1280 x 720, 5 to 8 s; 12 start pictures (Seedream 5.0 Pro); 135 MB |
| Licence | 3D simulations CC BY 4.0 (`LICENSE`); AI-generated part its own licence (`LICENSE-GENERATED`); code Apache-2.0 (`LICENSE-CODE`), except the Blender scripts, GPL-3.0-or-later |

## The three sets

The clips were made in three batches, each after a version of our detection rules was locked, so each later set is a fair test of the rules locked before it.

| Set | Clips | What it holds |
|:--|:--|:--|
| Design | R01 to R22 | One sit-up, one bed exit and one roll out of bed, each from seven camera positions, and one turn in bed. Used while designing rules, so not a fair test of rules designed on it |
| Fresh | R23 to R40 | Falls after standing and from the edge of the bed, a roll out of bed, lying back down and sitting down quickly on a chair; two bodies, cameras at 2.2 and 1.8 m |
| Floor check | R41 to R62 | 10 falls (5 kinds, each by both bodies) and 12 look-alikes, cameras at 2.2 and 1.8 m, each with the empty room's depth. Labelled for the fall alert only |

`metadata/clips.csv` lists every clip: set, scenario, expected alerts, body, camera, frames and event times. `metadata/scenarios.csv` describes each scenario. `docs/FORMATS.md` explains every file and field.

## Files

```
data/R45/                       one folder per clip
  R45_colour.mp4                colour video (the camera's colour sensor, 640 x 480)
  R45_grey.mp4                  grey infrared-like video (the depth camera's pixels, 640 x 400)
  depth/R45_depth_000000.png    depth per frame, uint16 millimetres, 0 = no data
  R45_background_depth.png      the empty room's depth (R41 to R62 only)
  R45_ground_truth.json         per-frame body points, hip height, trunk angle, visibility
  R45_meta.json                 camera, events, scenario, people, objects, render settings
  R45_motion.json               the keyed motion
  R45_contact_sheet.png         frames at a glance
  keyframes/                    colour and grey frames at event starts and ends
data/generated/videos/          the AI-generated videos, b1_SW1_a1.mp4 and so on
data/generated/start_pictures/  the generated start pictures they begin from, SF1.png to SF12.png
metadata/                       clips.csv, scenarios.csv, generated_videos.csv, generated_start_pictures.csv, checksums
baseline/                       locked detection rules, their results, the body points they read
code/                           load_clip.py; render/ (the Blender pipeline)
docs/                           FORMATS.md (all conventions), KNOWN_ISSUES.md
DATASHEET.md                    the questions of "Datasheets for Datasets", answered
CHANGELOG.md                    versions, and what was changed for release
CITATION.cff                    how to cite
```

The data is in two Zenodo archives: `bedside-depth-sim_v1.0_data.zip` (the 3D simulations) and `bedside-depth-sim_v1.0_generated.zip` (the AI-generated part). The repository holds everything else. Unzip the archives next to the repository so that `data/` sits beside `metadata/`. Check them with `sha256sum -c metadata/SHA256SUMS.txt` and `sha256sum -c metadata/SHA256SUMS_generated.txt`.

## Quick start

```
pip install numpy pillow scipy
python code/load_clip.py data/R45          # one clip: events, depth range, floor height, hip height
python baseline/evaluate.py data            # run the locked rules on every clip
```

## Baseline

`baseline/` holds the detection rules as they were locked before each test, the body points they read (from RTMPose-m with the YOLOX-m person finder, run on the grey videos), and their results. `baseline/RESULTS.md` lists every clip; the release build checks that `evaluate.py` reproduces those results exactly. In short:

| Rules | What they do | Judged on | Result |
|:--|:--|:--|:--|
| v3 | posture from depth | design set | exactly the expected alerts in 11 of 22 clips; every sit-up and bed exit from the wall in front of the bed, no falls |
| v4 | v3 plus a fast drop to the floor | fresh set | 10 of 18 clips; stand-ups 4 of 4, look-alikes quiet 8 of 8, falls 2 of 10 |
| v5 | v4 plus a floor check on depth alone | floor-check set | falls 10 of 10; look-alikes with a fall alert 1 of 12 |

These are small samples from simulation, and several clips show one motion from several cameras. They show what the rules do on this material, not how they would do in a hospital. After scoring, a fault was found in v5's check for a patient in bed (it took the ceiling for the mattress); `baseline/RESULTS.md` explains it.

## Read before use

`docs/KNOWN_ISSUES.md` lists what is wrong or simplified. The most important points:

- **Ideal depth, seen from the camera.** No noise, no holes, no minimum range: real depth cameras are worse, and get worse with distance. The depth measures the body's surface as the camera sees it, which reads 6 to 14 cm above the joint heights of the ground truth (`docs/FORMATS.md`).
- **An exactly known camera pose.** A real camera must estimate its tilt. A 2° error moves the floor about 9 cm at 3.6 m.
- **A simple lens.** A pinhole camera with the published fields of view, without the real lens's distortion, so people near the centre look about 45% smaller than through the real lens.
- **Lifted fallen bodies.** In R07 to R09, R19 to R26 and R31 to R36, the fallen body rests on one hand, 10 to 19 cm above the floor. The falls of R41 to R50 lie flat.
- **Hand-keyed motion, one room, two bodies,** and a second person who is the same model as the patient of other clips.

## How it was made

Blender 4.5.14 LTS (Eevee) with MakeHuman / MPFB 2.0.18 bodies (CC0). Motions were keyed by hand. Event times come from the animation itself, with the rule for each start and end given in `metadata/scenarios.csv` and each clip's `_meta.json`. The camera sits where the real camera would, pointed at the centre of the mattress, with the OAK-D Pro W's published fields of view. `code/render/` holds the pipeline. The Blender scene files are not included, because they embed local paths. The scripts rebuild them, given Blender and the MPFB add-on.

## The AI-generated videos

Made to see what a patient looks like from our camera position in a realistic hospital room, before any real recording exists.

**How they were made.** All requests went through the fal.ai service. Each `metadata/` table records, per file, the model, prompt, settings, seed and time.
1. **Start pictures.** Twelve were drawn from text alone by Seedream 5.0 Pro (ByteDance), each as a still from a camera high on the wall at the foot of a hospital bed. Four candidates were drawn per prompt, and the first that met a fixed checklist was kept.
2. **Videos.** Each picture was animated with a prompt describing one event or look-alike, by:
   - Wan 2.2 A14B (Alibaba): 32 videos, in two batches;
   - Veo 3.1 Fast (Google): 16 videos;
   - Seedance 2.0 (ByteDance): 4 videos.

**What they cover.** Sitting up, legs over the edge, standing up, three kinds of fall; and turning, reaching, lying back down and a nurse helping (look-alikes). `metadata/generated_videos.csv` lists them.

**Read before use.**
- **Labels not checked.** The scenario is what the prompt asked for. Whether each video shows it has not been checked by blind labelling.
- **Moving camera.** A wall camera does not move, but 13 of the 16 Veo videos and 4 of the 32 Wan videos (all in the first batch) zoom or shift more than 1.5% (`camera_moved`).
- **No depth.** The videos are colour only, with no depth or ground truth.
- **Frame rates.** Wan videos run at 16 frames per second, Veo and Seedance at 24. Veo videos carry generated sound.
- **Files as made.** They are released byte for byte as returned by the service; each matches the checksum recorded when it was made. They keep their makers' provenance marks: C2PA manifests, and Google's SynthID in the Veo videos.

**Results.** `baseline/results/generated_picture_rule.csv` gives the picture rules' alerts on the second batch.

## What is not included, and why

- **Copies of public dataset clips:** they show real volunteers, whose likeness is not covered by those datasets' licences.

## Ethics

All people in the 3D simulations are computer models built from CC0 assets. The people in the AI-generated part are invented by the models: the start pictures were made from text alone, with no photograph of a real person as input. The dataset holds no recordings of real people and no patient data.

## Intended use

Testing and comparing methods that detect bed exit, standing and falls from a depth camera in front of a bed, and studying how camera position changes what a method sees. **Not for** clinical validation, and not as evidence that any method works on real patients.

## Licence

- **3D simulation data** (`data/R01` to `data/R62`, `metadata/`, `baseline/body_points/`, `baseline/results/`, the documentation): Creative Commons Attribution 4.0 International (`LICENSE`).
- **AI-generated part** (`data/generated/`, `metadata/generated_videos.csv`, `metadata/generated_start_pictures.csv`): its own licence (`LICENSE-GENERATED`). It allows any use with attribution, provided the files stay marked as AI-generated and are not used to train or improve image or video generation models. The services that made them have terms of their own.
- **Code** (`code/load_clip.py`, `baseline/evaluate.py`, `baseline/rules/`): Apache License 2.0 (`LICENSE-CODE`).
- **The Blender pipeline** (`code/render/`): GNU General Public License 3.0 or later (`code/render/LICENSE`). These scripts use Blender's Python API, and Blender's licence asks that such scripts, if published, be shared under a GPL-compliant licence.

## Citation

See `CITATION.cff`. Data: https://doi.org/10.5281/zenodo.23926720. Code and documentation: https://github.com/shahabafshar/bedside-depth-sim.

## References

Tools and models used to make or score the data:

- Blender 4.5 LTS. Blender Foundation. https://www.blender.org
- MPFB 2 (MakeHuman for Blender) and the MakeHuman system assets (CC0). MakeHuman Community. https://static.makehumancommunity.org
- Jiang T. et al. RTMPose: Real-Time Multi-Person Pose Estimation based on MMPose. arXiv:2303.07399, 2023.
- Ge Z. et al. YOLOX: Exceeding YOLO Series in 2021. arXiv:2107.08430, 2021.
- rtmlib 0.0.16. https://github.com/Tau-J/rtmlib
- Wan 2.2. Alibaba, Wan team. https://github.com/Wan-Video/Wan2.2
- Veo 3.1. Google. https://ai.google.dev/gemini-api/docs/veo
- Seedream 5.0 and Seedance 2.0. ByteDance. https://www.byteplus.com
- fal.ai, the service through which the generated files were made. https://fal.ai
- Luxonis OAK-D Pro W, whose published fields of view the virtual camera uses. https://docs.luxonis.com
- Gebru T. et al. Datasheets for Datasets. Communications of the ACM 64(12), 2021, pp. 86 to 92.

## Contact

TO BE CONFIRMED.
