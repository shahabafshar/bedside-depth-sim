"""
Rules version 5: v4 plus a floor check that needs no pose model
===============================================================
Purpose: on renders, the person detector stopped finding patients once they lay on the floor
(research/synthetic_video/pilot/results/RENDERS_diagnosis.md), so v4 caught 2 of 10 fresh falls.
v5 adds a check on the depth picture alone: something new, low, person-sized and person-long on
the floor beside an empty bed, for long enough, is a patient on the floor. Everything else is v4's.
Date: 2026-10-19. Thresholds in rules_v5.json; reasons in rules_v5.md (plan step S4).

Extra inputs per clip:
  background  (H, W) uint16 mm: the room without the person, from the same camera (on the product:
              captured at installation and refreshed while the room is empty; in renders: the
              scene at frame 0 without the person)
  bed_rect    (x0, x1, y0, y1) in room metres: the bed's footprint, marked once at installation
"""

import numpy as np
import posture_rules_v4 as p4


def room_points(depth, K, cam_to_world, step):
    """Room coordinates (x, y, z) of every step-th pixel with valid depth, and those pixels' depths."""
    fx, fy, cx, cy = K
    v, u = np.mgrid[0:depth.shape[0]:step, 0:depth.shape[1]:step]
    z = depth[::step, ::step].astype(float) / 1000
    ok = z > 0
    pc = np.stack([(u[ok] - cx) * z[ok] / fx, (v[ok] - cy) * z[ok] / fy, z[ok], np.ones(ok.sum())])
    return (cam_to_world @ pc)[:3].T, ok


def footprint(xy, grid):
    """Floor area (m2) covered by points, as occupied cells of a grid."""
    if len(xy) == 0:
        return 0.0
    return len(np.unique(np.floor(xy / grid).astype(int), axis=0)) * grid * grid


def largest_person_sized(xy, grid, min_extent):
    """Area (m2) of the largest separate low object at least min_extent long (bounding-box diagonal):
    a person lying or sitting on the floor is long; a bag is not."""
    from scipy import ndimage
    if len(xy) == 0:
        return 0.0
    cells = np.unique(np.floor(xy / grid).astype(int), axis=0)
    lo = cells.min(axis=0)
    occ = np.zeros(tuple(cells.max(axis=0) - lo + 1), bool)
    occ[tuple((cells - lo).T)] = True
    lab, n = ndimage.label(occ, structure=np.ones((3, 3)))
    best = 0.0
    for k in range(1, n + 1):
        ij = np.argwhere(lab == k)
        extent = np.hypot(*((ij.max(axis=0) - ij.min(axis=0) + 1) * grid))
        if extent >= min_extent:
            best = max(best, len(ij) * grid * grid)
    return best


def floor_check(t, depth, background, K, cam_to_world, bed_rect, cfg):
    """Per frame: floor area of the largest new, low, person-length object in the zone around the bed, and whether the bed is occupied.
    Alert when the area reaches floor_area_min_m2 with the bed empty for floor_check_hold_s
    (share floor_check_fraction of the frames)."""
    step, grid = cfg["depth_step_px"], cfg["grid_m"]
    x0, x1, y0, y1 = bed_rect
    m = cfg["bed_margin_m"]
    zone = cfg["floor_zone_m"]
    bg_pts, bg_ok = room_points(background, K, cam_to_world, step)
    bed_pts = bg_pts[(bg_pts[:, 0] > x0) & (bg_pts[:, 0] < x1) & (bg_pts[:, 1] > y0) & (bg_pts[:, 1] < y1)]
    top = np.percentile(bed_pts[:, 2], 90) if len(bed_pts) else cfg["mattress_top_default_m"]  # mattress top of the empty bed
    bg = background[::step, ::step].astype(float) / 1000
    area, occ = np.zeros(len(t)), np.zeros(len(t))
    for i in range(len(t)):
        pts, ok = room_points(depth[i], K, cam_to_world, step)
        d = depth[i][::step, ::step].astype(float)[ok] / 1000
        b = bg[ok]
        new = (b <= 0) | (d < b - cfg["fg_min_m"])  # closer to the camera than the empty room
        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
        in_bed = (x > x0 - m) & (x < x1 + m) & (y > y0 - m) & (y < y1 + m)
        near = (x > x0 - zone) & (x < x1 + zone) & (y > y0 - zone) & (y < y1 + zone)
        low = (z >= cfg["floor_obj_min_h_m"]) & (z <= cfg["floor_obj_max_h_m"])
        area[i] = largest_person_sized(np.c_[x, y][new & low & near & ~in_bed], grid, cfg["floor_obj_min_extent_m"])
        on_bed = new & (x > x0) & (x < x1) & (y > y0) & (y < y1) & (z >= top + cfg["bed_body_min_above_m"])
        occ[i] = footprint(np.c_[x, y][on_bed], grid)
    fps = 1.0 / np.median(np.diff(t)) if len(t) > 1 else 15.0
    w = max(1, int(round(cfg["floor_check_hold_s"] * fps)))
    hit = (area >= cfg["floor_area_min_m2"]) & (occ < cfg["bed_occupied_min_m2"])
    for i in range(0, len(t) - w + 1):
        if hit[i:i + w].mean() >= cfg["floor_check_fraction"]:
            return True, float(t[min(i + w - 1, len(t) - 1)]), area, occ, float(top)
    return False, None, area, occ, float(top)


def evaluate_clip(t, kpts, scores, boxes, size, depth, K, cam_to_world, background, bed_rect, cfg):
    """v4's outputs, with a fall also raised by the floor check. fall_path says which: 'drop' (v4's rule) or 'floor'."""
    out, f = p4.evaluate_clip(t, kpts, scores, boxes, size, depth, K, cam_to_world, cfg)
    fl, fl_t, area, occ, top = floor_check(t, depth, background, K, np.asarray(cam_to_world, float), bed_rect, cfg)
    paths = (["drop"] if out["pred_fall"] else []) + (["floor"] if fl else [])
    times = [x for x in (out["pred_fall_t"], fl_t) if x is not None]
    out.update({"pred_fall": int(bool(paths)), "pred_fall_t": min(times) if times else None, "fall_path": "+".join(paths),
                "floor_alert_t": fl_t, "floor_area_max_m2": round(float(area.max()), 3) if len(area) else 0.0,
                "mattress_top_m": round(top, 3)})
    return out, f, area, occ
