"""Tune contour fit to match gray pad drawing."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]


def build_cells(ink_dilate_iter, cell_dilate_iter):
    ink = (gray < 108).astype(np.uint8) * 255
    ink = cv2.dilate(ink, np.ones((3, 3), np.uint8), ink_dilate_iter)
    shaded = ((gray >= 125) & (gray <= 185)).astype(np.uint8) * 255
    cells = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
    cells = cv2.morphologyEx(cells, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)
    return cells, cell_dilate_iter


def fit(cells, cell_dilate_iter, sx, sy):
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
        return None
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = cells.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    if cell_dilate_iter:
        cell = cv2.dilate(cell, np.ones((3, 3), np.uint8), cell_dilate_iter)
    # clip growth so we don't spill into neighbors: keep within mid-gray+near
    allow = ((gray >= 115) & (gray <= 190)).astype(np.uint8) * 255
    cell = cv2.bitwise_and(cell, allow)
    contours, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    cnt = max(contours, key=cv2.contourArea)
    if cv2.contourArea(cnt) < 80:
        return None
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.012 * peri, True)
    if len(approx) < 3:
        return None
    pts = approx.reshape(-1, 2).astype(np.float32)
    return [(float(x), float(y)) for x, y in pts]


# Try ink_dilate=1, cell_dilate=2
cells, cd = build_cells(1, 2)
img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
for sx, sy in seeds:
    poly = fit(cells, cd, sx, sy)
    if not poly:
        print("fail", sx, sy)
        continue
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    print(f"ok ({sx:.0f},{sy:.0f}) verts={len(poly)}")

out = ROOT / "scratch" / "shaded_contour_tuned.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
