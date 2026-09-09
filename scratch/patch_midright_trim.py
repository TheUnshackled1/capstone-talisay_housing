"""Drop oversized leaked polys in mid-right; keep good flood fits only."""
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
path = ROOT / "static" / "units" / "lot_plan_polygons.json"
data = json.loads(path.read_text(encoding="utf-8"))

X0, X1, Y0, Y1 = 555, 775, 170, 355

# Remove oversized / bad from region
clean = []
dropped = 0
for L in data["lots"]:
    cx, cy = L["cx"] * W, L["cy"] * H
    if X0 <= cx <= X1 and Y0 <= cy <= Y1 and L["area"] > 0.003:
        print("drop big", round(cx), round(cy), L["area"])
        dropped += 1
        continue
    clean.append(L)

# Re-seed only the holes: distance peaks where no existing poly covers
sep = (gray < 80).astype(np.uint8) * 255
sep = cv2.dilate(sep, np.ones((2, 2), np.uint8), 1)
roi = np.zeros((H, W), np.uint8)
roi[Y0:Y1, X0:X1] = 255
fillable = ((gray >= 95) & (gray <= 205)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, roi)
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(sep))

covered = np.zeros((H, W), np.uint8)
for L in clean:
    cx, cy = L["cx"] * W, L["cy"] * H
    if not (X0 <= cx <= X1 and Y0 <= cy <= Y1):
        continue
    pts = (np.array(L["points"]) * [W, H]).astype(np.int32)
    cv2.fillPoly(covered, [pts], 255)

open_fill = cv2.bitwise_and(fillable, cv2.bitwise_not(covered))
dist = cv2.distanceTransform(open_fill, cv2.DIST_L2, 5)


def r4(v: float) -> float:
    return round(float(v), 4)


def flood_cell(sx, sy):
    ix, iy = int(round(sx)), int(round(sy))
    if fillable[iy, ix] == 0:
        for r in range(1, 10):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and fillable[yy, xx] and covered[yy, xx] == 0:
                        ix, iy = xx, yy
                        break
                else:
                    continue
                break
            else:
                continue
            break
    if fillable[iy, ix] == 0:
        return None
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = fillable.copy()
    # block already-covered from flood expansion
    flood[covered > 0] = 0
    if flood[iy, ix] == 0:
        return None
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    a = int(cell.sum() // 255)
    if a < 80 or a > 1400:
        return None
    hard = (gray < 55).astype(np.uint8) * 255
    allow = cv2.bitwise_and(roi, cv2.bitwise_not(hard))
    for _ in range(2):
        cell = cv2.bitwise_and(cv2.dilate(cell, np.ones((3, 3), np.uint8), 1), allow)
        cell = cv2.bitwise_and(cell, cv2.bitwise_not(covered))
    return cell


added = []
vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
# draw existing good ones
for L in clean:
    cx, cy = L["cx"] * W, L["cy"] * H
    if X0 <= cx <= X1 and Y0 <= cy <= Y1:
        pts = [(int(p[0] * W), int(p[1] * H)) for p in L["points"]]
        dr.polygon(pts, fill=(40, 150, 255, 90), outline=(0, 70, 220, 255))

for _ in range(30):
    _mn, maxVal, _mnLoc, maxLoc = cv2.minMaxLoc(dist)
    if maxVal < 3.5:
        break
    sx, sy = float(maxLoc[0]), float(maxLoc[1])
    cv2.circle(dist, maxLoc, 10, 0, -1)
    cell = flood_cell(sx, sy)
    if cell is None:
        print("skip", sx, sy)
        continue
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        continue
    cnt = max(cnts, key=cv2.contourArea)
    peri = float(cv2.arcLength(cnt, True))
    approx = cv2.approxPolyDP(cnt, max(0.55, 0.01 * peri), True)
    if len(approx) < 3:
        approx = cnt
    poly = [(int(p[0][0]), int(p[0][1])) for p in approx]
    arr = np.array(poly, dtype=np.float32)
    area_px = float(cv2.contourArea(arr))
    if area_px > 1400:
        print("skip big", sx, sy, area_px)
        continue
    c = arr.mean(axis=0)
    lot = {
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in poly],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    }
    added.append(lot)
    cv2.fillPoly(covered, [np.array(poly, dtype=np.int32)], 255)
    dr.polygon(poly, fill=(40, 200, 120, 110), outline=(0, 160, 80, 255))
    print("add", round(sx), round(sy), "n", len(poly), "area", round(area_px))

clean.extend(added)
clean.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = clean
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
vis.crop((560, 175, 770, 350)).resize((630, 525), Image.NEAREST).save(
    ROOT / "scratch" / "midright_qa.png"
)
print("dropped", dropped, "added", len(added), "lots", len(clean))
