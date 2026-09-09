"""Watershed on gray pads with seed markers — best cell split."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

x0, y0, x1, y1 = 88, 78, 220, 165
roi_gray = gray[y0:y1, x0:x1]
ink = cv2.dilate((roi_gray < 100).astype(np.uint8) * 255, np.ones((2, 2), np.uint8), 1)
pad = ((roi_gray >= 128) & (roi_gray <= 178)).astype(np.uint8) * 255
pad = cv2.bitwise_and(pad, cv2.bitwise_not(ink))

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]

markers = np.zeros(pad.shape, np.int32)
markers[pad == 0] = 255
for i, (sx, sy) in enumerate(seeds, start=1):
    # larger seed disks so watershed claims full cell
    cv2.circle(markers, (int(round(sx - x0)), int(round(sy - y0))), 4, i, -1)

bgr = cv2.cvtColor(rgb[y0:y1, x0:x1], cv2.COLOR_RGB2BGR)
ws = markers.copy()
cv2.watershed(bgr, ws)

img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
boxes = []
for i, (sx, sy) in enumerate(seeds, start=1):
    cell = (ws == i).astype(np.uint8) * 255
    # restrict to pad-ish
    cell = cv2.bitwise_and(cell, ((roi_gray >= 120) & (roi_gray <= 185)).astype(np.uint8) * 255)
    ys, xs = np.where(cell > 0)
    if len(xs) < 50:
        print(f"#{i} tiny {len(xs)}")
        continue
    pts = np.column_stack([xs + x0, ys + y0]).astype(np.float32)
    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect).astype(np.float32)
    c = box.mean(axis=0)
    box = c + (box - c) * 0.93
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    (cx, cy), (rw, rh), ang = rect
    print(f"#{i} ({sx:.0f},{sy:.0f}) n={len(xs)} {min(rw,rh):.1f}x{max(rw,rh):.1f} ang={ang:.1f}")
    boxes.append(box)

out = ROOT / "scratch" / "shaded_ws2_fit.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
