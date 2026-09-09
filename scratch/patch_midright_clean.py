"""Clean mid-right block: drop ALL intersecting leftovers, refit with flood."""
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

# Slightly larger bbox so edge leftovers get replaced too
X0, X1, Y0, Y1 = 555, 775, 170, 355

sep = (gray < 80).astype(np.uint8) * 255
sep = cv2.dilate(sep, np.ones((2, 2), np.uint8), 1)
roi = np.zeros((H, W), np.uint8)
roi[Y0:Y1, X0:X1] = 255
fillable = ((gray >= 95) & (gray <= 205)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, roi)
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(sep))

path = ROOT / "static" / "units" / "lot_plan_polygons.json"
data = json.loads(path.read_text(encoding="utf-8"))


def intersects_region(L: dict) -> bool:
    pts = np.array(L["points"], dtype=np.float32) * [W, H]
    minx, miny = pts.min(axis=0)
    maxx, maxy = pts.max(axis=0)
    return not (maxx < X0 or minx > X1 or maxy < Y0 or miny > Y1)


# Keep only lots that do NOT intersect this visual block
kept = [L for L in data["lots"] if not intersects_region(L)]
removed = len(data["lots"]) - len(kept)
print("removed intersecting", removed, "kept", len(kept))

# Seeds from distance-transform peaks inside fillable (reliable cell centers)
dist = cv2.distanceTransform(fillable, cv2.DIST_L2, 5)
seeds = []
dist_work = dist.copy()
for _ in range(80):
    _mn, maxVal, _mnLoc, maxLoc = cv2.minMaxLoc(dist_work)
    if maxVal < 3.2:
        break
    sx, sy = float(maxLoc[0]), float(maxLoc[1])
    # skip if too close to an existing seed
    if any((sx - t[0]) ** 2 + (sy - t[1]) ** 2 < 9**2 for t in seeds):
        cv2.circle(dist_work, maxLoc, 8, 0, -1)
        continue
    seeds.append((sx, sy))
    cv2.circle(dist_work, maxLoc, 9, 0, -1)
print("seeds", len(seeds))


def r4(v: float) -> float:
    return round(float(v), 4)


def flood_cell(sx: float, sy: float) -> np.ndarray | None:
    ix, iy = int(round(sx)), int(round(sy))
    if fillable[iy, ix] == 0:
        for r in range(1, 12):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and fillable[yy, xx]:
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
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    area0 = int(cell.sum() // 255)
    if area0 < 60 or area0 > 2800:
        return None
    # Grow 2px toward ink walls
    hard = (gray < 55).astype(np.uint8) * 255
    allow = cv2.bitwise_and(roi, cv2.bitwise_not(hard))
    for _ in range(2):
        cell = cv2.bitwise_and(cv2.dilate(cell, np.ones((3, 3), np.uint8), 1), allow)
    return cell


vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
fixed = []
used: list[np.ndarray] = []

for sx, sy in seeds:
    cell = flood_cell(sx, sy)
    if cell is None:
        continue
    area = int(cell.sum() // 255)
    if area < 80 or area > 3000:
        continue
    if any(int(np.logical_and(cell > 0, m > 0).sum()) > area * 0.3 for m in used):
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
    c = arr.mean(axis=0)
    dr.polygon(poly, fill=(40, 150, 255, 110), outline=(0, 70, 220, 255))
    dr.ellipse((int(sx) - 1, int(sy) - 1, int(sx) + 1, int(sy) + 1), fill=(255, 255, 255, 255))
    used.append(cell)
    fixed.append({
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in poly],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    })
    print(f"OK {sx:.0f},{sy:.0f} n={len(poly)} area={area_px:.0f}")

vis.crop((560, 175, 770, 350)).resize((630, 525), Image.NEAREST).save(
    ROOT / "scratch" / "midright_qa.png"
)
vis.crop((680, 185, 760, 340)).resize((320, 620), Image.NEAREST).save(
    ROOT / "scratch" / "midright_col_qa.png"
)

kept.extend(fixed)
kept.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = kept
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("lots", len(kept), "fixed", len(fixed))
