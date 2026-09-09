"""Refine gap seeds with enclosure checks; preview on map."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
lots = json.loads((ROOT / "static/units/lot_plan_polygons.json").read_text())["lots"]
pts = np.array([[L["cx"] * W, L["cy"] * H] for L in lots], dtype=np.float64)
sides = np.sqrt(np.array([L["area"] * W * H for L in lots]))
med_side = float(np.median(sides))

tree = cKDTree(pts)
dists, idxs = tree.query(pts, k=min(9, len(pts)))
local_sp = np.median(dists[:, 1:5], axis=1)

ink = (gray < 105).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
dist_ink = cv2.distanceTransform(cv2.bitwise_not(ink), cv2.DIST_L2, 5)

cov = np.zeros((H, W), dtype=np.uint8)
for L in lots:
    p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], dtype=np.int32)
    cv2.fillConvexPoly(cov, p, 255)


def enclosed(mx: float, my: float, sp: float) -> bool:
    """True if ink walls surround this point like a lot cell."""
    x, y = int(round(mx)), int(round(my))
    if not (8 <= x < W - 8 and 8 <= y < H - 8):
        return False
    if gray[y, x] < 130:
        return False
    if float(dist_ink[y, x]) < 3.0:
        return False
    if float(dist_ink[y, x]) > sp * 0.85:
        return False  # too open = road
    hits = 0
    for ang in (0, 45, 90, 135, 180, 225, 270, 315):
        rad = np.deg2rad(ang)
        found = False
        for t in np.linspace(sp * 0.28, sp * 0.75, 10):
            xx = int(round(mx + t * np.cos(rad)))
            yy = int(round(my + t * np.sin(rad)))
            if not (0 <= xx < W and 0 <= yy < H):
                break
            if ink[yy, xx]:
                found = True
                break
        if found:
            hits += 1
    return hits >= 5


seeds = []
pairs = tree.query_pairs(r=med_side * 3.2)
for i, j in pairs:
    dx = pts[j, 0] - pts[i, 0]
    dy = pts[j, 1] - pts[i, 1]
    dist = float(np.hypot(dx, dy))
    sp = 0.5 * (local_sp[i] + local_sp[j])
    if sp < med_side * 0.5:
        continue
    if not (1.75 * sp <= dist <= 2.3 * sp):
        continue
    # prefer axis-ish relative to i's nearest neighbor direction
    n1 = idxs[i, 1]
    ndx = pts[n1, 0] - pts[i, 0]
    ndy = pts[n1, 1] - pts[i, 1]
    nlen = float(np.hypot(ndx, ndy)) or 1.0
    # cos of angle between pair and neighbor / perpendicular
    cos_a = abs((dx * ndx + dy * ndy) / (dist * nlen))
    cos_perp = abs((-dx * ndy + dy * ndx) / (dist * nlen))  # wait use perp of neighbor
    # better: angle alignment with neighbor OR with neighbor's perpendicular
    cos_par = abs((dx * ndx + dy * ndy) / (dist * nlen))
    cos_orth = abs((-ndx * dy + ndy * dx) / (dist * nlen))  # pair · neighbor_perp
    if max(cos_par, cos_orth) < 0.82:
        continue

    mx = 0.5 * (pts[i, 0] + pts[j, 0])
    my = 0.5 * (pts[i, 1] + pts[j, 1])
    x, y = int(round(mx)), int(round(my))
    if not (6 <= x < W - 6 and 6 <= y < H - 6):
        continue
    if cov[y, x]:
        continue
    near_d, _ = tree.query([mx, my], k=1)
    if near_d < 0.72 * sp:
        continue
    if not enclosed(mx, my, sp):
        continue
    w = 0.5 * (sides[i] + sides[j]) * 0.9
    seeds.append((mx, my, w, dist, sp, i, j))

kept = []
for s in sorted(seeds, key=lambda t: -t[2]):
    if any((s[0] - k[0]) ** 2 + (s[1] - k[1]) ** 2 < (med_side * 0.65) ** 2 for k in kept):
        continue
    kept.append(s)

print(f"refined gap seeds={len(kept)}")
for mx, my, w, dist, sp, i, j in kept:
    print(f"  ({mx:.0f},{my:.0f}) w={w:.1f} d={dist:.1f} sp={sp:.1f} gray={gray[int(my),int(mx)]} distInk={dist_ink[int(my),int(mx)]:.1f}")

dbg = rgb.copy()
for L in lots:
    p = np.array([[int(pp[0] * W), int(pp[1] * H)] for pp in L["points"]], dtype=np.int32)
    cv2.polylines(dbg, [p], True, (0, 200, 255), 1)
for mx, my, w, dist, sp, i, j in kept:
    # oriented box along pair vector
    ang = np.arctan2(pts[j, 1] - pts[i, 1], pts[j, 0] - pts[i, 0])
    # use minArea-like rect: width along pair half-sp, height from neighbor size
    hw, hh = sp * 0.38, w * 0.42
    c, s = np.cos(ang), np.sin(ang)
    # corners of axis-aligned then... just draw circle + AABB for preview
    cv2.rectangle(
        dbg,
        (int(mx - hw), int(my - hh)),
        (int(mx + hw), int(my + hh)),
        (255, 0, 0),
        1,
    )
Image.fromarray(dbg).save(ROOT / "scratch/lot_map_gapfill_preview.png")
print("wrote scratch/lot_map_gapfill_preview.png")
