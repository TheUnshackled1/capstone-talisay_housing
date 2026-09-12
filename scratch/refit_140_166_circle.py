"""Refit lots 140 and 166 — ink flood + circle excluded on left junction."""
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
IDS = [140, 166]
POLY = Path("static/units/lot_plan_polygons.json")
IMG = Path("static/images/lot_plan_roads.png")
bak = Path("scratch/lot_plan_polygons_before_refit_140_166.json")
shutil.copy(POLY, bak)

data = json.loads(POLY.read_text(encoding="utf-8"))
lots = data["lots"]
rgb = np.array(Image.open(IMG).convert("RGB"))
gray = np.array(Image.open(IMG).convert("L"), float)

ink = (gray < 95).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
fillable = ((gray >= 145) & (gray <= 210)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(ink))

# Aligned to gray sketch circle on left junction (see scratch/inspect_140_166.png).
CX, CY, R = 41.0, 193.0, 4.5
R_ARC = R + 0.55
print("circle", CX, CY, "R", R)

LOTS = {
    140: {"seed": (45, 188), "roi": (28, 172, 60, 204)},
    166: {"seed": (42, 212), "roi": (24, 195, 58, 226)},
}


def r4(v: float) -> float:
    return round(float(v), 4)


def to_norm(xy: np.ndarray) -> list:
    return [[float(x / W), float(y / H)] for x, y in xy]


def flood_cell(seed: tuple[int, int], roi: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = roi
    roi_m = np.zeros((H, W), np.uint8)
    roi_m[y0:y1, x0:x1] = 255
    region = cv2.bitwise_and(fillable, roi_m)
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = region.copy()
    cv2.floodFill(flood, mask, seed, 200)
    cell = (flood == 200).astype(np.uint8) * 255
    hard = (gray < 55).astype(np.uint8) * 255
    allow = cv2.bitwise_and(roi_m, cv2.bitwise_not(hard))
    for _ in range(2):
        cell = cv2.bitwise_and(cv2.dilate(cell, np.ones((3, 3), np.uint8), 1), allow)
    yy, xx = np.mgrid[0:H, 0:W]
    cell[((xx - CX) ** 2 + (yy - CY) ** 2) <= R ** 2] = 0
    return cell


def ink_bbox(cell: np.ndarray) -> tuple[float, float, float, float]:
    ys, xs = np.where(cell)
    return float(xs.min()) + 0.5, float(ys.min()) + 0.5, float(xs.max()) + 0.5, float(ys.max()) + 0.5


def norm_ang(a: float) -> float:
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def point_in_poly(x: float, y: float, poly: np.ndarray) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def bevel_inner(xy: np.ndarray) -> np.ndarray:
    n = len(xy)
    lot_centroid = xy.mean(axis=0)
    dists = [np.linalg.norm(p - [CX, CY]) for p in xy]
    idx = int(np.argmin(dists))
    v = xy[idx]
    prev = xy[(idx - 1) % n]
    nxt = xy[(idx + 1) % n]
    t1 = 0.42
    p1 = v + t1 * (prev - v)
    p2 = v + t1 * (nxt - v)
    a1 = math.atan2(p1[1] - CY, p1[0] - CX)
    a2 = math.atan2(p2[1] - CY, p2[0] - CX)
    da_short = norm_ang(a2 - a1)
    da_long = da_short + (2 * math.pi if da_short < 0 else -2 * math.pi)
    arc = None
    for da in (da_short, da_long):
        cand = [
            np.array([CX + R_ARC * math.cos(a1 + da * t), CY + R_ARC * math.sin(a1 + da * t)])
            for t in np.linspace(0, 1, 7)
        ]
        mid = cand[len(cand) // 2]
        toward_lot = lot_centroid - np.array([CX, CY])
        if np.dot(mid - np.array([CX, CY]), toward_lot) > 0:
            arc = cand
            break
    if arc is None:
        arc = [
            np.array([CX + R_ARC * math.cos(a1 + da_short * t), CY + R_ARC * math.sin(a1 + da_short * t)])
            for t in np.linspace(0, 1, 5)
        ]
    out = []
    for i in range(n):
        if i == idx:
            out.extend(arc)
        else:
            out.append(xy[i])
    xy2 = np.array(out)
    for k, p in enumerate(xy2):
        d = np.linalg.norm(p - [CX, CY])
        if d < R_ARC:
            xy2[k] = np.array([CX, CY]) + (p - np.array([CX, CY])) / max(d, 1e-6) * R_ARC
    return xy2


def merge_raw(xy: np.ndarray, raw: np.ndarray) -> np.ndarray:
    out = xy.copy()
    for i, target in enumerate(out):
        for p in raw:
            if np.linalg.norm(p - target) < 4.0:
                out[i] = p
                break
    return out


def extract_raw(seed: tuple[int, int], roi: tuple[int, int, int, int]) -> np.ndarray:
    cell = flood_cell(seed, roi)
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnt = max(cnts, key=cv2.contourArea).astype(np.float32)
    peri = cv2.arcLength(cnt, True)
    return cv2.approxPolyDP(cnt, 0.018 * peri, True).reshape(-1, 2).astype(float)


for idx in IDS:
    cfg = LOTS[idx]
    cell = flood_cell(cfg["seed"], cfg["roi"])
    x0, y0, x1, y1 = ink_bbox(cell)
    raw = extract_raw(cfg["seed"], cfg["roi"])
    xy = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)
    xy = merge_raw(xy, raw)
    xy = bevel_inner(xy)
    lots[idx] = {
        "points": to_norm(xy),
        "cx": r4(xy[:, 0].mean() / W),
        "cy": r4(xy[:, 1].mean() / H),
        "area": r4(abs(float(cv2.contourArea(xy.astype(np.float32)))) / (W * H)),
    }
    print(idx, [(round(x, 1), round(y, 1)) for x, y in xy])


def to_xy(pts):
    return np.array([[p[0] * W, p[1] * H] for p in pts], float)


cov = {i: 0 for i in IDS}
for y in range(int(CY - 8), int(CY + 8) + 1):
    for x in range(int(CX - 8), int(CX + 8) + 1):
        px, py = x + 0.5, y + 0.5
        if (px - CX) ** 2 + (py - CY) ** 2 > R ** 2:
            continue
        for i in IDS:
            if point_in_poly(px, py, to_xy(lots[i]["points"])):
                cov[i] += 1
print("verify cov inside R", cov)
assert all(v == 0 for v in cov.values())
assert len(lots) == 420
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2), encoding="utf-8")

vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
dr.ellipse([CX - R, CY - R, CX + R, CY + R], outline=(0, 220, 0, 220), width=2)
for i in IDS:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(30, 100, 255, 175), outline=(0, 40, 180, 255))
    for x, y in pts:
        dr.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(220, 0, 0, 255))
    dr.text((L["cx"] * W - 12, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis.crop((20, 165, 70, 235)).resize((900, 1000), Image.NEAREST).save(
    "scratch/fix_140_166_circle.png"
)

insp = Image.fromarray(rgb.copy()).convert("RGBA")
idr = ImageDraw.Draw(insp, "RGBA")
idr.ellipse([CX - R, CY - R, CX + R, CY + R], outline=(0, 220, 0, 255), width=2)
for i in IDS:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    idr.rectangle([min(xs), min(ys), max(xs), max(ys)], outline=(220, 0, 0, 255), width=2)
insp.crop((28, 168, 58, 230)).resize((900, 1200), Image.NEAREST).save(
    "scratch/inspect_140_166.png"
)

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
