"""Compare contour vs minAreaRect fits for shaded cluster."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
print("shape", W, H)

ink = (gray < 100).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
shaded = ((gray >= 120) & (gray <= 190)).astype(np.uint8) * 255
cells = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
cells = cv2.morphologyEx(cells, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 1)

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


def flood_cell(sx, sy):
    ix, iy = int(round(sx)), int(round(sy))
    if cells[iy, ix] == 0:
        for r in range(1, 15):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and cells[yy, xx]:
                        ix, iy = xx, yy
                        break
                else:
                    continue
                break
            else:
                continue
            break
    if cells[iy, ix] == 0:
        return None
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = cells.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    return (flood == 200).astype(np.uint8) * 255


vis = rgb.copy()
for sx, sy in seeds:
    cell = flood_cell(sx, sy)
    if cell is None:
        print("fail", sx, sy)
        continue
    cell2 = cv2.dilate(cell, np.ones((3, 3), np.uint8), 2)
    allow = ((gray >= 115) & (gray <= 195)).astype(np.uint8) * 255
    cell2 = cv2.bitwise_and(cell2, allow)
    cnts, _ = cv2.findContours(cell2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnt = max(cnts, key=cv2.contourArea)
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
    rect = cv2.minAreaRect(cnt)
    box = cv2.boxPoints(rect).astype(np.int32)
    x, y, w, h = cv2.boundingRect(cnt)
    print(
        f"seed {sx, sy} area={cv2.contourArea(cnt):.0f} "
        f"approxN={len(approx)} rect={rect[1]} aabb={w}x{h}"
    )
    cv2.drawContours(vis, [approx], -1, (0, 255, 255), 1)
    cv2.polylines(vis, [box], True, (255, 0, 255), 1)
    cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 1)
    cv2.circle(vis, (int(sx), int(sy)), 2, (255, 0, 0), -1)

Image.fromarray(vis).crop((85, 70, 230, 180)).save("scratch/fit_compare.png")
print("wrote fit_compare")
reg = gray[75:175, 90:220]
print("gray hist peaks", np.bincount(reg.ravel()).argsort()[-8:][::-1])
