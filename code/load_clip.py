"""
Load one clip: its metadata, depth in metres, ground truth, and each depth pixel's position in the room.

    python code/load_clip.py data/R45

Needs numpy and Pillow. Room coordinates are in metres with z up and the floor at z = 0.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def load(clip_dir):
    """Metadata, ground truth, and the depth video as a (frames, height, width) array in metres (0 = no data)."""
    d = Path(clip_dir)
    cid = d.name
    meta = json.loads((d / f"{cid}_meta.json").read_text(encoding="utf-8"))
    truth = json.loads((d / f"{cid}_ground_truth.json").read_text(encoding="utf-8"))
    files = sorted((d / "depth").glob(f"{cid}_depth_*.png"))
    depth_m = np.stack([np.asarray(Image.open(p), dtype=np.float64) for p in files]) / 1000.0
    return meta, truth, depth_m


def room_points(depth_m, meta):
    """Room coordinates (x, y, z) of every pixel of one depth frame. Depth is planar: the distance along the mono
    camera's optical axis, in the OpenCV camera frame (x right, y down, z forward)."""
    mono = meta["camera"]["mono"]
    k = mono["intrinsics_opencv"]
    cam_to_world = np.linalg.inv(np.array(mono["world_to_camera_opencv_4x4"], float))
    v, u = np.mgrid[0:depth_m.shape[0], 0:depth_m.shape[1]]
    z = depth_m
    pts = np.stack([(u - k["cx"]) * z / k["fx"], (v - k["cy"]) * z / k["fy"], z, np.ones_like(z)], axis=-1)
    return (pts @ cam_to_world.T)[..., :3]


def main():
    meta, truth, depth = load(sys.argv[1])
    xyz = room_points(depth[0], meta)
    low = xyz[..., 2][depth[0] > 0]
    print(f"{meta['clip_id']}: scenario {meta['scenario_id']}, {meta['frame_count']} frames at {meta['fps']} fps, "
          f"camera {meta['camera']['label']}")
    for e in meta.get("events") or []:
        print(f"  event {e['scenario']}: {e['start_s']:.2f} to {e['end_s']:.2f} s")
    print(f"  depth {depth.shape[1]} x {depth.shape[2]}, {depth[0][depth[0] > 0].min():.2f} to {depth[0].max():.2f} m; "
          f"lowest surface in frame 0 at z = {np.percentile(low, 1):.3f} m (the floor)")
    hip = [f["hip_height_m"] for f in truth["frames"]]
    print(f"  true hip height: {hip[0]:.2f} m in the first frame, {min(hip):.2f} m at its lowest")


if __name__ == "__main__":
    main()
