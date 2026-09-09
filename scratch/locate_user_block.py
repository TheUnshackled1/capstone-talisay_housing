"""Locate the block from user screenshots (large left lots + small right column)."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

# Thick-ink regions: lots with heavy black borders like the screenshot
ink = (gray < 70).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)

# Find connected thick-border clusters by looking at ink density in windows
# Also dump existing polygons that look like small stacked rectangles
data = json.loads(Path("static/units/lot_plan_polygons.json").read_text(encoding="utf-8"))

# Heuristic: find vertical stacks of small lots (narrow width, similar cx)
cands = []
for i, L in enumerate(data["lots"]):
    pts = np.array(L["points"]) * [W, H]
    xs, ys = pts[:, 0], pts[:, 1]
    bw, bh = xs.max() - xs.min(), ys.max() - ys.min()
    cx, cy = L["cx"] * W, L["cy"] * H
    if 8 < bw < 35 and 10 < bh < 40:
        cands.append((i, cx, cy, bw, bh, len(L["points"])))

cands.sort(key=lambda t: (round(t[1] / 15), t[2]))
print("small lots", len(cands))
# Group by approx cx
from collections import defaultdict
cols = defaultdict(list)
for c in cands:
    cols[int(c[1] // 20)].append(c)
for k, v in sorted(cols.items(), key=lambda kv: -len(kv[1])):
    if len(v) >= 4:
        print(f"col x~{k*20}: n={len(v)}")
        for t in v[:12]:
            print(" ", t)

# Save full map with small-lot overlays
vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for i, cx, cy, bw, bh, n in cands:
    L = data["lots"][i]
    pts = [(int(p[0] * W), int(p[1] * H)) for p in L["points"]]
    dr.polygon(pts, outline=(0, 220, 255, 255))
vis.save("scratch/small_lots_all.png")
print("wrote small_lots_all.png")

# Also look for mid-gray shaded pads outside the known upper-left cluster
shaded = ((gray >= 140) & (gray <= 180)).astype(np.uint8) * 255
shaded = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
nlab, labels, stats, cents = cv2.connectedComponentsWithStats(shaded, 8)
print("shaded blobs > 200px:")
for i in range(1, nlab):
    a = int(stats[i, cv2.CC_STAT_AREA])
    if a < 200:
        continue
    x, y, w, h = (int(stats[i, j]) for j in range(4))
    cx, cy = cents[i]
    # skip known upper-left
    if 90 < cx < 220 and 80 < cy < 160:
        continue
    print(f"  id={i} area={a} bbox=({x},{y},{w},{h}) c=({cx:.0f},{cy:.0f})")
