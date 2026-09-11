"""Final clean edge-trace for 298/295/289: corners + smoothed road curve."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
POLY = Path("static/units/lot_plan_polygons.json")

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
data = json.loads(POLY.read_text())
lots = data["lots"]
assert len(lots) == 420


def r4(v: float) -> float:
    return round(float(v), 4)


def poly_area(pts: np.ndarray) -> float:
    return abs(float(cv2.contourArea(pts.astype(np.float32))))


def mask_of(pts: np.ndarray) -> np.ndarray:
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.round(pts).astype(np.int32)], 1)
    return m


def lot_xy(i: int) -> np.ndarray:
    return np.array([[p[0] * W, p[1] * H] for p in lots[i]["points"]], float)


def ink_x(guess: int, y0: int, y1: int, span: int = 4) -> float:
    best_x, best = guess, 1e18
    for x in range(guess - span, guess + span + 1):
        col = gray[y0:y1, x].astype(float)
        s = col.mean() - 3 * (col < 75).sum()
        if s < best:
            best, best_x = s, x
    return float(best_x)


def bottommost_road_top(x: float, y_lo: float, y_hi: int = 366) -> float | None:
    """Top of the lowest horizontal ink stroke (= road inner edge)."""
    xi = int(round(x))
    best = None
    y = int(y_lo)
    while y < y_hi:
        if gray[y, xi] >= 92:
            y += 1
            continue
        y0 = y
        while y + 1 < y_hi and gray[y + 1, xi] < 105:
            y += 1
        run = y - y0 + 1
        horiz = sum(
            1 for dx in (-3, -2, -1, 1, 2, 3) if 0 <= xi + dx < W and gray[y0, xi + dx] < 100
        )
        if horiz >= 2 and run <= 12:
            # keep lowest stroke (largest y0)
            if best is None or y0 > best:
                best = float(y0)
        y += 1
    return best


def smooth_ys(ys: list[float], win: int = 3) -> np.ndarray:
    arr = np.array(ys, float)
    out = arr.copy()
    for i in range(len(arr)):
        lo = max(0, i - win // 2)
        hi = min(len(arr), i + win // 2 + 1)
        out[i] = float(np.median(arr[lo:hi]))
    return out


p277, p357, p269 = lot_xy(277), lot_xy(357), lot_xy(269)
# Pin walls from pixel inspection of ink columns
X = [635.0, 676.0, 694.0, 715.0]
X = [ink_x(int(x), 328, 350, span=1) for x in X]
IN = 0.7
YT = {
    298: float(p277[:, 1].max()) + 0.8,
    295: float(p357[:, 1].max()) + 0.8,
    289: float(p269[:, 1].max()) + 0.8,
}
print("walls", X)
print("tops", YT)


def build(xl: float, xr: float, yt: float, n: int) -> np.ndarray:
    tl = (xl + IN, yt)
    tr = (xr - IN, yt)
    xs = np.linspace(xl + IN, xr - IN, n)
    raw = []
    for x in xs:
        # ignore upper horizontals (neighbor bottoms); road is the lowest stroke
        y = bottommost_road_top(x, y_lo=max(yt + 8, 338))
        if y is None:
            y = bottommost_road_top(x, y_lo=yt + 3)
        raw.append(yt + 22 if y is None else y)
    ys = smooth_ys(raw, win=3)
    # reject outliers vs local median
    for _ in range(2):
        med = smooth_ys(list(ys), win=5)
        for i in range(len(ys)):
            if abs(ys[i] - med[i]) > 4:
                ys[i] = med[i]
    road = [(float(xs[i]), float(ys[i]) - 0.35) for i in range(len(xs))]
    br = (xr - IN, road[-1][1])
    bl = (xl + IN, road[0][1])
    mid = list(reversed(road))[1:-1]
    pts = [tl, tr, br] + mid + [bl]
    out = [pts[0]]
    for p in pts[1:]:
        if np.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 0.9:
            out.append(p)
    arr = np.array(out, float)
    if abs(arr[0, 1] - arr[-1, 1]) < 8:
        raise RuntimeError(f"degenerate left edge: {arr[0]} {arr[-1]}")
    return arr


results = {
    298: build(X[0], X[1], YT[298], 9),
    295: build(X[1], X[2], YT[295], 6),
    289: build(X[2], X[3], YT[289], 8),
}
for i, p in results.items():
    print(i, [(round(x, 1), round(y, 1)) for x, y in p], "a", round(poly_area(p)))

for a, b, w in [(298, 295, X[1]), (295, 289, X[2])]:
    for _ in range(5):
        v = int((mask_of(results[a]) & mask_of(results[b])).sum())
        if v <= 5:
            break
        for idx, sgn in ((a, -1), (b, 1)):
            pts = results[idx]
            for j in range(len(pts)):
                if abs(pts[j, 0] - w) < 3:
                    pts[j, 0] += sgn * 0.3
            results[idx] = pts

for idx, ab in [(298, 277), (295, 357), (289, 269)]:
    for _ in range(8):
        v = int((mask_of(results[idx]) & mask_of(lot_xy(ab))).sum())
        if v <= 5:
            break
        pts = results[idx]
        top = pts[:, 1].min()
        for j in range(len(pts)):
            if pts[j, 1] <= top + 0.6:
                pts[j, 1] += 0.45
        results[idx] = pts

for idx, pts in results.items():
    ap = poly_area(pts)
    lots[idx] = {
        "points": [[r4(x / W), r4(y / H)] for x, y in pts],
        "cx": r4(pts[:, 0].mean() / W),
        "cy": r4(pts[:, 1].mean() / H),
        "area": r4(ap / (W * H)),
    }

assert len(lots) == 420
data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2) + "\n")

print("\nFINAL")
for i in [298, 295, 289]:
    pts = lot_xy(i)
    print(
        i,
        "n",
        len(pts),
        "a",
        round(poly_area(pts)),
        "y",
        round(pts[:, 1].min(), 1),
        "-",
        round(pts[:, 1].max(), 1),
    )
    print(" ", [(round(x, 1), round(y, 1)) for x, y in pts])

ids = [297, 277, 357, 269, 298, 295, 289]
ms = {i: mask_of(lot_xy(i)) for i in ids}
print(
    "ovs",
    [(a, b, int((ms[a] & ms[b]).sum())) for a in ids for b in ids if b > a and int((ms[a] & ms[b]).sum()) > 5],
)

cols = {298: (220, 40, 200, 150), 295: (255, 140, 0, 150), 289: (40, 120, 255, 150)}
vis = Image.fromarray(rgb.copy()).convert("RGBA")
dr = ImageDraw.Draw(vis, "RGBA")
for i in [245, 258, 255, 270, 277, 357, 269, 297, 298, 295, 289]:
    L = lots[i]
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=cols.get(i, (40, 200, 80, 100)), outline=(0, 100, 0, 255))
    if i in cols:
        for x, y in pts:
            dr.ellipse([x - 2.2, y - 2.2, x + 2.2, y + 2.2], fill=(255, 0, 0, 255))
    dr.text((L["cx"] * W - 10, L["cy"] * H - 4), str(i), fill=(200, 0, 0, 255))
vis.crop((600, 300, 730, 370)).resize((650, 350), Image.NEAREST).save("scratch/fix_295_row.png")

edge = Image.fromarray(rgb.copy()).convert("RGBA")
edr = ImageDraw.Draw(edge, "RGBA")
for i, col in cols.items():
    pts = [(p[0] * W, p[1] * H) for p in lots[i]["points"]]
    edr.line(pts + [pts[0]], fill=col[:3] + (255,), width=2)
    for x, y in pts:
        edr.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=(255, 0, 0, 255))
edge.crop((600, 300, 730, 370)).resize((650, 350), Image.NEAREST).save("scratch/fix_295_edges.png")
print("saved scratch/fix_295_row.png + fix_295_edges.png")
