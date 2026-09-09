"""Diagnose why specific cells miss traces; try line-based cell recovery."""
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

cov = np.zeros((H, W), dtype=np.uint8)
centers = []
for L in lots:
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.int32)
    cv2.fillConvexPoly(cov, pts, 255)
    centers.append((L["cx"] * W, L["cy"] * H))
centers = np.array(centers)

# Strong ink lines
ink = (gray < 110).astype(np.uint8) * 255
ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8), 1)

# Invert: cells between lines
cells = cv2.bitwise_not(ink)
cells = cv2.morphologyEx(cells, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)
n, labels, stats, cents = cv2.connectedComponentsWithStats(cells, connectivity=4)

missed = []
for i in range(1, n):
    x, y, w, h, area = stats[i]
    if not (80 <= area <= 2800):
        continue
    if not (8 <= w <= 90 and 8 <= h <= 90):
        continue
    if max(w, h) / max(min(w, h), 1) > 3.5:
        continue
    # skip roads: mean gray too high AND aspect very wide/tall empty
    cx, cy = float(cents[i][0]), float(cents[i][1])
    if not (6 <= cx < W - 6 and 6 <= cy < H - 6):
        continue
    # already covered if a lot center is inside this component
    if any(labels[int(round(yy)), int(round(xx))] == i for xx, yy in centers):
        continue
    # or substantial overlap with cov
    sub_cov = cov[y : y + h, x : x + w]
    sub_lab = labels[y : y + h, x : x + w] == i
    sub_gray = gray[y : y + h, x : x + w]
    if not sub_lab.any():
        continue
    if float(sub_cov[sub_lab].mean()) > 40:
        continue
    gmean = float(sub_gray[sub_lab].mean())
    if gmean < 100:  # too dark = ink blob
        continue
    # reject very bright road corridors that are thin
    if gmean > 210 and min(w, h) < 12:
        continue
    missed.append((area, x, y, w, h, int(cx), int(cy), gmean))

missed.sort(reverse=True)
print(f"line-cell missed candidates: {len(missed)}")
for row in missed[:60]:
    print(f"  area={row[0]:4d} box=({row[1]},{row[2]},{row[3]}x{row[4]}) c=({row[5]},{row[6]}) mean={row[7]:.0f}")

dbg = rgb.copy()
for L in lots:
    pts = np.array([[int(p[0] * W), int(p[1] * H)] for p in L["points"]], dtype=np.int32)
    cv2.polylines(dbg, [pts], True, (0, 200, 255), 1)
for a, x, y, w, h, cx, cy, gm in missed:
    cv2.rectangle(dbg, (x, y), (x + w, y + h), (255, 0, 0), 1)
    cv2.circle(dbg, (cx, cy), 2, (255, 0, 0), -1)
out = ROOT / "scratch/lot_map_missed_cells.png"
Image.fromarray(dbg).save(out)
print(f"wrote {out}")

# Sample gray-shaded cluster region (right of center road) ~ looking at image
# Rough region of right block mid: x 480-700, y 180-320
print("\nSample gray cluster region coverage:")
for y in range(200, 320, 20):
    for x in range(500, 700, 25):
        covered = cov[y, x] > 0
        print(f"  ({x},{y}) gray={gray[y,x]} cov={covered}")
