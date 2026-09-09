"""Test flood separation with mild ink."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

# Mild ink: dark lines only, light dilate
ink = (gray < 90).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
# Pads are ~165 gray
shaded = ((gray >= 140) & (gray <= 185)).astype(np.uint8) * 255
cells = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
# NO morph close (that merges)

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

vis = rgb.copy()
colors = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 128, 0),
    (128, 0, 255),
]
areas = []
for i, (sx, sy) in enumerate(seeds):
    ix, iy = int(sx), int(sy)
    if cells[iy, ix] == 0:
        found = False
        for r in range(1, 20):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and cells[yy, xx]:
                        ix, iy = xx, yy
                        found = True
                        break
                if found:
                    break
            if found:
                break
    if cells[iy, ix] == 0:
        print("NO CELL", sx, sy)
        continue
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = cells.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8)
    area = int(cell.sum())
    areas.append(area)
    # Grow toward borders: dilate into near-pad OR near-black-adjacent pad pixels
    grown = cell.copy() * 255
    grown = cv2.dilate(grown, np.ones((3, 3), np.uint8), 3)
    # keep pixels that are pad-ish OR dark border (we'll use contour of grown&~road)
    keep = ((gray >= 100) & (gray <= 190)).astype(np.uint8) * 255
    grown = cv2.bitwise_and(grown, keep)
    # Also include dark border pixels adjacent to cell for outer edge
    border = ((gray < 90) & (cv2.dilate(cell * 255, np.ones((3, 3), np.uint8), 2) > 0)).astype(
        np.uint8
    ) * 255
    # Use pad-only for fill geometry (not border ink)
    cnts, _ = cv2.findContours(grown, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        print("no contour", sx, sy, area)
        continue
    cnt = max(cnts, key=cv2.contourArea)
    # Force 4-point via minAreaRect — but expand to cover contour extrema
    rect = cv2.minAreaRect(cnt)
    box = cv2.boxPoints(rect)
    # Expand box slightly so it reaches ink
    c = box.mean(axis=0)
    box = c + (box - c) * 1.05
    box_i = box.astype(np.int32)
    cv2.polylines(vis, [box_i], True, colors[i], 2)
    cv2.drawContours(vis, [cnt], -1, colors[i], 1)
    cv2.circle(vis, (int(sx), int(sy)), 3, (255, 255, 255), -1)
    print(f"seed {i} {sx,sy} flood={area} contour={cv2.contourArea(cnt):.0f} box={rect}")

print("areas", areas, "unique-ish", len(set(areas)))
Image.fromarray(vis).crop((85, 70, 230, 180)).save("scratch/fit_separated.png")
Image.fromarray(cells).crop((85, 70, 230, 180)).save("scratch/cells_mask.png")
print("done")
