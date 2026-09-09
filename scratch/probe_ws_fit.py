"""Watershed-fit shaded cluster cells; write QA."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

ink = (gray < 100).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
shaded = ((gray >= 130) & (gray <= 178)).astype(np.uint8) * 255
shaded = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]

# Crop ROI for speed/stability
x0, y0, x1, y1 = 90, 75, 220, 165
roi = shaded[y0:y1, x0:x1]
markers = np.zeros(roi.shape, np.int32)
for i, (sx, sy) in enumerate(seeds, start=1):
    markers[int(round(sy - y0)), int(round(sx - x0))] = i
# unknown = 0; background = -1? OpenCV watershed needs: markers >0 seeds, 0 unknown
# set non-shaded as sure background
markers[roi == 0] = -1
# convert -1 to 0 for watershed convention: 0=unknown, >0 seeds... actually
# OpenCV: markers must be 32-bit; 0 = unknown to label, non-zero = barriers/seeds
# Better: sure-bg = 255? Standard recipe:
# markers: 0 unknown, 1..N seeds, and sure background as another label

markers2 = np.zeros(roi.shape, np.int32)
markers2[roi == 0] = 255  # background
for i, (sx, sy) in enumerate(seeds, start=1):
    cv2.circle(markers2, (int(round(sx - x0)), int(round(sy - y0))), 2, i, -1)

img_bgr = cv2.cvtColor(rgb[y0:y1, x0:x1], cv2.COLOR_RGB2BGR)
ws = markers2.copy()
cv2.watershed(img_bgr, ws)

img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
for i, (sx, sy) in enumerate(seeds, start=1):
    cell = (ws == i).astype(np.uint8) * 255
    ys, xs = np.where(cell > 0)
    if len(xs) < 30:
        print(f"seed {i} tiny {len(xs)}")
        continue
    pts = np.column_stack([xs + x0, ys + y0]).astype(np.float32)
    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect)
    c = box.mean(axis=0)
    box = c + (box - c) * 0.90
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    (cx, cy), (rw, rh), ang = rect
    print(f"#{i} ({sx:.0f},{sy:.0f}) -> ({cx:.1f},{cy:.1f}) {min(rw,rh):.1f}x{max(rw,rh):.1f} ang={ang:.1f} n={len(xs)}")

out = ROOT / "scratch" / "shaded_ws_fit.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
