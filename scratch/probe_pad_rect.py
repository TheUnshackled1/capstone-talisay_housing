"""minAreaRect on lightly-split gray pads — match drawing."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

# Light ink barrier only — keep gray pads intact
ink = cv2.dilate((gray < 100).astype(np.uint8) * 255, np.ones((2, 2), np.uint8), 1)
pad = ((gray >= 130) & (gray <= 175)).astype(np.uint8) * 255
pad = cv2.bitwise_and(pad, cv2.bitwise_not(ink))
pad = cv2.morphologyEx(pad, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)
# light erode to split merges without shrinking too much
pad_split = cv2.erode(pad, np.ones((2, 2), np.uint8), 1)

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]


def fit(sx, sy):
    ix, iy = int(round(sx)), int(round(sy))
    src = pad_split
    if src[iy, ix] == 0:
        for r in range(1, 12):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and src[yy, xx]:
                        ix, iy = xx, yy
                        break
                else:
                    continue
                break
            else:
                continue
            break
    if src[iy, ix] == 0:
        return None
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = src.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    # restore size lost to erode
    cell = cv2.dilate(cell, np.ones((2, 2), np.uint8), 1)
    cell = cv2.bitwise_and(cell, pad)
    ys, xs = np.where(cell > 0)
    if len(xs) < 40:
        return None
    pts = np.column_stack([xs, ys]).astype(np.float32)
    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect).astype(np.float32)
    c = box.mean(axis=0)
    box = c + (box - c) * 0.97
    return box, c, rect


img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
for sx, sy in seeds:
    hit = fit(sx, sy)
    if not hit:
        print("fail", sx, sy)
        continue
    box, c, rect = hit
    (cx, cy), (rw, rh), ang = rect
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    print(f"({sx:.0f},{sy:.0f}) -> ({c[0]:.1f},{c[1]:.1f}) {min(rw,rh):.1f}x{max(rw,rh):.1f} ang={ang:.1f}")

out = ROOT / "scratch" / "shaded_pad_rect.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
