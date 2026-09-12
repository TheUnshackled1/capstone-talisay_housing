"""Trace and refit lots 0 and 2 — exclude mid-divider sketch circle."""
import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
IDS = [0, 2]
POLY = Path("static/units/lot_plan_polygons.json")
IMG = Path("static/images/lot_plan_roads.png")
bak = Path("scratch/lot_plan_polygons_before_refit_0_2.json")
shutil.copy(POLY, bak)

data = json.loads(POLY.read_text(encoding="utf-8"))
lots = data["lots"]
rgb = np.array(Image.open(IMG).convert("RGB"))
gray = np.array(Image.open(IMG).convert("L"), float)

ink = (gray < 95).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
fillable = ((gray >= 145) & (gray <= 210)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(ink))

best = None
for r_try in (6.0, 6.5, 7.0, 7.5, 8.0):
    for cy in range(24, 33):
        for cx in range(649, 656):
            ang = np.linspace(0, 2 * math.pi, 48, endpoint=False)
            ring = np.array(
                [
                    gray[
                        min(H - 1, max(0, int(cy + r_try * math.sin(a)))),
                        min(W - 1, max(0, int(cx + r_try * math.cos(a)))),
                    ]
                    for a in ang
                ]
            )
            ring_m = float(ring.mean())
            core = float(gray[cy, cx])
            if ring_m > 105 or core < 150:
                continue
            score = core - ring_m
            if best is None or score > best[0]:
                best = (score, cx, cy, r_try)
CX, CY, R = float(best[1]), float(best[2]), float(best[3])
R_ARC = R + 0.35
print("circle", CX, CY, "R", R, "R_ARC", R_ARC, "score", round(best[0], 1))

LOTS = {
    0: {"seed": (640, 28), "roi": (632, 8, 652, 48), "side": "left"},
    2: {"seed": (666, 28), "roi": (652, 8, 676, 48), "side": "right"},
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


def arc_pts(a1: float, a2: float, n: int = 8) -> list[np.ndarray]:
    if a2 < a1:
        a2 += 2 * math.pi
    return [
        np.array([CX + R_ARC * math.cos(a), CY + R_ARC * math.sin(a)])
        for a in np.linspace(a1, a2, n)
    ]


def arc_pts_cw(a1: float, a2: float, n: int = 8) -> list[np.ndarray]:
    if a2 > a1:
        a2 -= 2 * math.pi
    return [
        np.array([CX + R_ARC * math.cos(a), CY + R_ARC * math.sin(a)])
        for a in np.linspace(a1, a2, n)
    ]


def push_out(xy: np.ndarray) -> np.ndarray:
    out: list[np.ndarray] = []
    n = len(xy)
    for j in range(n):
        a, b = xy[j], xy[(j + 1) % n]
        out.append(a)
        mid = a * 0.5 + b * 0.5
        d = np.linalg.norm(mid - [CX, CY])
        if d < R:
            v = mid - np.array([CX, CY])
            out.append(np.array([CX, CY]) + v / np.linalg.norm(v) * R_ARC)
    xy2 = np.array(out)
    for k, p in enumerate(xy2):
        d = np.linalg.norm(p - [CX, CY])
        if d < R:
            xy2[k] = np.array([CX, CY]) + (p - np.array([CX, CY])) / max(d, 1e-6) * R_ARC
    return xy2


def polygon_for(side: str, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    """CW polygon — straight outer edges, circle cutout on shared divider."""
    a_top = -math.pi / 2
    a_bot = math.pi / 2

    if side == "left":
        pts: list[np.ndarray] = [
            np.array([x0, y0]),
            np.array([CX, y0]),
            np.array([CX, CY - R_ARC]),
        ]
        pts.extend(arc_pts_cw(a_top, a_bot)[1:])
        pts.append(np.array([CX, y1]))
        pts.append(np.array([x0, y1]))
    else:
        pts = [
            np.array([x1, y0]),
            np.array([CX, y0]),
            np.array([CX, CY - R_ARC]),
        ]
        pts.extend(arc_pts(a_top, a_bot)[1:])
        pts.append(np.array([CX, y1]))
        pts.append(np.array([x1, y1]))
    return np.array(pts, float)


def dedupe(xy: np.ndarray, tol: float = 0.35) -> np.ndarray:
    out: list[np.ndarray] = []
    for p in xy:
        if not out or np.linalg.norm(p - out[-1]) > tol:
            out.append(p)
    if len(out) > 1 and np.linalg.norm(out[0] - out[-1]) <= tol:
        out.pop()
    return np.array(out)


for idx in IDS:
    cfg = LOTS[idx]
    cell = flood_cell(cfg["seed"], cfg["roi"])
    x0, y0, x1, y1 = ink_bbox(cell)
    xy = dedupe(push_out(polygon_for(cfg["side"], x0, y0, x1, y1)))
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


def verify():
    cov = {i: 0 for i in IDS}
    edge_hits = {i: 0 for i in IDS}
    for y in range(int(CY - 12), int(CY + 12) + 1):
        for x in range(int(CX - 12), int(CX + 12) + 1):
            px, py = x + 0.5, y + 0.5
            if (px - CX) ** 2 + (py - CY) ** 2 > R ** 2:
                continue
            for i in IDS:
                if point_in_poly(px, py, to_xy(lots[i]["points"])):
                    cov[i] += 1
    for i in IDS:
        pts = to_xy(lots[i]["points"])
        n = len(pts)
        for j in range(n):
            a, b = pts[j], pts[(j + 1) % n]
            for t in np.linspace(0, 1, 24):
                p = a * (1 - t) + b * t
                if (p[0] - CX) ** 2 + (p[1] - CY) ** 2 < (R - 0.3) ** 2:
                    edge_hits[i] += 1
    print("verify cov inside R", cov, "edge_hits", edge_hits)
    assert all(v == 0 for v in cov.values())
    assert all(v == 0 for v in edge_hits.values())


verify()
assert len(lots) == 420
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2), encoding="utf-8")

vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
dr.ellipse([CX - R, CY - R, CX + R, CY + R], outline=(0, 220, 0, 230), width=2)
for i in IDS:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(30, 100, 255, 175), outline=(0, 40, 180, 255))
    for x, y in pts:
        dr.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(220, 0, 0, 255))
    dr.text((L["cx"] * W - 8, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis.crop((625, 8, 685, 50)).resize((900, 840), Image.NEAREST).save("scratch/fix_0_2_circle_cut.png")

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
