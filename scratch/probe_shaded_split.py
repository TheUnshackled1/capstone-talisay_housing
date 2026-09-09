"""Probe how to split the merged shaded 2x4 block into cells."""
import cv2
import numpy as np
from PIL import Image

W, H = 906, 543
gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)

x0, y0, ww, hh = 90, 80, 130, 90
roi = gray[y0 : y0 + hh, x0 : x0 + ww]
ink = (roi < 100).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
shaded = ((roi >= 130) & (roi <= 178)).astype(np.uint8) * 255
shaded = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))

# erode to split cells
for k in (3, 5, 7):
    er = cv2.erode(shaded, np.ones((k, k), np.uint8), 1)
    n, _, stats, cents = cv2.connectedComponentsWithStats(er, 8)
    big = [(i, stats[i, cv2.CC_STAT_AREA], cents[i]) for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 40]
    print(f"erode {k}x{k}: {len(big)} cells")
    for i, a, c in big[:12]:
        print(f"  area={a} center=({c[0]+x0:.0f},{c[1]+y0:.0f})")

# distance transform peaks
dist = cv2.distanceTransform(shaded, cv2.DIST_L2, 5)
# local maxima
kern = np.ones((15, 15), np.uint8)
dil = cv2.dilate(dist, kern)
peaks = (dist == dil) & (dist >= 4.0) & (shaded > 0)
ys, xs = np.where(peaks)
print(f"\ndist peaks (>=4): {len(xs)}")
# non-max suppress by greedily keeping far peaks
pts = list(zip(xs.tolist(), ys.tolist(), dist[ys, xs].tolist()))
pts.sort(key=lambda t: -t[2])
kept = []
for x, y, d in pts:
    if any((x - kx) ** 2 + (y - ky) ** 2 < 14**2 for kx, ky, _ in kept):
        continue
    kept.append((x, y, d))
print(f"after NMS: {len(kept)}")
for x, y, d in kept:
    print(f"  ({x+x0:.0f},{y+y0:.0f}) d={d:.1f}")

# save viz
viz = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
for x, y, d in kept:
    cv2.circle(viz, (x, y), 3, (0, 255, 255), -1)
Image.fromarray(cv2.cvtColor(viz, cv2.COLOR_BGR2RGB)).save("scratch/crop_shaded_peaks.png")
print("wrote scratch/crop_shaded_peaks.png")
