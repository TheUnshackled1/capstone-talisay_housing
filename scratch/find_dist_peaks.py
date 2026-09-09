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

ink = (gray < 108).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
dist = cv2.distanceTransform(cv2.bitwise_not(ink), cv2.DIST_L2, 5)

# Uncovered fill where dist is a local max and in lot-like range
mask = (cov == 0) & (gray >= 155) & (gray <= 205) & (dist >= 4.5) & (dist <= 14)
ys, xs = np.where(mask)
print(f"uncovered lot-like pixels: {len(xs)}")

# Non-max suppression
peaks = []
for x, y in zip(xs.tolist(), ys.tolist()):
    d = float(dist[y, x])
    if d < dist[max(0, y - 1) : y + 2, max(0, x - 1) : x + 2].max() - 1e-6:
        continue
    if any((x - px) ** 2 + (y - py) ** 2 < 70 for px, py, _ in peaks):
        continue
    peaks.append((x, y, d))

peaks.sort(key=lambda t: -t[2])
print(f"peaks: {len(peaks)}")
for x, y, d in peaks[:40]:
    print(f"  ({x},{y}) dist={d:.1f} gray={gray[y,x]}")

dbg = np.array(Image.open("scratch/lot_map_polygons_debug.png").convert("RGB"))
for x, y, d in peaks:
    cv2.circle(dbg, (x, y), 3, (255, 0, 0), -1)
Image.fromarray(dbg).save("scratch/lot_map_uncovered_peaks.png")
print("wrote scratch/lot_map_uncovered_peaks.png")
