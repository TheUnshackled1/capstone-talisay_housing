import json, shutil, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
IDS = [117, 125, 141, 151]
POLY = Path("static/units/lot_plan_polygons.json")
bak = Path("scratch/lot_plan_polygons_before_circle_cut_117.json")
shutil.copy(POLY, bak)
data = json.loads(POLY.read_text())
lots = data["lots"]

gray = np.array(Image.open("static/images/lot_plan_roads.png").convert("L"), float)


def to_xy(pts):
    return np.array([[p[0] * W, p[1] * H] for p in pts], float)


def to_norm(xy):
    return [[float(x / W), float(y / H)] for x, y in xy]


allp = []
for i in IDS:
    xy = to_xy(lots[i]["points"])
    print(i, "n", len(xy), [(round(x, 1), round(y, 1)) for x, y in xy])
    allp.append(xy)
allp = np.vstack(allp)
cen0 = allp.mean(axis=0)
inners = []
for i in IDS:
    xy = to_xy(lots[i]["points"])
    d = np.linalg.norm(xy - cen0, axis=1)
    inners.append(xy[int(np.argmin(d))])
inners = np.array(inners)
CX0, CY0 = inners.mean(axis=0)
print("inner corners mean", CX0, CY0)

best = None
cx0, cy0 = int(round(CX0)), int(round(CY0))
for cy in range(cy0 - 8, cy0 + 9):
    for cx in range(cx0 - 8, cx0 + 9):
        if cy < 3 or cx < 3 or cy >= H - 3 or cx >= W - 3:
            continue
        ang = np.linspace(0, 2 * np.pi, 48, endpoint=False)
        ring = np.array(
            [gray[int(cy + 6 * np.sin(a)), int(cx + 6 * np.cos(a))] for a in ang]
        ).mean()
        core = gray[cy - 2 : cy + 3, cx - 2 : cx + 3].mean()
        score = core - ring
        if best is None or score > best[0]:
            best = (score, cx, cy, core, ring)
print("best circle", best)
CX, CY = float(best[1]), float(best[2])
R = 8.5


def point_in_poly(x, y, poly):
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def coverage(rr):
    ys, xs = np.mgrid[int(CY - rr) : int(CY + rr) + 1, int(CX - rr) : int(CX + rr) + 1]
    cov = {i: 0 for i in IDS}
    total = 0
    for y, x in zip(ys.ravel(), xs.ravel()):
        if (x - CX) ** 2 + (y - CY) ** 2 > rr * rr:
            continue
        total += 1
        for i in IDS:
            xy = to_xy(lots[i]["points"])
            if point_in_poly(x + 0.5, y + 0.5, xy):
                cov[i] += 1
    return total, cov


def norm_ang(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def bevel_inner(xy):
    n = len(xy)
    dists = [np.linalg.norm(p - [CX, CY]) for p in xy]
    idx = int(np.argmin(dists))
    v = xy[idx]
    prev = xy[(idx - 1) % n]
    nxt = xy[(idx + 1) % n]
    t1 = 0.4
    p1 = v + t1 * (prev - v)
    p2 = v + t1 * (nxt - v)
    a1 = math.atan2(p1[1] - CY, p1[0] - CX)
    a2 = math.atan2(p2[1] - CY, p2[0] - CX)
    da = norm_ang(a2 - a1)
    pts_new = [
        np.array([CX + R * math.cos(a1 + da * t), CY + R * math.sin(a1 + da * t)])
        for t in (0.0, 0.5, 1.0)
    ]
    out = []
    for i in range(n):
        if i == idx:
            out.extend(pts_new)
        else:
            out.append(xy[i])
    return np.array(out)


print("BEFORE inkRing6", coverage(6))
print("BEFORE clearR", coverage(R))

for i in IDS:
    xy = to_xy(lots[i]["points"])
    xy2 = bevel_inner(xy)
    for k, p in enumerate(xy2):
        d = np.linalg.norm(p - [CX, CY])
        if d < R:
            xy2[k] = np.array([CX, CY]) + (p - np.array([CX, CY])) / max(d, 1e-6) * R
    print(i, "after", [(round(x, 1), round(y, 1)) for x, y in xy2])
    lots[i]["points"] = to_norm(xy2)
    lots[i]["cx"] = float(xy2[:, 0].mean() / W)
    lots[i]["cy"] = float(xy2[:, 1].mean() / H)

print("AFTER inkRing6", coverage(6))
print("AFTER clearR", coverage(R))

assert len(lots) == 420
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2))

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
dr.ellipse([CX - 6, CY - 6, CX + 6, CY + 6], outline=(255, 0, 0, 140), width=1)
for i in IDS:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(30, 100, 255, 175), outline=(0, 40, 180, 255))
    for x, y in pts:
        dr.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(220, 0, 0, 255))
    dr.text((L["cx"] * W - 10, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis.crop((int(CX) - 45, int(CY) - 40, int(CX) + 45, int(CY) + 40)).resize(
    (700, 650), Image.NEAREST
).save("scratch/fix_117_circle_cut.png")
print("CXCY", CX, CY, "saved QA")

ov = Path("scratch/lot_plan_all_indices.png")
vis2 = Image.fromarray(rgb.copy()).convert("RGBA")
dr2 = ImageDraw.Draw(vis2, "RGBA")
empty = []
for i, L in enumerate(lots):
    pts = L.get("points") or []
    if len(pts) < 3:
        empty.append(i)
        continue
    xy = [(p[0] * W, p[1] * H) for p in pts]
    dr2.polygon(xy, fill=(40, 120, 255, 120), outline=(0, 60, 180, 200))
    dr2.text((L["cx"] * W - 8, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis2.convert("RGB").save(ov)
print("overview regenerated, empty", empty)
