# Known issues

What is wrong or simplified in this dataset, most important first. Read this before drawing conclusions from it.

## Faults that change results

**Fallen bodies propped on one hand (R07 to R09, R19 to R26, R31 to R36).**
- **What:** at the end of these falls only a wrist touches the floor, and the trunk is held 10 to 19 cm above it.
- **Cause:** the rig's rest pose bends the elbows about 43° forward, so an arm on the floor points into it, and the contact solver lifts the body onto that hand.
- **Effect:** from the camera the body looks as if it lies on the floor, but its depth and hip height are too high. This matters for any rule that uses height above the floor.
- **Second effect:** in R07 to R09 and R19 to R22 the hip centre never goes below 0.30 m (it stays at 0.33 m). The E6 end rule ("hip centre below 0.30 m") is never met, so their end times (5.33 s) come from the stillness test alone.
- **Not affected:** the falls of R41 to R50 were checked to lie flat. The pelvis is within 1 cm of the floor, or on it when sitting, and no ending is propped on a hand.

**A lens that makes people small.**
- **What:** both cameras are pinholes with square pixels, set to the published horizontal fields of view (95° colour, 127° mono). The real lenses are strongly distorted.
- **Size effect:** if the real mono lens is close to an equidistant ("f-theta") lens, a person near the centre of the grey and depth images looks about 45% smaller here than through the real lens. The corners are stretched.
- **Field of view:** the vertical fields of view (78.6° and 102.8°) are wider than the published ones (72° and 79.5°).
- **Effect:** a pose model sees a smaller person than it would on the real camera. This may have made the baseline's person finder lose fallen patients more often.

