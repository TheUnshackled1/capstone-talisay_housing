"""Refit lots 0 and 2 to ink cells; cut shared circle at ~(653, 24)."""
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
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

ink = (gray < 95).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
fillable = ((gray >= 145) & (gray <= 210)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(ink))

CX, CY, R = 653.0, 24.0, 9.0


def r4(v: float) -> float:
    return round(float(v), 4)


def to_norm(xy: np.ndarray) -> list:
    return [[float(x / W), float(y / H)] for x, y in xy]


def flood_roi(seed_x: float, seed_y: float, roi: tuple[int, int, int, int], shrink: float = 0.92):
    x0, y0, x1, y1 = roi
    roi_m = np.zeros((H, W), np.uint8)
    roi_m[y0:y1, x0:x1] = 255
    region = cv2.bitwise_and(fillable, roi_m)
    ix, iy = int(round(seed_x)), int(round(seed_y))
    if region[iy, ix] == 0:
        found = False
        for rad in range(1, 14):
            for dy in range(-rad, rad + 1):
                for dx in range(-rad, rad + 1):
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
    allow = cv2.bitwise_and(roi_m, cv2.bitwise_not(hard))
    for _ in range(2):
        cell = cv2.bitwise_and(cv2.dilate(cell, np.ones((3, 3), np.uint8), 1), allow)
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    box = cv2.boxPoints(cv2.minAreaRect(cnt)).astype(float)
    c = box.mean(axis=0)
    box = c + (box - c) * shrink
    angs = np.arctan2(box[:, 1] - c[1], box[:, 0] - c[0])
    box = box[np.argsort(angs)]
    area = abs(float(cv2.contourArea(box.astype(np.float32))))
    if area < 80:
        return None
    return box, c, area


left = flood_roi(640, 28, (632, 10, 653, 44))
right = flood_roi(664, 28, (652, 10, 674, 48))
assert left is not None and right is not None, "flood failed"

lots[0] = {
    "points": to_norm(left[0]),
    "cx": r4(left[1][0] / W),
    "cy": r4(left[1][1] / H),
    "area": r4(left[2] / (W * H)),
}
lots[2] = {
    "points": to_norm(right[0]),
    "cx": r4(right[1][0] / W),
    "cy": r4(right[1][1] / H),
    "area": r4(right[2] / (W * H)),
}


def to_xy(pts):
    return np.array([[p[0] * W, p[1] * H] for p in pts], float)


def norm_ang(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def cut_shared(xy: np.ndarray, is_left: bool) -> np.ndarray:
    n = len(xy)
    cen = xy.mean(axis=0)
    best_e, best_s = None, 1e9
    for j in range(n):
        a, b = xy[j], xy[(j + 1) % n]
        mid = (a + b) / 2
        d = np.linalg.norm(mid - [CX, CY])
        if is_left and mid[0] < CX - 2:
            continue
        if not is_left and mid[0] > CX + 2:
            continue
        if d < best_s:
            best_s = d
            best_e = j
    assert best_e is not None
    v_a, v_b = xy[best_e], xy[(best_e + 1) % n]
    a1 = math.atan2(v_a[1] - CY, v_a[0] - CX)
    a2 = math.atan2(v_b[1] - CY, v_b[0] - CX)
    da = norm_ang(a2 - a1)
    d_other = da - 2 * math.pi if da > 0 else da + 2 * math.pi

    def arc(d, steps=3):
        return [
            np.array([CX + R * math.cos(a1 + d * t), CY + R * math.sin(a1 + d * t)])
            for t in np.linspace(0, 1, steps)
        ]

    short, longg = arc(da), arc(d_other, 5)

    def mid(a):
        return a[len(a) // 2]

    chosen = short if np.linalg.norm(mid(short) - cen) <= np.linalg.norm(mid(longg) - cen) else longg
    out = []
    for j in range(n):
        if j == best_e:
            out.extend(chosen)
        elif j == (best_e + 1) % n:
            continue
        else:
            out.append(xy[j])
    xy2 = np.array(out)
    for k, p in enumerate(xy2):
        d = np.linalg.norm(p - [CX, CY])
        if d < R:
            xy2[k] = np.array([CX, CY]) + (p - np.array([CX, CY])) / max(d, 1e-6) * R
    return xy2


def point_in_poly(x, y, poly):
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def coverage(rr=6):
    ys, xs = np.mgrid[int(CY - rr) : int(CY + rr) + 1, int(CX - rr) : int(CX + rr) + 1]
    cov = {0: 0, 2: 0}
    for y, x in zip(ys.ravel(), xs.ravel()):
        if (x - CX) ** 2 + (y - CY) ** 2 > rr * rr:
            continue
        for i in [0, 2]:
            if point_in_poly(x + 0.5, y + 0.5, to_xy(lots[i]["points"])):
                cov[i] += 1
    return cov


def push_clear(xy: np.ndarray) -> np.ndarray:
    xy2 = xy.copy()
    for k, p in enumerate(xy2):
        d = np.linalg.norm(p - [CX, CY])
        if d < R:
            xy2[k] = np.array([CX, CY]) + (p - np.array([CX, CY])) / max(d, 1e-6) * R
    out = []
    n = len(xy2)
    for j in range(n):
        a, b = xy2[j], xy2[(j + 1) % n]
        out.append(a)
        mid = (a + b) / 2
        if np.linalg.norm(mid - [CX, CY]) < R:
            v = mid - np.array([CX, CY])
            d = np.linalg.norm(v)
            if d < 1e-6:
                v = xy2.mean(axis=0) - np.array([CX, CY])
                d = np.linalg.norm(v)
            out.append(np.array([CX, CY]) + v / max(d, 1e-6) * R)
    xy2 = np.array(out)
    for k, p in enumerate(xy2):
        d = np.linalg.norm(p - [CX, CY])
        if d < R:
            xy2[k] = np.array([CX, CY]) + (p - np.array([CX, CY])) / max(d, 1e-6) * R
    return xy2


for i, is_left in [(0, True), (2, False)]:
    xy2 = cut_shared(to_xy(lots[i]["points"]), is_left)
    xy2 = push_clear(xy2)
    lots[i]["points"] = to_norm(xy2)
    lots[i]["cx"] = r4(xy2[:, 0].mean() / W)
    lots[i]["cy"] = r4(xy2[:, 1].mean() / H)
    print(i, [(round(x, 1), round(y, 1)) for x, y in xy2])

cov = coverage()
print("coverage", cov)
assert cov[0] == 0 and cov[2] == 0
assert len(lots) == 420
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2), encoding="utf-8")

vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
dr.ellipse([CX - 6, CY - 6, CX + 6, CY + 6], outline=(255, 0, 0, 140), width=1)
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
