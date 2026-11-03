# Code

## `load_clip.py`: read a clip

```
python code/load_clip.py data/R45
```

It prints the clip's events, depth range, the height of the lowest surface (the floor, near z = 0) and the true hip height. As a library:

```python
from load_clip import load, room_points
meta, truth, depth_m = load("data/R45")      # depth_m: (frames, 400, 640) in metres, 0 = no data
xyz = room_points(depth_m[0], meta)          # (400, 640, 3) room coordinates in metres, z up
```

Needs numpy and Pillow. Licence: Apache-2.0 (`../LICENSE-CODE`).

## `render/`: the Blender pipeline that made the clips

Licence: GNU GPL 3.0 or later (`render/LICENSE`), because the scripts use Blender's Python API.

### What you need

| | Version used | Where |
|:--|:--|:--|
| Blender | 4.5.14 LTS (Windows x64 portable; SHA-256 `b9533d2397ac1984db4466fb23a7a4649391cca93f6e84209f9bcc60d071c8b9`, matching the published checksum) | download.blender.org |
| MPFB (MakeHuman for Blender) | 2.0.18, `add-on-mpfb-v2.0.18.zip` (SHA-256 `c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad`) | extensions.blender.org |
| MakeHuman system asset pack (CC0) | `makehuman_system_assets_cc0.zip` (SHA-256 `b542127a8e25547c7c29c19f2d1d2adb9a664c80396ecd694095dbc8028a0107`) | static.makehumancommunity.org, asset packs page |
| "Dress 01" asset pack (CC0), for body B | `dress01_cc0.zip` (SHA-256 `f49ba54a3c93acd3c3307cc5a96cfc65daf8abfed9212a7e580791d821c9e93a`) | the same site |

Blender's own Python, numpy and OpenImageIO are enough; nothing else is installed. Only Blender 4.5.14 was used.

Install MPFB without the interface:

```
blender --command extension install-file -r user_default -e add-on-mpfb-v2.0.18.zip
```

On Windows, MPFB has files 108 characters deep and Blender's Python cannot open paths over 260 characters. Set `BLENDER_USER_EXTENSIONS` to a short folder before installing and running, and keep the asset packs in short folders.

### Steps

Run these from `code/render/`. Clips are written to `data/` at the top of the repository. Each `.sh` runner takes `BLENDER=<path to blender>` and `MACHINE="<label>"` (recorded in each clip's metadata).

1. **Scene for R01 to R22:** `blender -b -P build_scene.py -- --assets <system asset pack folder>` writes `scene_base.blend` (room, bed, lights, both cameras, body A with its rig).
2. **Scene for R23 to R40:** `blender -b scene_base.blend -P build_scene_v2.py -- --assets <system asset pack folder> --dress <Dress 01 pack folder>` writes `scene_v2.blend` (adds body B and a chair).
3. **Scene for R41 to R62:** `blender -b scene_v2.blend -P build_scene_v3.py` writes `scene_v3.blend` (adds a blanket, a bag, slippers and a movable chair).
4. **Render:** `./run_all.sh` (R01 to R22), `./run_batch2.sh` (R23 to R40) and `./run_batch3.sh` (R41 to R62). Each renders its clips and then runs `verify_outputs.py`, which checks every clip and writes `SHA256SUMS.txt`.

One clip at a time:

```
blender -b scene_base.blend -P render_clips.py -- --scenario E1 --clips R01
blender -b scene_v3.blend -P render_clips_v3.py -- --motion F1 --people A --clips R41
```

### Files

| File | What |
|:--|:--|
| `config.py` | room, bed and camera settings, the clip list |
| `scene_room.py` | the room, bed, table and lights |
| `build_scene.py`, `build_scene_v2.py`, `build_scene_v3.py` | build the three scene files |
| `motions.py`, `motions3.py` | the motions as key poses (joint angles), with scripted times |
| `animate.py` | eases between key poses and solves each frame so the body rests on the mattress, chair or floor without passing through them |
| `objects3.py` | the blanket drape, the bag, slippers and chair |
| `events.py` | the rules that measure event start and end times on the rendered body |
| `render_clips.py`, `render_clips_v3.py` | render colour, grey and depth, and write the ground truth and metadata |
| `verify_outputs.py` | checks every clip's outputs and writes checksums |
| `tests/` | a smoke test, collision checks, previews |

### What to expect

- **Motions:** they are deterministic. Each clip's `motion_sha256` should come out the same.
- **Pixels:** expect them to differ slightly between machines and graphics drivers.
- **Speed:** on the machine used (Xeon E3-1240 v6, Quadro K620 2 GB), a clip of R41 to R62 took 2 to 6.5 minutes. Each clip's metadata records its render times.
- **Linux and Cycles:** Eevee needs an OpenGL context. `render_clips.py` accepts `--engine CYCLES` for machines without one, but Cycles was not used for these clips, and `render_clips_v3.py` uses Eevee only.
