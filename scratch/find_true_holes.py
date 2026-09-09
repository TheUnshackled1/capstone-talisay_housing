import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
H, W = gray.shape
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]
cov = np.zeros((H, W), np.uint8)
for L in lots:
    p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], np.int32)
    cv2.fillConvexPoly(cov, p, 255)
# Expand so shrink gaps aren't treated as missing lots
cov_pad = cv2.dilate(cov, np.ones((9, 9), np.uint8), 1)

ink = (gray < 108).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
dist = cv2.distanceTransform(cv2.bitwise_not(ink), cv2.DIST_L2, 5)

mask = (cov_pad == 0) & (gray >= 155) & (gray <= 200) & (dist >= 5.5) & (dist <= 11.0)
ys, xs = np.where(mask)
print(f"true-hole pixels: {len(xs)}")


def enclosure_hits(sx, sy, med=21.0):
    hits = 0
    for ang in (0, 45, 90, 135, 180, 225, 270, 315):
        rad = np.deg2rad(ang)
        for t in np.linspace(med * 0.28, med * 0.70, 10):
            xx = int(round(sx + t * np.cos(rad)))
            yy = int(round(sy + t * np.sin(rad)))
            if not (0 <= xx < W and 0 <= yy < H):
                break
            if ink[yy, xx]:
                hits += 1
                break
    return hits


peaks = []
for x, y in zip(xs.tolist(), ys.tolist()):
    d = float(dist[y, x])
    # local max in 5x5
    if d + 1e-6 < dist[max(0, y - 2) : y + 3, max(0, x - 2) : x + 3].max():
        continue
    if enclosure_hits(x, y) < 5:
        continue
    if any((x - px) ** 2 + (y - py) ** 2 < 100 for px, py, _ in peaks):
        continue
    peaks.append((x, y, d))

peaks.sort(key=lambda t: -t[2])
print(f"true peaks: {len(peaks)}")
for x, y, d in peaks:
    print(f"  ({x},{y}) dist={d:.1f} gray={gray[y,x]} hits={enclosure_hits(x,y)}")

dbg = np.array(Image.open("scratch/lot_map_polygons_debug.png").convert("RGB"))
for x, y, d in peaks:
    cv2.circle(dbg, (x, y), 4, (255, 0, 0), -1)
Image.fromarray(dbg).save("scratch/lot_map_true_holes.png")
print("wrote scratch/lot_map_true_holes.png")
