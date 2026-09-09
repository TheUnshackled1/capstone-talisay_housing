"""Refit mid-right block via ink-separated flood + contour (no ray leak)."""
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

X0, X1, Y0, Y1 = 560, 760, 185, 340

# Thick ink walls
sep = (gray < 80).astype(np.uint8) * 255
sep = cv2.dilate(sep, np.ones((2, 2), np.uint8), 1)

# Fillable: non-ink, non-bright-road, in ROI
roi = np.zeros((H, W), np.uint8)
roi[Y0:Y1, X0:X1] = 255
fillable = ((gray >= 90) & (gray <= 210)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, roi)
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(sep))

# Seeds = existing polygon centers in region + a few extras for shaded pads
path = ROOT / "static" / "units" / "lot_plan_polygons.json"
data = json.loads(path.read_text(encoding="utf-8"))

# Re-load BEFORE our bad patch? We already overwrote. Use current centers + pad peaks.
seeds = []
for L in data["lots"]:
    cx, cy = L["cx"] * W, L["cy"] * H
    if X0 <= cx <= X1 and Y0 <= cy <= Y1:
        seeds.append((float(cx), float(cy)))

# Also distance-transform peaks inside fillable for missing cells
dist = cv2.distanceTransform(fillable, cv2.DIST_L2, 5)
# suppress near existing seeds
for sx, sy in list(seeds):
    cv2.circle(dist, (int(sx), int(sy)), 10, 0, -1)
# find peaks
for _ in range(40):
    minVal, maxVal, minLoc, maxLoc = cv2.minMaxLoc(dist)
    if maxVal < 3.5:
        break
    seeds.append((float(maxLoc[0]), float(maxLoc[1])))
    cv2.circle(dist, maxLoc, 10, 0, -1)

# Dedupe
uniq = []
for s in seeds:
    if any((s[0] - t[0]) ** 2 + (s[1] - t[1]) ** 2 < 10**2 for t in uniq):
        continue
    uniq.append(s)
seeds = uniq
print("seeds", len(seeds))


def r4(v: float) -> float:
    return round(float(v), 4)


def flood_cell(sx: float, sy: float) -> np.ndarray | None:
    ix, iy = int(round(sx)), int(round(sy))
    if fillable[iy, ix] == 0:
        for r in range(1, 14):
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
    # Grow toward ink midpoint: dilate a few times into non-hard-ink
    hard = (gray < 55).astype(np.uint8) * 255
    allow = cv2.bitwise_and(roi, cv2.bitwise_not(hard))
    for _ in range(3):
        grown = cv2.dilate(cell, np.ones((3, 3), np.uint8), 1)
        grown = cv2.bitwise_and(grown, allow)
        # don't cross into other fillable cells that weren't ours — stop at sep
        # allow can include sep fringe; keep away from other seeds later
        cell = grown
    return cell


vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
fixed = []
used_masks: list[np.ndarray] = []

for sx, sy in seeds:
    cell = flood_cell(sx, sy)
    if cell is None:
        print("FAIL flood", sx, sy)
        continue
    area = int(cell.sum() // 255)
    if area < 70 or area > 4500:
        print("FAIL area", sx, sy, area)
        continue
    # Overlap check with already accepted
    overlap_bad = False
    for m in used_masks:
        inter = int(np.logical_and(cell > 0, m > 0).sum())
        if inter > area * 0.35:
            overlap_bad = True
            break
    if overlap_bad:
        print("DROP overlap", sx, sy)
        continue

    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        continue
    cnt = max(cnts, key=cv2.contourArea)
    peri = float(cv2.arcLength(cnt, True))
    approx = cv2.approxPolyDP(cnt, max(0.6, 0.012 * peri), True)
    if len(approx) < 3:
        approx = cnt
    poly = [(int(p[0][0]), int(p[0][1])) for p in approx]
    arr = np.array(poly, dtype=np.float32)
    area_px = float(cv2.contourArea(arr))
    c = arr.mean(axis=0)
    if not (X0 <= c[0] <= X1 and Y0 <= c[1] <= Y1):
        print("DROP oob", sx, sy)
        continue

    dr.polygon(poly, fill=(40, 150, 255, 110), outline=(0, 70, 220, 255))
    dr.ellipse((int(sx) - 1, int(sy) - 1, int(sx) + 1, int(sy) + 1), fill=(255, 255, 255, 255))
    used_masks.append(cell)
    fixed.append({
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in poly],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    })
    print(f"OK {sx,sy} n={len(poly)} area={area_px:.0f}")

vis.crop((X0, Y0, X1, Y1)).resize((600, 450), Image.NEAREST).save(
    ROOT / "scratch" / "midright_qa.png"
)

# Replace region lots
kept = [
    L
    for L in data["lots"]
    if not (X0 <= L["cx"] * W <= X1 and Y0 <= L["cy"] * H <= Y1)
]
kept.extend(fixed)
kept.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = kept
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("lots", len(kept), "fixed", len(fixed))
