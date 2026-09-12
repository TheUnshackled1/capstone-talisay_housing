"""Refit lot 0 only from ink flood contour; circle excluded. Preserve lot 2."""
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
POLY = Path("static/units/lot_plan_polygons.json")
IMG = Path("static/images/lot_plan_roads.png")
bak = Path("scratch/lot_plan_polygons_before_refit_lot0.json")
shutil.copy(POLY, bak)

data = json.loads(POLY.read_text(encoding="utf-8"))
lots = data["lots"]
rgb = np.array(Image.open(IMG).convert("RGB"))
gray = np.array(Image.open(IMG).convert("L"))

ink = (gray < 95).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
fillable = ((gray >= 145) & (gray <= 210)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(ink))

CX, CY, R = 649.0, 16.0, 9.0


def r4(v: float) -> float:
    return round(float(v), 4)


def to_norm(xy: np.ndarray) -> list:
    return [[float(x / W), float(y / H)] for x, y in xy]


def flood_cell(seed_x: float, seed_y: float, roi: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = roi
    roi_m = np.zeros((H, W), np.uint8)
    roi_m[y0:y1, x0:x1] = 255
    region = cv2.bitwise_and(fillable, roi_m)
    ix, iy = int(round(seed_x)), int(round(seed_y))
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = region.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    hard = (gray < 55).astype(np.uint8) * 255
    allow = cv2.bitwise_and(roi_m, cv2.bitwise_not(hard))
    for _ in range(2):
        cell = cv2.bitwise_and(cv2.dilate(cell, np.ones((3, 3), np.uint8), 1), allow)
    yy, xx = np.mgrid[0:H, 0:W]
    cell[((xx - CX) ** 2 + (yy - CY) ** 2) <= R ** 2] = 0
    return cell


def extract_polygon(cell: np.ndarray, eps: float = 0.015) -> np.ndarray:
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea).astype(np.float32)
    peri = cv2.arcLength(cnt, True)
    return cv2.approxPolyDP(cnt, eps * peri, True).reshape(-1, 2).astype(float)


def snap_lot0(xy: np.ndarray) -> np.ndarray:
    out = []
    for x, y in xy:
        if x < 634:
            x = 632.5
        elif x > 646 and y < 30:
            pass
        elif x > 646:
            x = 650.5
        if y < 12.5:
            y = 10.5
        elif y > 41:
            y = 42.5
        out.append([x, y])
    return np.array(out, float)


def dedupe(xy: np.ndarray, tol: float = 0.35) -> np.ndarray:
    out = []
    for p in xy:
        if not out or np.linalg.norm(p - out[-1]) > tol:
            out.append(p)
    if len(out) > 1 and np.linalg.norm(out[0] - out[-1]) <= tol:
        out.pop()
    return np.array(out)


cell0 = flood_cell(640, 28, (632, 8, 652, 48))
raw = snap_lot0(extract_polygon(cell0))
# clockwise from top-left: top -> notch -> right -> bottom -> left
lot0 = np.array(
    [
        [632.5, 10.5],
        [641.0, 10.5],
        [639.0, 16.0],
        [644.0, 24.0],
        [645.0, 33.0],
        [650.5, 34.0],
        [650.5, 42.5],
        [632.5, 42.5],
    ],
    float,
)
# pull notch/edge points from raw if present
for i, target in enumerate(lot0):
    for p in raw:
        if np.linalg.norm(p - target) < 2.5:
            lot0[i] = p
            break
lot0 = dedupe(lot0)

lots[0] = {
    "points": to_norm(lot0),
    "cx": r4(lot0[:, 0].mean() / W),
    "cy": r4(lot0[:, 1].mean() / H),
    "area": r4(abs(float(cv2.contourArea(lot0.astype(np.float32)))) / (W * H)),
}
print("0", [(round(x, 1), round(y, 1)) for x, y in lot0])


def to_xy(pts):
    return np.array([[p[0] * W, p[1] * H] for p in pts], float)


def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


cov = 0
for y in range(int(CY - 6), int(CY + 6) + 1):
    for x in range(int(CX - 6), int(CX + 6) + 1):
        if (x - CX) ** 2 + (y - CY) ** 2 > 36:
            continue
        if point_in_poly(x + 0.5, y + 0.5, to_xy(lots[0]["points"])):
            cov += 1
print("circle coverage", cov)
assert cov == 0
assert len(lots) == 420
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2), encoding="utf-8")

vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
dr.ellipse([CX - R, CY - R, CX + R, CY + R], outline=(255, 0, 0, 140), width=1)
for i in [0, 2]:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(30, 100, 255, 175), outline=(0, 40, 180, 255))
    for x, y in pts:
        dr.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(220, 0, 0, 255))
    dr.text((L["cx"] * W - 8, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis.crop((625, 0, 685, 55)).resize((700, 600), Image.NEAREST).save("scratch/fix_0_circle_cut.png")

ov = Path("scratch/lot_plan_all_indices.png")
vis2 = Image.fromarray(rgb.copy()).convert("RGBA")
dr2 = ImageDraw.Draw(vis2, "RGBA")
for i, L in enumerate(lots):
    pts = L.get("points") or []
    if len(pts) < 3:
        continue
    xy = [(p[0] * W, p[1] * H) for p in pts]
    dr2.polygon(xy, fill=(40, 120, 255, 120), outline=(0, 60, 180, 200))
    dr2.text((L["cx"] * W - 8, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis2.convert("RGB").save(ov)
print("done")
