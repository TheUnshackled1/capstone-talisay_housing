"""Split shaded cells by thick ink dilation, then minAreaRect each."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

ink = (gray < 108).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((3, 3), np.uint8), 2)  # thick barriers
shaded = ((gray >= 125) & (gray <= 185)).astype(np.uint8) * 255
cells = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
cells = cv2.morphologyEx(cells, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]

img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)

for sx, sy in seeds:
    ix, iy = int(round(sx)), int(round(sy))
    if cells[iy, ix] == 0:
        found = False
        for r in range(1, 10):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and cells[yy, xx]:
                        ix, iy, found = xx, yy, True
                        break
                if found:
                    break
            if found:
                break
    if cells[iy, ix] == 0:
        print(f"miss ({sx},{sy})")
        continue
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = cells.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    # expand a bit into the thick border zone so size matches drawing
    cell = cv2.dilate(cell, np.ones((3, 3), np.uint8), 1)
    ys, xs = np.where(cell > 0)
    if len(xs) < 40:
        print(f"tiny ({sx},{sy}) n={len(xs)}")
        continue
    pts = np.column_stack([xs, ys]).astype(np.float32)
    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect).astype(np.float32)
    c = box.mean(axis=0)
    box = c + (box - c) * 0.94
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    (cx, cy), (rw, rh), ang = rect
    print(f"({sx:.0f},{sy:.0f}) -> ({cx:.1f},{cy:.1f}) {min(rw,rh):.1f}x{max(rw,rh):.1f} ang={ang:.1f} n={len(xs)}")

out = ROOT / "scratch" / "shaded_inksplit_fit.png"
img.crop((90, 70, 230, 180)).save(out)
# also save cells mask crop
Image.fromarray(cells[70:180, 90:230]).save(ROOT / "scratch" / "shaded_cells_mask.png")
print("wrote", out)
