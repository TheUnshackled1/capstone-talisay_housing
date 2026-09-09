"""Probe CC-based minAreaRect fit for shaded cells."""
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
# erode to split merged cells
split = cv2.erode(shaded, np.ones((3, 3), np.uint8), 1)

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]

img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)

for sx, sy in seeds:
    ix, iy = int(round(sx)), int(round(sy))
    # flood from seed on split mask
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = split.copy()
    if flood[iy, ix] == 0:
        # nudge to nearest shaded pixel
        found = False
        for r in range(1, 8):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and split[yy, xx]:
                        ix, iy = xx, yy
                        found = True
                        break
                if found:
                    break
            if found:
                break
    if flood[iy, ix] == 0:
        print(f"no fill at ({sx},{sy})")
        continue
    cv2.floodFill(flood, mask, (ix, iy), 128)
    cell = (flood == 128).astype(np.uint8) * 255
    # grow slightly back toward original borders
    cell = cv2.dilate(cell, np.ones((3, 3), np.uint8), 1)
    cell = cv2.bitwise_and(cell, shaded)
    ys, xs = np.where(cell > 0)
    if len(xs) < 20:
        print(f"tiny cell ({sx},{sy})")
        continue
    pts = np.column_stack([xs, ys]).astype(np.float32)
    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect)
    # shrink a bit so hover stays inside thick border
    c = box.mean(axis=0)
    box = c + (box - c) * 0.92
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    dr.ellipse((sx - 2, sy - 2, sx + 2, sy + 2), fill=(255, 0, 0))
    (cx, cy), (rw, rh), ang = rect
    print(f"({sx:.0f},{sy:.0f}) -> ({cx:.1f},{cy:.1f}) {rw:.1f}x{rh:.1f} ang={ang:.1f}")

out = ROOT / "scratch" / "shaded_cc_fit.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
