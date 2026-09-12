"""Retrace lot 362 — wedge below 411, label inside polygon."""
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


def r4(v: float) -> float:
    return round(float(v), 4)


def to_norm(xy_arr: np.ndarray) -> list:
    return [[float(x / W), float(y / H)] for x, y in xy_arr]


def nudge_below_411(xy: np.ndarray, m411: np.ndarray) -> np.ndarray:
    """Shift top vertices down until fillPoly has zero overlap with 411."""
    xy = xy.copy()
    for _ in range(30):
        m = np.zeros((H, W), np.uint8)
        cv2.fillPoly(m, [xy.astype(np.int32)], 1)
        if int((m & (m411 // 255)).sum()) == 0:
            return xy
        top_y = xy[:, 1].min()
        for i in range(len(xy)):
            if xy[i, 1] <= top_y + 0.8:
                xy[i, 1] += 0.5
    return xy


ink = (gray < 70).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
fillable = ((gray >= 145) & (gray <= 210)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(ink))
blocked = cv2.bitwise_or(ink, mask_of_lot(411))
allow = cv2.bitwise_and(cv2.bitwise_not(blocked), fillable)

ROI = (585, 507, 622, 522)
SEED = (598, 512)
x0, y0, x1, y1 = ROI
roi_m = np.zeros((H, W), np.uint8)
roi_m[y0:y1, x0:x1] = 255
region = cv2.bitwise_and(allow, roi_m)
mask = np.zeros((H + 2, W + 2), np.uint8)
flood = region.copy()
cv2.floodFill(flood, mask, SEED, 200)
comp = (flood == 200).astype(np.uint8) * 255
comp = cv2.bitwise_and(comp, cv2.bitwise_not(mask_of_lot(411)))

flood_px = int(comp.sum() // 255)
assert flood_px > 50, f"flood region too small: {flood_px}px"
mom = cv2.moments(comp)
label_cx = mom["m10"] / mom["m00"]
label_cy = mom["m01"] / mom["m00"]

cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
cnt = max(cnts, key=cv2.contourArea)
peri = cv2.arcLength(cnt, True)
xy = cv2.approxPolyDP(cnt, 0.025 * peri, True).reshape(-1, 2).astype(float) + 0.5
xy = nudge_below_411(xy, mask_of_lot(411))

area_px = abs(float(cv2.contourArea(xy.astype(np.float32))))
print("npts", len(xy), "area_px", round(area_px, 1))
print("label", round(label_cx, 1), round(label_cy, 1))
print("pts", [(round(x, 1), round(y, 1)) for x, y in xy])

m_new = np.zeros((H, W), np.uint8)
cv2.fillPoly(m_new, [xy.astype(np.int32)], 255)
ov = int((m_new // 255 & mask_of_lot(411) // 255).sum())
print("overlap with 411 px", ov)
assert ov == 0
assert 150 < area_px < 350

lots[IDX] = {
    "points": to_norm(xy),
    "cx": r4(label_cx / W),
    "cy": r4(label_cy / H),
    "area": r4(area_px / (W * H)),
}
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2), encoding="utf-8")

vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
for i in [411, IDX]:
    pts = [(p[0] * W, p[1] * H) for p in lots[i]["points"]]
    col = (30, 100, 255, 170) if i == IDX else (255, 120, 30, 120)
    dr.polygon(pts, fill=col, outline=(0, 40, 180, 255))
    dr.text(
        (lots[i]["cx"] * W - 10, lots[i]["cy"] * H - 5),
        str(i),
        fill=(200, 0, 0, 255),
    )
vis.crop((580, 495, 630, 525)).resize((1000, 600), Image.NEAREST).save(
    "scratch/fix_362_overlap.png"
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
