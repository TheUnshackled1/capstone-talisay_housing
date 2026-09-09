"""Find black-line corner junctions near each shaded cell for hand quads."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

ink = (gray < 70).astype(np.uint8) * 255
# skeleton-ish: erode then keep
skel = ink.copy()
# corners = high response of Harris on ink
ink_f = np.float32(ink)
harris = cv2.cornerHarris(ink_f, 3, 3, 0.04)
harris = cv2.dilate(harris, None)
ys, xs = np.where(harris > 0.02 * harris.max())
pts = list(zip(xs.tolist(), ys.tolist()))
# keep only in shaded ROI
pts = [(x, y) for x, y in pts if 88 <= x <= 225 and 78 <= y <= 170]
print("corners", len(pts))

vis = Image.fromarray(rgb)
dr = ImageDraw.Draw(vis)
for x, y in pts:
    dr.ellipse((x - 1, y - 1, x + 1, y + 1), fill=(255, 0, 0))

# Also print for each seed the nearest 4 extreme corners in NW/NE/SE/SW
seeds = [
    (108.0, 96.0),
    (138.0, 101.0),
    (167.0, 106.0),
    (196.0, 111.0),
    (104.0, 116.0),
    (133.0, 126.0),
    (161.0, 134.0),
    (194.0, 145.0),
]


def nearest_in_quadrant(sx, sy, qx, qy, limit=28):
    """qx,qy in {-1,1} for left/right and up/down."""
    best = None
    best_d = 1e9
    for x, y in pts:
        if qx < 0 and x > sx:
            continue
        if qx > 0 and x < sx:
            continue
        if qy < 0 and y > sy:
            continue
        if qy > 0 and y < sy:
            continue
        d = (x - sx) ** 2 + (y - sy) ** 2
        if d < best_d and d <= limit * limit:
            best_d = d
            best = (x, y)
    return best


for sx, sy in seeds:
    corners = [
        nearest_in_quadrant(sx, sy, -1, -1),
        nearest_in_quadrant(sx, sy, 1, -1),
        nearest_in_quadrant(sx, sy, 1, 1),
        nearest_in_quadrant(sx, sy, -1, 1),
    ]
    print(f"seed {sx,sy} -> {corners}")
    for c in corners:
        if c:
            dr.line([(sx, sy), c], fill=(0, 255, 0), width=1)

vis.crop((85, 70, 230, 180)).save("scratch/shaded_corners_qa.png")
print("wrote shaded_corners_qa.png")
