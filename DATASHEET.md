# Datasheet: Bedside Depth Simulations v1.0

Answers to the questions of "Datasheets for Datasets" (Gebru et al., Communications of the ACM 64(12), 2021), for this dataset.

## Motivation

**For what purpose was the dataset created?**
- **Purpose:** to test rules that detect a hospital patient sitting up, leaving the bed or falling, seen by one depth camera (a Luxonis OAK-D Pro W) on the wall in front of the bed.
- **The gap:** of the 53 public datasets we checked, none shows real patients leaving hospital beds from this camera position.
- **Why simulation:** it gives exact event times, exact 3D body positions and exact depth, which recorded video cannot give.

**Who created it, and on whose behalf?** TO BE CONFIRMED.

**Who funded its creation?** TO BE CONFIRMED.

## Composition

**What do the instances represent?** Each instance is a short rendered clip of a hospital room with a bed: a patient (and in four clips a second person) performs one scripted movement, seen by a virtual camera.

**How many instances are there?** 62 clips (R01 to R62): 7,217 frames at 15 frames per second, 5.1 to 13.5 s per clip.
- 41 show an event: sitting up, leaving the bed, or one of eight kinds of fall.
- 21 show a look-alike movement that should raise no fall alert.
- 22 clips (R41 to R62) also have a depth image of the empty room.

A second, separate part holds AI-generated hospital videos from the same camera position:
- **Videos:** 52, made by Wan 2.2 (32), Veo 3.1 Fast (16) and Seedance 2.0 (4).
- **Start pictures:** the 12 generated pictures (Seedream 5.0 Pro) the videos begin from.
- **What they asked for:** 42 videos ask for an event (sitting up, legs over the edge, standing up, three kinds of fall) and 10 for a look-alike, 2 of them a nurse helping the patient.
- **Missing:** they have no depth, no ground truth, and labels that have not been checked against the videos.

**Is it a sample of a larger set?**
- **The camera positions:** a small, chosen set (seven positions, mostly the centred foot wall at 1.8 and 2.2 m).
- **The movements:** a scripted selection.
- **Not representative of:** real patients, rooms, cameras or the frequency of events in hospitals.

**What data does each instance consist of?**
- **Videos:** a colour video (640 x 480) and a grey, infrared-like video (640 x 400).
- **Depth:** a 16-bit depth image per frame (millimetres, planar, ideal).
- **Ground truth per frame:** 24 body points in 3D and in each camera's pixels, with visibility flags; hip height, trunk angle, and contact with mattress or chair.
- **Metadata:** event start and end times with the rules that set them; camera calibration; the solved motion; a contact sheet and key frames.
- **Format guide:** `docs/FORMATS.md`.

**Is there a label or target?** Yes:
- **Event labels:** the expected alerts per clip (`metadata/clips.csv`) and the event times (`<clip>_meta.json`).
- **Floor-check set:** R41 to R62 were labelled for the fall alert only.

**Is any information missing?**
- **Empty-room depth:** only for R41 to R62.
- **Second person:** only in R53, R54, R57 and R58.
- **Scene files:** the Blender scene files are not included (they hold local file paths); `code/render/` rebuilds them.

**Are relationships between instances explicit?**
- **Shared motions:** clips of the same scenario and body share one motion (same `motion_sha256`), seen from different cameras.
- **`metadata/clips.csv`** gives scenario, body and camera for each clip.

**Are there recommended splits?** The three sets were made at different times, each after a version of the baseline rules was locked (see the README):
- use the design set (R01 to R22) for development;
- use the fresh (R23 to R40) and floor-check (R41 to R62) sets for testing.
- Treat clips of one motion as one case, not several.

**Are there errors, sources of noise or redundancies?** Yes. `docs/KNOWN_ISSUES.md` lists them. The most important:
- some fallen bodies rest on one hand, 10 to 19 cm above the floor (R07 to R09, R19 to R26, R31 to R36);
- the pinhole lens makes people about 45% smaller than the real lens would;
- the depth is ideal.

**Is the dataset self-contained?** Yes. The baseline body points were made with public models (RTMPose-m and YOLOX-m through rtmlib 0.0.16) and are included.

**Does it contain confidential data, or data that might be offensive?**
- **No real people:** all people are computer models built from CC0 assets.
- **No patient data, no recordings of real people.**

**Does it identify subpopulations?** The two bodies are described by their MakeHuman settings:
- A: male, about 74 years;
- B: female, about 79 years, heavier build.

Both are pale-skinned. The dataset does not represent other ages, sizes or skin tones, and should not be used to judge how a method performs across them.

**Can individuals be identified?** No.

## Collection process

