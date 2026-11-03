"""
Run the locked detection rules on the dataset and write what each one raises, clip by clip.

    python baseline/evaluate.py data                     all clips under data/
    python baseline/evaluate.py data --out results.csv   choose the output file

Rules (in rules/, unchanged since they were locked; checksums in rules/FROZEN_*.json):
  v3  posture from depth: sit-up, stand-up, and a fall as hips low on the floor
  v4  v3 with a fall rule for a fast drop that allows for depth seeing the body's surface
  v5  v4 plus a floor check on depth alone (needs the clip's empty-room depth, so clips R41 to R62 only)
The body points they read are in body_points/ (RTMPose-m with the YOLOX-m person finder, rtmlib 0.0.16, "balanced",
run on each clip's grey video at 15 frames per second). Needs numpy, Pillow and scipy.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "rules"))
import posture_rules_v3 as p3  # noqa: E402
import posture_rules_v4 as p4  # noqa: E402
import posture_rules_v5 as p5  # noqa: E402

CFG = {v: json.loads((HERE / "rules" / f"rules_{v}.json").read_text(encoding="utf-8")) for v in ("v3", "v4", "v5")}
BED = (-0.50, 0.50, 1.60, 3.75)  # bed footprint in room coordinates (m), when a clip's metadata does not give one


def alerts(out):
    raised = ({"fall"} if out["pred_fall"] else set()) | {k for k in ("sit_up", "stand_up") if out[f"pred_{k}"]}
    return " ".join(sorted(raised)) or "none"


def evaluate(clip_dir):
    d = Path(clip_dir)
    cid = d.name
    m = json.loads((d / f"{cid}_meta.json").read_text(encoding="utf-8"))
    mono = m["camera"]["mono"]
    k = mono["intrinsics_opencv"]
    K = (k["fx"], k["fy"], k["cx"], k["cy"])
    cam_to_world = np.linalg.inv(np.array(mono["world_to_camera_opencv_4x4"], float))
    pose = dict(np.load(HERE / "body_points" / f"{cid}_grey.npz"))
    frames = np.clip(np.round(pose["t"] * m["fps"]).astype(int), 0, m["frame_count"] - 1)
    depth = np.stack([np.array(Image.open(d / "depth" / f"{cid}_depth_{i:06d}.png")) for i in frames])
    args = (pose["t"], pose["kpts"], pose["scores"], pose["boxes"], pose["size"], depth, K, cam_to_world)
    o3, _ = p3.evaluate_clip(*args, CFG["v3"])
    o4, _ = p4.evaluate_clip(*args, CFG["v4"])
    row = {"clip": cid, "v3": alerts(o3), "v4": alerts(o4), "v4_fall": int(o4["pred_fall"]), "v5_fall": "",
           "v5_fall_path": "", "v5_alert_s": ""}
    background = d / f"{cid}_background_depth.png"
    if background.exists():
        o5, _, _, _ = p5.evaluate_clip(*args, np.array(Image.open(background)), tuple(m.get("bed_rect_m") or BED), CFG["v5"])
        alert_t = o5["pred_fall_t"]
        row.update(v5_fall=int(o5["pred_fall"]), v5_fall_path=o5["fall_path"],
                   v5_alert_s=round(float(alert_t), 3) if alert_t else "")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", help="folder holding the clip folders R01 to R62")
    ap.add_argument("--out", default=str(HERE / "results" / "reproduced.csv"))
    a = ap.parse_args()
    rows = [evaluate(d) for d in sorted(Path(a.data).glob("R[0-9][0-9]")) if d.is_dir()]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} clips evaluated; results in {a.out}")


if __name__ == "__main__":
    main()
