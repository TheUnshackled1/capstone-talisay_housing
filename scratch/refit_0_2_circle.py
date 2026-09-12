"""Refit lots 0 and 2: ink-edge quads with circle notch at (649, 16)."""
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
bak = Path("scratch/lot_plan_polygons_before_refit_0_2.json")
shutil.copy(POLY, bak)

data = json.loads(POLY.read_text(encoding="utf-8"))
lots = data["lots"]
rgb = np.array(Image.open(IMG).convert("RGB"))

CX, CY, R = 649.0, 16.0, 9.5


def r4(v: float) -> float:
    return round(float(v), 4)


def to_norm(xy: np.ndarray) -> list:
    return [[float(x / W), float(y / H)] for x, y in xy]


def arc_pts(a1: float, a2: float, steps: int = 4) -> list[np.ndarray]:
    da = a2 - a1
    while da > math.pi:
        da -= 2 * math.pi
    while da < -math.pi:
        da += 2 * math.pi
    if abs(da) > math.pi:
        da = da - 2 * math.pi if da > 0 else da + 2 * math.pi
    return [
        np.array([CX + R * math.cos(a1 + da * t), CY + R * math.sin(a1 + da * t)])
        for t in np.linspace(0, 1, steps)
    ]


def h_line_y(y: float, x_lo: float, x_hi: float) -> np.ndarray | None:
    d2 = R ** 2 - (y - CY) ** 2
    if d2 < 0:
        return None
    xs = [CX - math.sqrt(d2), CX + math.sqrt(d2)]
    xs = [x for x in xs if x_lo <= x <= x_hi]
    return np.array([min(xs), y]) if xs else None


def v_line_x(x: float, y_lo: float, y_hi: float) -> np.ndarray | None:
    d2 = R ** 2 - (x - CX) ** 2
    if d2 < 0:
        return None
    ys = [CY - math.sqrt(d2), CY + math.sqrt(d2)]
    ys = [y for y in ys if y_lo <= y <= y_hi]
    return np.array([x, min(ys)]) if ys else None


# Lot 0 ink rect: left=632.5 top=10.5 right=650.5 bottom=43.5
p0_top = h_line_y(10.5, 632.5, 650.5)          # (641.25, 10.5)
p0_right = v_line_x(650.5, 10.5, 43.5)         # (650.5, 25.38)
a1 = math.atan2(p0_top[1] - CY, p0_top[0] - CX)
a2 = math.atan2(p0_right[1] - CY, p0_right[0] - CX)
lot0 = np.array(
    [
        [632.5, 10.5],
        p0_top,
        *arc_pts(a1, a2, 4),
        p0_right,
        [650.5, 43.5],
        [632.5, 43.5],
    ],
    float,
)

# Lot 2 ink rect: left=652.5 top=13.5 right=672.5 bottom=45.5
p2_left = v_line_x(652.5, 13.5, 45.5)          # (652.5, 25.09)
p2_top = h_line_y(13.5, 652.5, 672.5)            # (658.17, 13.5)
b1 = math.atan2(p2_left[1] - CY, p2_left[0] - CX)
b2 = math.atan2(p2_top[1] - CY, p2_top[0] - CX)
lot2 = np.array(
    [
        p2_left,
        *arc_pts(b1, b2, 4),
        p2_top,
        [672.5, 13.5],
        [672.5, 45.5],
        [652.5, 45.5],
    ],
    float,
)

def dedupe(xy: np.ndarray, tol: float = 0.3) -> np.ndarray:
    out = []
    for p in xy:
        if not out or np.linalg.norm(p - out[-1]) > tol:
            out.append(p)
    return np.array(out)


for idx, xy in [(0, lot0), (2, lot2)]:
    xy = dedupe(xy)
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


def coverage(rr=7):
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
print("coverage r=7", cov)
assert cov[0] == 0 and cov[2] == 0
assert len(lots) == 420
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2), encoding="utf-8")

vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
dr.ellipse([CX - R, CY - R, CX + R, CY + R], outline=(255, 0, 0, 180), width=1)
for i in [0, 2]:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(30, 100, 255, 175), outline=(0, 40, 180, 255))
    for x, y in pts:
        dr.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(220, 0, 0, 255))
    dr.text((L["cx"] * W - 8, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis.crop((625, 0, 685, 55)).resize((700, 600), Image.NEAREST).save("scratch/fix_0_2_circle_cut.png")

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