**How was the data acquired?**
- **Software:** rendered in Blender 4.5.14 LTS (Eevee) from Python scripts.
- **Room and objects:** built from Blender primitives.
- **People:** made with MPFB 2.0.18 and the MakeHuman system asset pack (CC0); body B's dress comes from the CC0 "Dress 01" pack.
- **Motion:** keyed by hand in Python as joint angles. A solver keeps the body on the mattress, chair or floor without passing through them. No motion capture was used.

**The AI-generated part.**
1. **Start pictures:** generated on 19 October 2026 through the fal.ai service, by Seedream 5.0 Pro from text prompts alone. Four candidates were drawn per prompt, and the first that met a fixed checklist (view from high on the foot wall, whole bed in view) was kept.
2. **Videos:** Wan 2.2 A14B, Veo 3.1 Fast and Seedance 2.0 animated the pictures, each prompted with one scenario, two attempts per model and picture.
3. **Recorded per request:** model, prompt, settings, seed, time and the returned file's checksum.
4. **Not released:** failed and refused requests.
5. **Camera check:** each video's camera stillness was measured afterwards against a threshold set beforehand (1.5% zoom or shift).

**How were the labels made?** Event times were measured on the rendered body by fixed rules, written into each clip's metadata. Two exceptions are scripted keyframes: the starts of E6 and F3. Body points, visibility and contact come from the 3D scene itself.

**How was it checked?**
- **Per clip:** a script checked every clip's outputs:
  - frame counts and image sizes;
  - depth against ray casts through 40 pixels (median error 1.5 to 3 mm);
  - projection of the body points (0.0 px disagreement);
  - motion checksums.
- **Collisions:** a test confirmed no person passes through the bed, rails, table, chair, walls or floor in R41 to R62.
- **Fall endings:** a contact report confirmed the fall endings of R41 to R50 lie flat.

**Over what timeframe?**
- R01 to R22 were rendered on 19 October 2026.
- R23 to R40 were rendered on 19 October 2026, after rules v4 were locked (21:23 UTC).
- R41 to R62 were rendered on 20 October 2026, 01:59 to 04:18 UTC, after rules v5 were locked (01:19 UTC).

**Ethical review?** Not applicable: no human participants or personal data.

## Preprocessing, cleaning, labelling

**Was any preprocessing done?**
- The key frame images were re-saved without their embedded text blocks (Blender's render stamp, which held a local file path); their pixels are unchanged.
- Nothing else was changed after rendering.

**Is the raw data available?** The released files are the rendered outputs. The scene files and motions can be rebuilt with `code/render/`.

## Uses

**What has the dataset been used for?** To test three locked versions of simple detection rules (`baseline/`):
- posture from depth (v3);
- a fast drop to the floor (v4);
- a floor check on depth alone (v5).

`baseline/RESULTS.md` lists the results.

**What else could it be used for?**
- comparing detectors of bed exit, standing and falls from a depth camera in front of the bed;
- studying how camera height and position change what a method sees;
- checking depth-based floor and bed geometry methods;
- testing pose models on older bodies lying, sitting and falling near a bed.

**What should it not be used for?**
- clinical validation;
- claims about how a method performs on real patients or real depth cameras;
- training a model meant for deployment without real data.

The clips are few, from one room and two bodies, with ideal depth.

## Distribution

**How is it distributed?**
- **Data:** two Zenodo archives, the 3D simulations and the AI-generated part (https://doi.org/10.5281/zenodo.23926720).
- **Code and documentation:** https://github.com/shahabafshar/bedside-depth-sim.

**Licence:**
- **3D simulation data:** Creative Commons Attribution 4.0 International.
- **AI-generated part:** its own licence (`LICENSE-GENERATED`). Any use with attribution, provided the files stay marked as AI-generated and are not used to train or improve image or video generation models. The services and models that made them have their own terms; none of them claims ownership of the outputs.
- **Code:** Apache License 2.0, except the Blender scripts in `code/render/`, which are under the GNU GPL 3.0 or later because they use Blender's Python API.
- **Assets used:** the MakeHuman assets are CC0. The renders were made with Blender, whose licence page states: "What you create with Blender is your sole property."

**Export controls or other restrictions?** None known.

## Maintenance

**Who maintains it, and how can they be contacted?** TO BE CONFIRMED.

**Will it be updated?**
- **Errors:** corrections will be published as new versions on Zenodo, each with its own DOI, and listed in `CHANGELOG.md`.
- **Known faults:** fixing the lifted fallen bodies would mean re-rendering 17 clips. If done, they will be a new version, not a silent replacement.

**Can others contribute?** Issues and pull requests on the GitHub repository are welcome.
