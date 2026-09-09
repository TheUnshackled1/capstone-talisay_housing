"""Dump ink-split boxes and patch JSON with fixed shaded quads."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
W, H = 906, 543
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

ink = (gray < 108).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((3, 3), np.uint8), 2)
shaded = ((gray >= 125) & (gray <= 185)).astype(np.uint8) * 255
cells = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
cells = cv2.morphologyEx(cells, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]


def order_quad(pts):
    arr = np.array(pts, dtype=float)
    ang = np.arctan2(arr[:, 1] - arr[:, 1].mean(), arr[:, 0] - arr[:, 0].mean())
    return [pts[int(j)] for j in np.argsort(ang)]


def box_for(sx, sy, shrink=0.90):
    ix, iy = int(round(sx)), int(round(sy))
    if cells[iy, ix] == 0:
        for r in range(1, 12):
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
    cell = (flood == 200).astype(np.uint8) * 255
    # modest grow toward borders
    cell = cv2.dilate(cell, np.ones((3, 3), np.uint8), 1)
    allow = ((gray >= 120) & (gray <= 188)).astype(np.uint8) * 255
    cell = cv2.bitwise_and(cell, allow)
    ys, xs = np.where(cell > 0)
    if len(xs) < 60:
        return None
    pts = np.column_stack([xs, ys]).astype(np.float32)
    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect).astype(np.float32)
    c = box.mean(axis=0)
    box = c + (box - c) * shrink
    return box


img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
fixed = []
for sx, sy in seeds:
    box = box_for(sx, sy)
    if box is None:
        print("FAIL", sx, sy)
        continue
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 200, 255), width=2)
    fixed.append(box)
    print("OK", sx, sy, box.mean(axis=0))

img.crop((90, 70, 230, 180)).save(ROOT / "scratch" / "shaded_fixed_qa.png")

# Patch JSON
path = ROOT / "static" / "units" / "lot_plan_polygons.json"
data = json.loads(path.read_text())
lots = [
    L for L in data["lots"]
    if not (95 <= L["cx"] * W <= 210 and 85 <= L["cy"] * H <= 155)
]
for box in fixed:
    pts = order_quad([[round(float(x) / W, 4), round(float(y) / H, 4)] for x, y in box])
    c = box.mean(axis=0)
    # approx area from AABB
    bw = float(box[:, 0].max() - box[:, 0].min())
    bh = float(box[:, 1].max() - box[:, 1].min())
    lots.append({
        "points": pts,
        "cx": round(float(c[0]) / W, 4),
        "cy": round(float(c[1]) / H, 4),
        "area": round(bw * bh / (W * H), 4),
    })
lots.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = lots
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("lots", len(lots), "shaded", len(fixed))
