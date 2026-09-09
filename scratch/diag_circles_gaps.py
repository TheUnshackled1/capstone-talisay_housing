"""Locate circular markers and check neighboring lot coverage."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
lots = json.loads((ROOT / "static/units/lot_plan_polygons.json").read_text())["lots"]

blur = cv2.medianBlur(gray, 5)
raw = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1.2, 18, param1=85, param2=22, minRadius=5, maxRadius=16)
circles = raw[0] if raw is not None else []
print(f"circles={len(circles)}")

cov = np.zeros((H, W), dtype=np.uint8)
for L in lots:
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.int32)
    cv2.fillConvexPoly(cov, pts, 255)

# For each circle, sample 4 diagonal offsets (lot centers near junction)
for i, (cx, cy, r) in enumerate(circles):
    cx, cy, r = float(cx), float(cy), float(r)
    print(f"\ncircle {i}: ({cx:.0f},{cy:.0f}) r={r:.1f}")
    for dx, dy, name in [
        (-12, -10, "NW"),
        (12, -10, "NE"),
        (-12, 10, "SW"),
        (12, 10, "SE"),
        (0, -18, "N"),
        (0, 18, "S"),
        (-18, 0, "W"),
        (18, 0, "E"),
    ]:
        x, y = int(cx + dx), int(cy + dy)
        if not (0 <= x < W and 0 <= y < H):
            continue
        print(f"  {name} ({x},{y}) gray={gray[y,x]:3d} cov={bool(cov[y,x])}")

# Watershed recovery on ink cells
ink = (gray < 105).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
sure_bg = cv2.dilate(ink, np.ones((3, 3), np.uint8), 2)
dist = cv2.distanceTransform(cv2.bitwise_not(ink), cv2.DIST_L2, 5)
# peaks = local maxima as lot seeds
_, sure_fg = cv2.threshold(dist, 0.35 * dist.max(), 255, 0)
sure_fg = np.uint8(sure_fg)
# better: peaks via dilation
kernel = np.ones((5, 5), np.uint8)
local_max = (dist == cv2.dilate(dist, kernel)) & (dist > 3.5)
markers = np.zeros((H, W), dtype=np.int32)
ys, xs = np.where(local_max)
# cluster nearby peaks
from scipy import ndimage  # may not exist

# manual peak list filtering
peaks = list(zip(xs.tolist(), ys.tolist(), dist[ys, xs].tolist()))
peaks.sort(key=lambda t: -t[2])
kept_peaks = []
for x, y, d in peaks:
    if any((x - kx) ** 2 + (y - ky) ** 2 < 64 for kx, ky, _ in kept_peaks):
        continue
    # skip if already covered
    if cov[y, x]:
        continue
    # skip road: very bright neighborhood AND elongated
    if gray[y, x] < 115:
        continue
    kept_peaks.append((x, y, d))

print(f"\nuncovered distance peaks: {len(kept_peaks)}")
for x, y, d in kept_peaks[:40]:
    print(f"  ({x},{y}) dist={d:.1f} gray={gray[y,x]}")

dbg = rgb.copy()
for L in lots:
    pts = np.array([[int(p[0] * W), int(p[1] * H)] for p in L["points"]], dtype=np.int32)
    cv2.polylines(dbg, [pts], True, (0, 200, 255), 1)
for x, y, d in kept_peaks:
    cv2.circle(dbg, (x, y), 3, (255, 0, 0), -1)
Image.fromarray(dbg).save(ROOT / "scratch/lot_map_peak_gaps.png")
print("wrote scratch/lot_map_peak_gaps.png")
