"""Trace and refit lots 0, 1, and 2 from ink flood contours; circle excluded on 0/2."""
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
POLY = Path("static/units/lot_plan_polygons.json")
IMG = Path("static/images/lot_plan_roads.png")
bak = Path("scratch/lot_plan_polygons_before_refit_0_1_2.json")
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


def flood_cell(seed_x: float, seed_y: float, roi: tuple[int, int, int, int], cut_circle: bool = False) -> np.ndarray:
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
    if cut_circle:
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


def snap_lot1(xy: np.ndarray) -> np.ndarray:
    out = []
    for x, y in xy:
        if x < 615:
            x = 613.5
        elif x > 629:
            x = 631.5
        if y < 14:
            y = 12.5
        elif y > 42:
            y = 43.5
        out.append([x, y])
    return np.array(out, float)


def snap_lot2(xy: np.ndarray) -> np.ndarray:
    out = []
    for x, y in xy:
        if x < 655 and y > 30:
            x = 652.5
        elif x < 655 and y < 30:
            pass
        elif x > 670:
            x = 672.5
        if y < 14.5 and x > 665:
            y = 13.5
        elif y < 14.5 and x < 660:
            y = 13.5
        if y > 43 and x > 665:
            y = 44.5
        elif y > 41 and x < 655:
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


def merge_targets(targets: np.ndarray, raw: np.ndarray) -> np.ndarray:
    out = targets.copy()
    for i, target in enumerate(out):
        for p in raw:
            if np.linalg.norm(p - target) < 2.5:
                out[i] = p
                break
    return dedupe(out)


raw0 = snap_lot0(extract_polygon(flood_cell(640, 28, (632, 8, 652, 48), True)))
raw1 = snap_lot1(extract_polygon(flood_cell(620, 28, (610, 8, 632, 48), False)))
raw2 = snap_lot2(extract_polygon(flood_cell(666, 28, (652, 8, 676, 48), True)))

lot0 = merge_targets(
    np.array(
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
    ),
    raw0,
)

# lot 1: clockwise TL -> TR -> BR -> BL (angled bottom follows curved ink road)
lot1 = merge_targets(
    np.array(
        [
            [613.5, 14.0],
            [631.5, 12.5],
            [631.5, 42.5],
            [618.0, 43.5],
        ],
        float,
    ),
    raw1,
)

lot2 = merge_targets(
    np.array(
        [
            [658.0, 13.5],
            [672.5, 13.5],
            [672.5, 44.5],
            [652.5, 42.5],
            [652.5, 37.0],
            [660.0, 31.0],
            [660.0, 24.0],
            [656.0, 22.0],
        ],
        float,
    ),
    raw2,
)

for idx, xy in [(0, lot0), (1, lot1), (2, lot2)]:
    lots[idx] = {
        "points": to_norm(xy),
        "cx": r4(xy[:, 0].mean() / W),
        "cy": r4(xy[:, 1].mean() / H),
        "area": r4(abs(float(cv2.contourArea(xy.astype(np.float32)))) / (W * H)),
    }
    print(idx, [(round(x, 1), round(y, 1)) for x, y in xy])


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


def coverage(rr=6):
    cov = {0: 0, 2: 0}
    for y in range(int(CY - rr), int(CY + rr) + 1):
        for x in range(int(CX - rr), int(CX + rr) + 1):
            if (x - CX) ** 2 + (y - CY) ** 2 > rr * rr:
                continue
            for i in [0, 2]:
                if point_in_poly(x + 0.5, y + 0.5, to_xy(lots[i]["points"])):
                    cov[i] += 1
    return cov


cov = coverage()
print("coverage r=6", cov)
assert cov[0] == 0 and cov[2] == 0
assert len(lots) == 420
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2), encoding="utf-8")

vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
dr.ellipse([CX - R, CY - R, CX + R, CY + R], outline=(255, 0, 0, 140), width=1)
for i in [0, 1, 2]:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(30, 100, 255, 175), outline=(0, 40, 180, 255))
    for x, y in pts:
        dr.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(220, 0, 0, 255))
    dr.text((L["cx"] * W - 8, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis.crop((600, 0, 685, 55)).resize((750, 600), Image.NEAREST).save("scratch/fix_0_1_2_trace.png")

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
