"""Check every rendered clip and write SHA256SUMS.txt for the outputs.

    blender -b -P verify_outputs.py [-- --out-root DIR]

Checks per clip: files present; MP4 frame count, size and frame rate (read
back with Blender's movie reader); number, size and type of the depth PNGs;
event times present; and that clips of the same scenario share one motion
(same checksum). Prints a summary table (Markdown) and exits with an error
if a check fails.
"""
import argparse
import glob
import hashlib
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as C  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out-root", default=os.path.normpath(os.path.join(HERE, "..", "..", "data")))
a = ap.parse_args(argv)


def movie_info(path):
    clip = bpy.data.movieclips.load(path)
    info = (clip.frame_duration, tuple(clip.size), clip.fps)
    bpy.data.movieclips.remove(clip)
    return info


def png_info(path):
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(path)
    sp = inp.spec()
    info = (sp.width, sp.height, sp.nchannels, str(sp.format))
    inp.close()
    return info


problems, rows, hashes = [], [], {}
for clip in sorted(C.CLIPS):
    d = os.path.join(a.out_root, clip)
    mp = os.path.join(d, f"{clip}_meta.json")
    if not os.path.isfile(mp):
        b_, m_, c_ = C.clip_spec(clip)
        rows.append(f"| {clip} | {b_} {m_} | {c_} | not rendered | | | |")
        continue
    m = json.load(open(mp, encoding="utf-8"))
    n = m["frame_count"]
    for key in ("colour_mp4", "grey_mp4", "ground_truth", "motion", "contact_sheet"):
        if not os.path.isfile(os.path.join(d, m["files"][key])):
            problems.append(f"{clip}: missing {m['files'][key]}")
    for key, res in (("colour_mp4", C.COLOUR_RES), ("grey_mp4", C.MONO_RES)):
        frames, size, fps = movie_info(os.path.join(d, m["files"][key]))
        if frames != n or size != tuple(res) or abs(fps - C.FPS) > 1e-6:
            problems.append(f"{clip}: {key} has {frames} frames, size {size}, {fps} fps (expected {n}, {res}, {C.FPS})")
    depth = sorted(glob.glob(os.path.join(d, "depth", f"{clip}_depth_*.png")))
    if len(depth) != n:
        problems.append(f"{clip}: {len(depth)} depth PNGs for {n} frames")
    for p in (depth[0], depth[-1]):
        w, h, ch, fmt = png_info(p)
        if (w, h) != tuple(C.MONO_RES) or ch != 1 or fmt != "uint16":
            problems.append(f"{clip}: depth PNG {os.path.basename(p)} is {w}x{h}, {ch} channels, {fmt}")
    gt = json.load(open(os.path.join(d, m["files"]["ground_truth"]), encoding="utf-8"))
    if len(gt["frames"]) != n:
        problems.append(f"{clip}: ground truth has {len(gt['frames'])} frames for {n}")
    motion_key = (m.get("people") or m.get("body", "A")) + " " + m.get("motion_id", m["scenario_id"])
    if "background_depth_png" in m["files"]:       # third batch: depth of the scene without any person
        bgp = os.path.join(d, m["files"]["background_depth_png"])
        if not os.path.isfile(bgp):
            problems.append(f"{clip}: missing background depth")
        else:
            w, h, ch, fmt = png_info(bgp)
            if (w, h) != tuple(C.MONO_RES) or ch != 1 or fmt != "uint16":
                problems.append(f"{clip}: background depth is {w}x{h}, {ch} channels, {fmt}")
        if m.get("bed_rect_m") != C.BED_RECT_M:
            problems.append(f"{clip}: bed_rect_m missing or different")
    hashes.setdefault(motion_key, set()).add(m["motion_sha256"])
    if not m["events"] and not m["phases"]:
        problems.append(f"{clip}: no event or movement times")
    ev = "; ".join(f"{e['scenario']} {e['start_s']:.2f} to {e['end_s']:.2f} s" for e in m["events"]) or \
        "; ".join((f"{k.replace('_', ' ')} {p['start_s']:.2f} to {p['end_s']:.2f} s" if p.get("end_s") is not None
                   else f"{k.replace('_', ' ')} {p['start_s']:.2f} s") if p.get("start_s") is not None
                  else f"{k.replace('_', ' ')}: none" for k, p in m["phases"].items())
    r = m["render"]
    rows.append(f"| {clip} | {motion_key} | {m['camera']['label']} | {n} ({m['duration_s']:.2f} s) | {ev} | "
                f"{m['depth']['check_against_ray_casts']['median_abs_error_mm']} | "
                f"{r['seconds_total_clip']:.0f} |")
for s, hs in hashes.items():
    if len(hs) != 1:
        problems.append(f"body and motion {s}: clips have {len(hs)} different motions")

print("| Clip | Body, motion | Camera | Frames | Events (start to end) | Depth check, median error (mm) | Render time (s) |")
print("|---|---|---|---|---|---|---|")
print("\n".join(rows))
print("\nMOTION CHECKSUMS", {s: sorted(h)[0][:16] for s, h in hashes.items() if len(h) == 1})

# checksums of every output file
lines = []
for root, _, files in os.walk(a.out_root):
    for fn in sorted(files):
        if fn == "SHA256SUMS.txt":
            continue
        p = os.path.join(root, fn)
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {os.path.relpath(p, a.out_root).replace(os.sep, '/')}")
lines.sort(key=lambda s: s.split("  ", 1)[1])
with open(os.path.join(a.out_root, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(lines) + "\n")
print(f"SHA256SUMS.txt: {len(lines)} files")
if problems:
    print("PROBLEMS:\n" + "\n".join(problems))
    sys.exit(1)
print("ALL CHECKS PASSED")
