"""Trace small wedge below lot 411 into index 362."""
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
IDX = 362
POLY = Path("static/units/lot_plan_polygons.json")
bak = Path("scratch/lot_plan_polygons_before_trace_362.json")
shutil.copy(POLY, bak)

data = json.loads(POLY.read_text(encoding="utf-8"))
lots = data["lots"]
assert len(lots) == 420

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = np.array(Image.open("static/images/lot_plan_roads.png").convert("L"), float)

def mask_of_lot(i: int) -> np.ndarray:
    m = np.zeros((H, W), np.uint8)
    pts = lots[i].get("points") or []
    if len(pts) < 3:
        return m
    p = np.array([[int(p[0] * W), int(p[1] * H)] for p in pts], np.int32)
    cv2.fillConvexPoly(m, p, 255)
    return m


ROI = (585, 504, 622, 520)
SEED = (600, 510)
x0, y0, x1, y1 = ROI
ink = (gray < 70).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
fillable = ((gray >= 145) & (gray <= 210)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(ink))
blocked = cv2.bitwise_or(ink, mask_of_lot(411))
allow = cv2.bitwise_and(cv2.bitwise_not(blocked), fillable)
roi_m = np.zeros((H, W), np.uint8)
roi_m[y0:y1, x0:x1] = 255
region = cv2.bitwise_and(allow, roi_m)
mask = np.zeros((H + 2, W + 2), np.uint8)
flood = region.copy()
cv2.floodFill(flood, mask, SEED, 200)
comp = (flood == 200).astype(np.uint8) * 255
cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
cnt = max(cnts, key=cv2.contourArea)
peri = cv2.arcLength(cnt, True)
xy = cv2.approxPolyDP(cnt, 0.02 * peri, True).reshape(-1, 2).astype(float)
xy += 0.5

area_px = abs(float(cv2.contourArea(xy.astype(np.float32))))
print("npts", len(xy), "area_px", area_px, "pts", [(round(x, 1), round(y, 1)) for x, y in xy])


def r4(v: float) -> float:
    return round(float(v), 4)


def to_norm(xy_arr: np.ndarray) -> list:
    return [[float(x / W), float(y / H)] for x, y in xy_arr]


lots[IDX] = {
    "points": to_norm(xy),
    "cx": r4(xy[:, 0].mean() / W),
    "cy": r4(xy[:, 1].mean() / H),
    "area": r4(area_px / (W * H)),
}
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2), encoding="utf-8")


ov = int((mask_of_lot(IDX) // 255 & mask_of_lot(411) // 255).sum())
print("overlap with 411 px", ov)
assert ov == 0
assert 20 < area_px < 200

vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
for i in [411, IDX]:
    pts = [(p[0] * W, p[1] * H) for p in lots[i]["points"]]
    col = (30, 100, 255, 170) if i == IDX else (255, 120, 30, 120)
    dr.polygon(pts, fill=col, outline=(0, 40, 180, 255))
    dr.text((lots[i]["cx"] * W - 10, lots[i]["cy"] * H - 5), str(i), fill=(200, 0, 0, 255))
vis.crop((580, 495, 625, 525)).resize((900, 600), Image.NEAREST).save(
    "scratch/trace_362_below_411.png"
)

ov_path = Path("scratch/lot_plan_all_indices.png")
vis2 = Image.fromarray(rgb.copy()).convert("RGBA")
dr2 = ImageDraw.Draw(vis2, "RGBA")
for i, L in enumerate(lots):
    pts = L.get("points") or []
    if len(pts) < 3:
        continue
    xy2 = [(p[0] * W, p[1] * H) for p in pts]
    dr2.polygon(xy2, fill=(40, 120, 255, 120), outline=(0, 60, 180, 200))
    dr2.text((L["cx"] * W - 8, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis2.convert("RGB").save(ov_path)
print("done", IDX, lots[IDX])
