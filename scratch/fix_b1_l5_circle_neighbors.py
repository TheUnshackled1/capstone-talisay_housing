"""Fill clickable traces around B1 L5 (idx 413) by the cul-de-sac.

Left neighbor + lot below L5. Index-stable in-place refits.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
POLY = ROOT / "static" / "units" / "lot_plan_polygons.json"
IMG = ROOT / "static" / "images" / "lot_plan_roads.png"

rgb = np.array(Image.open(IMG).convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
data = json.loads(POLY.read_text(encoding="utf-8"))
lots = data["lots"]

ink = (gray < 95).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
fillable = ((gray >= 145) & (gray <= 210)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(ink))


def r4(v: float) -> float:
    return round(float(v), 4)


def flood_lot(sx: float, sy: float, roi_box: tuple[int, int, int, int], shrink: float = 0.93) -> dict | None:
    x0, y0, x1, y1 = roi_box
    roi = np.zeros((H, W), np.uint8)
    roi[y0:y1, x0:x1] = 255
    region = cv2.bitwise_and(fillable, roi)
    ix, iy = int(round(sx)), int(round(sy))
    if region[iy, ix] == 0:
        found = False
        for r in range(1, 14):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and region[yy, xx]:
                        ix, iy = xx, yy
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if not found:
            return None
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = region.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    hard = (gray < 55).astype(np.uint8) * 255
    allow = cv2.bitwise_and(roi, cv2.bitwise_not(hard))
    for _ in range(2):
        cell = cv2.bitwise_and(cv2.dilate(cell, np.ones((3, 3), np.uint8), 1), allow)
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    box = cv2.boxPoints(cv2.minAreaRect(cnt)).astype(np.float64)
    c = box.mean(axis=0)
    box = c + (box - c) * shrink
    angs = np.arctan2(box[:, 1] - c[1], box[:, 0] - c[0])
    box = box[np.argsort(angs)]
    area_px = abs(float(cv2.contourArea(box.astype(np.float32))))
    if area_px < 100:
        return None
    return {
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in box],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    }


# L5 is idx 413 at ~392,401. Circle is on the divider to its left.
left = flood_lot(366, 398, (348, 382, 382, 418), 0.93)
below = flood_lot(392, 422, (376, 408, 412, 442), 0.93)
self_l5 = flood_lot(392, 401, (376, 384, 412, 414), 0.93)
# also the four lots around the OTHER B1 cul-de-sac (490,171) — 113 left, 127 below 111
left_circle = flood_lot(475, 165, (458, 150, 492, 180), 0.93)
below_circle = flood_lot(507, 181, (492, 168, 525, 198), 0.93)

print("left of 413", None if left is None else (round(left["cx"] * W), round(left["cy"] * H), left["area"]))
print("below 413", None if below is None else (round(below["cx"] * W), round(below["cy"] * H), below["area"]))
print("L5 413", None if self_l5 is None else (round(self_l5["cx"] * W), round(self_l5["cy"] * H), self_l5["area"]))
print("left of 111", None if left_circle is None else (round(left_circle["cx"] * W), round(left_circle["cy"] * H), left_circle["area"]))
print("below 111", None if below_circle is None else (round(below_circle["cx"] * W), round(below_circle["cy"] * H), below_circle["area"]))

if self_l5:
    lots[413] = self_l5
if left:
    lots[349] = left  # existing left neighbor, expand to cell
if below:
    lots[372] = below  # existing below neighbor, expand to cell
if left_circle:
    lots[113] = left_circle
if below_circle:
    lots[127] = below_circle

# If left flood is far from 349, append instead of overwriting the wrong lot
if left:
    d = ((left["cx"] - 366 / W) ** 2 + (left["cy"] - 394 / H) ** 2) ** 0.5
    print("left vs 349-center dist", round(d, 4))

data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print("count", len(lots))

vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for i in [349, 357, 365, 372, 384, 413, 336]:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    fill = None
    outline = (0, 170, 255, 220)
    if i == 413:
        fill = (80, 160, 255, 140)
        outline = (0, 70, 220, 255)
    if i in (349, 372, 113, 127):
        fill = (40, 210, 80, 100)
        outline = (0, 140, 40, 255)
    dr.polygon(pts, fill=fill, outline=outline)
    dr.text((L["cx"] * W - 10, L["cy"] * H - 4), str(i), fill=(220, 0, 0, 255))
vis.crop((340, 360, 430, 450)).resize((450, 450), Image.NEAREST).save(
    ROOT / "scratch" / "b1_l5_here_fixed.png"
)
vis2 = Image.fromarray(rgb.copy())
dr2 = ImageDraw.Draw(vis2, "RGBA")
for i in [100, 113, 131, 97, 111, 127, 152]:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    fill = (40, 210, 80, 90) if i in (113, 127) else None
    outline = (0, 140, 40, 255) if i in (113, 127) else (0, 170, 255, 220)
    if i == 111:
        fill = (80, 160, 255, 140)
        outline = (0, 70, 220, 255)
    dr2.polygon(pts, fill=fill, outline=outline)
vis2.crop((450, 130, 540, 220)).resize((450, 450), Image.NEAREST).save(
    ROOT / "scratch" / "b1_circle_here_fixed.png"
)
print("QA scratch/b1_l5_here_fixed.png scratch/b1_circle_here_fixed.png")
