import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
H, W = gray.shape
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]
pts = np.array([[L["cx"] * W, L["cy"] * H] for L in lots])
tree = cKDTree(pts)
cov = np.zeros((H, W), np.uint8)
for L in lots:
    p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], np.int32)
    cv2.fillConvexPoly(cov, p, 255)
ink = (gray < 108).astype(np.uint8)
region = [
    (x, y)
    for y in range(200, 320, 2)
    for x in range(600, 720, 2)
    if gray[y, x] > 170 and not cov[y, x] and not ink[y, x]
]
kept = []
for x, y in region:
    if any((x - kx) ** 2 + (y - ky) ** 2 < 100 for kx, ky in ((k[0], k[1]) for k in kept)):
        continue
    hits = 0
    for ang in (0, 90, 180, 270):
        rad = np.deg2rad(ang)
        for t in np.linspace(5, 16, 8):
            xx = int(x + t * np.cos(rad))
            yy = int(y + t * np.sin(rad))
            if 0 <= xx < W and 0 <= yy < H and ink[yy, xx]:
                hits += 1
                break
    if hits >= 3:
        d, _ = tree.query([x, y])
        kept.append((x, y, float(d), hits, int(gray[y, x])))
print("candidate holes", len(kept))
for row in kept:
    print(" ", row)

# Also find left/right neighbors of gray cluster lots around 640,240
print("\nlots near (640,240):")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if abs(cx - 640) < 50 and abs(cy - 240) < 40:
        print(f"  #{i} ({cx:.0f},{cy:.0f})")
