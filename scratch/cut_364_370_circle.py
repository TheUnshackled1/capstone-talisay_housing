import json, shutil, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
POLY = Path("static/units/lot_plan_polygons.json")
bak = Path("scratch/lot_plan_polygons_before_circle_cut_364.json")
shutil.copy(POLY, bak)
data = json.loads(POLY.read_text())
lots = data["lots"]

gray = np.array(Image.open("static/images/lot_plan_roads.png").convert("L"), float)
best = None
for cy in range(405, 418):
    for cx in range(156, 168):
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


def to_xy(pts):
    return np.array([[p[0] * W, p[1] * H] for p in pts], float)


def to_norm(xy):
    return [[float(x / W), float(y / H)] for x, y in xy]


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
    cov = {i: 0 for i in [364, 370]}
    total = 0
    for y, x in zip(ys.ravel(), xs.ravel()):
        if (x - CX) ** 2 + (y - CY) ** 2 > rr * rr:
            continue
        total += 1
        for i in [364, 370]:
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


def cut_facing_edge(xy):
    """Replace the edge nearest the circle with an arc on the lot's side of the circle."""
    n = len(xy)
    cen = xy.mean(axis=0)
    dists = [(np.linalg.norm(p - [CX, CY]), i) for i, p in enumerate(xy)]
    dists.sort()
    i1 = dists[0][1]
    prev = (i1 - 1) % n
    nxt = (i1 + 1) % n
    i2 = (
        prev
        if np.linalg.norm(xy[prev] - [CX, CY]) <= np.linalg.norm(xy[nxt] - [CX, CY])
        else nxt
    )
    if (i1 + 1) % n == i2:
        e_start, v_a, v_b = i1, xy[i1], xy[i2]
    elif (i2 + 1) % n == i1:
        e_start, v_a, v_b = i2, xy[i2], xy[i1]
    else:
        e_start, v_a, v_b = i1, xy[i1], xy[nxt]
        i2 = nxt

    a1 = math.atan2(v_a[1] - CY, v_a[0] - CX)
    a2 = math.atan2(v_b[1] - CY, v_b[0] - CX)
    da = norm_ang(a2 - a1)
    d_other = da - 2 * math.pi if da > 0 else da + 2 * math.pi

    def arc(d, steps):
        return [
            np.array([CX + R * math.cos(a1 + d * t), CY + R * math.sin(a1 + d * t)])
            for t in np.linspace(0, 1, steps)
        ]

    arc_short = arc(da, 3)
    arc_long = arc(d_other, 5)

    def arc_mid(a):
        return a[len(a) // 2]

    chosen = (
        arc_short
        if np.linalg.norm(arc_mid(arc_short) - cen)
        <= np.linalg.norm(arc_mid(arc_long) - cen)
        else arc_long
    )

    out = []
    for i in range(n):
        if i == e_start:
            out.extend(chosen)
        elif i == (e_start + 1) % n:
            continue
        else:
            out.append(xy[i])
    return np.array(out)


print("BEFORE inkRing6", coverage(6))
print("BEFORE clearR", coverage(R))

for i in [364, 370]:
    xy = to_xy(lots[i]["points"])
    print(i, "before", [(round(x, 1), round(y, 1)) for x, y in xy])
    xy2 = cut_facing_edge(xy)
    # push any remaining verts inside R
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
for i in [364, 370]:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(30, 100, 255, 175), outline=(0, 40, 180, 255))
    for x, y in pts:
        dr.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(220, 0, 0, 255))
    dr.text((L["cx"] * W - 10, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis.crop((int(CX) - 40, int(CY) - 30, int(CX) + 40, int(CY) + 30)).resize(
    (640, 480), Image.NEAREST
).save("scratch/fix_364_370_circle_cut.png")
print("CXCY", CX, CY, "saved QA")

# refresh overview
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