**Ideal depth.**
- **What the depth leaves out:** no noise, no holes at edges or in shadows, no minimum range (the real camera's ideal range starts at about 0.7 m), no dot pattern, no stereo matching errors.
- **One viewpoint:** colour and mono images come from the same point. The real colour camera sits a few centimetres from the mono cameras.
- **Distance:** real depth gets worse with distance from the camera. Luxonis: "Depth accuracy decreases exponentially with the distance from the camera", and "Wider FOV will result in worse depth accuracy". Here a floor point 4.5 m away is as exact as one 1.4 m away.
- **Effect:** methods that work on this depth may fail on real depth. Results here are an upper bound.

**An exactly known camera pose.**
- **What:** the metadata gives each camera's position and tilt exactly, and the baseline uses them to turn depth into heights above the floor.
- **On a real camera:** they must be estimated, for example gravity from the camera's motion sensor and the floor from a plane fitted to the depth.
- **Size of the error:** measured on R45 (camera at 2.2 m), a tilt error of 1° moves the floor about 4 cm up or down 3.6 m from the camera, and 2° moves it about 9 cm. Near the camera the effect is small.
- **Effect:** rules that use height above the floor, such as v5's 0.10 to 0.40 m band, are sensitive to this, and this dataset does not test it.

**The grey image is not an infrared image.** It is the visible-light scene lit only by a spot light at the camera, with its brightness set once by eye. It does not model how skin and fabrics reflect at 940 nm, the dot pattern, sensor noise or auto exposure.

## Simplifications

**Motion.**
- **Keyed by hand, not captured.** It is smooth but too regular: no breathing, weight shifts or hesitation, and every joint eases in and out at the same keys.
- **Walking:** short-stepped and stiff, and turning on the spot rotates the feet in place.
- **Falls:** keyframed apart from the vertical drop. Impacts are a few degrees of rebound, then the body is perfectly still.
- **Particular falls:**
  - The roll-out of E6 slides off the edge almost flat before dropping.
  - F2's trip has no visible foot catch.
  - F5's collapse goes through a kneel before tipping over.

**Contact.**
- **Rigid surfaces:** mattress, pillow and floor do not deform. Bodies may press 1.5 cm into the mattress (4 cm at the pelvis) and up to 6 cm into the pillow, so they look slightly inside those surfaces.
- **Limbs:** not checked against each other.
- **High bed:** with the mattress top at 0.58 m, a seated patient's feet hang about 15 cm above the floor. In L14, body B's feet stay about 15 cm up while she bends, so each slipper rises from the floor to the foot.

**Objects.**
- **Blanket:** a procedural drape (L10), not a cloth simulation. At frame 0 it looks stiff and shrouds the body, and in the empty-room depth of L10 it keeps the patient's shape.
- **Clothes:** move rigidly with the body.
- **Bag and chair:** the bag is held without the fingers closing, and the chair slides without tilting.
- **Slippers:** they jump onto the feet over 0.6 s.

**One room, two bodies.**
- **Room:** one clean, evenly lit room with one bed layout; no clutter, window light, camera noise or motion blur. The colour image is a little washed out.
- **Bodies:** two, both older and pale-skinned: A, male, about 74 years, 1.71 m; B, female, about 79 years, 1.55 m, heavier build.
- **Second person:** the visitor (L11) and the nurse (L13) are body A, the same model and clothes as the patient of other clips.

**Camera positions.**
- **Foot wall:** most clips use the centred foot-wall camera at 2.2 or 1.8 m.
- **Comparison views:** the off-centre, side and corner views appear only in the design set, with one motion each of E1, E4 and E6.
- **Corner view (R14, R18, R22):** the camera is 10 cm from two walls. Both walls are in the mono view, overexposed in the grey video, and down to 68 mm in depth. That is closer than a real camera can measure.

**Moved table in F3 (R45, R46).** In F3 only, the bedside table was moved 0.40 m from the bed and the non-exit rails lowered, so a body fits between them. The metadata records this.

## Labels

**Event times.** They come from the rendered body by fixed rules, written into each clip's metadata, so they are exact for those rules. Two starts are scripted rather than measured:
- E6 starts at the keyframe where the body begins to move over the edge;
- F3 starts at the keyframe where the fast roll begins.

**Floor-check set.** R41 to R62 were labelled for the fall alert only. Sit-up and stand-up alerts were not judged there, and some of those clips do contain a sit-up or stand-up (L12, L15). See `alerts_judged` in `metadata/clips.csv`.

**Visibility flags.** `hidden_by_body` is approximate: it fires when the camera ray meets the body more than 15 cm before the point. Ankles seen end-on from the foot of the bed can be flagged while the foot is visible.

**L13 at 2.2 m.** In the last frames of R53 and R57, the second person is at the very edge of the wide mono image.

## The AI-generated part

**Labels not checked.** Each video's scenario is what its prompt asked for. Blind labelling of whether each video shows that event has not been done. Some videos show something else, or nothing happening.

**The camera moves in some videos.** The camera zooms or shifts by more than 1.5% in:
- 13 of the 16 Veo videos, even though they were asked twice not to;
- 4 of the 8 first-batch Wan videos.

No second-batch Wan video and no Seedance video moved. A wall camera never moves, so treat moved videos with care (`camera_moved`).

**No depth, no ground truth.** These are colour videos only. Event times, body positions and depth are not available.

**Generated people and rooms.** The models invent the people, the rooms and the motion. The videos have not been checked for the faults such models are known for, such as bodies that change between frames, malformed hands or implausible motion. The camera's view was asked for in the prompt, not modelled on the OAK-D's lens.

**One picture, several videos.** Each start picture is used by 2 to 8 videos from different models and seeds. Count a start picture's scenario, not a video, as one test case.

**Faces.** The start pictures were made from text alone, but a generated face could still look like a real person by chance.

## Baseline

**The v5 bed check never acted.**
- **The fault:** rules v5 estimate the mattress top as the 90th percentile height of the empty room's points over the bed. The camera also sees the ceiling above the bed, so the estimate reads about 3 m. The guard that should silence the floor check while the patient is in bed never acts.
- **Why the tests missed it:** the rules' own test scenes had no ceiling.
- **What it affects:** the two nurse clips (R57, R58) were decided by floor area alone, just either side of the rule's 0.10 m² limit.
- **What we did:** the result is reported as locked.

**The baseline body points are model output.**
- **What:** they come from a general pose model run on the grey video (`baseline/body_points/`). They are not ground truth.
- **Where they fail:** on the floor the person finder often lost the patient.

**Not independent.** Several clips show one motion from several cameras, and every motion is played by one or two bodies. Count a motion, not a clip, as one test case.
