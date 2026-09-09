"""Refit mid-right thick-border block with ink-midpoint rays (same as shaded fix)."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
W, H = 906, 543
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

# Region covering the user's screenshots (left thick-border lots + right small column)
X0, X1, Y0, Y1 = 560, 760, 185, 340

# Manual seeds for every cell in this block (centers of gray/white pads inside ink).
# Left thick-border 2-col cluster + right narrow column. Tuned against cand_a.png.
SEEDS = [
    # left column of larger lots (top→bottom)
    (587.0, 205.0),
    (583.0, 222.0),
    (580.0, 239.0),
    (577.0, 256.0),
    (574.0, 273.0),
    (571.0, 290.0),
    # middle / shaded pair area
    (620.0, 210.0),
    (640.0, 230.0),
    (670.0, 235.0),
    (655.0, 255.0),
    (645.0, 275.0),
    (635.0, 295.0),
    # right narrow column (cyan boxes in screenshot)
    (711.0, 202.0),
    (730.0, 205.0),
    (703.0, 248.0),
    (722.0, 250.0),
    (697.0, 273.0),
    (716.0, 276.0),
    (703.0, 295.0),
    (688.0, 313.0),
    (708.0, 314.0),
]


def r4(v: float) -> float:
    return round(float(v), 4)


def order_poly(pts):
    arr = np.array(pts, dtype=float)
    c = arr.mean(axis=0)
    ang = np.arctan2(arr[:, 1] - c[1], arr[:, 0] - c[0])
    return [pts[int(j)] for j in np.argsort(ang)]


def ray_ink_mid(sx: float, sy: float, dx: float, dy: float, max_r: int = 36):
    n = (dx * dx + dy * dy) ** 0.5
    dx, dy = dx / n, dy / n
    ink_start = None
    last_ink = None
    last_pad = (int(round(sx)), int(round(sy)))
    for r in range(1, max_r + 1):
        x = int(round(sx + dx * r))
        y = int(round(sy + dy * r))
        if not (0 <= x < W and 0 <= y < H):
            break
        g = int(gray[y, x])
        if g < 75:
            if ink_start is None:
                ink_start = r
            last_ink = (x, y, r)
            continue
        if ink_start is not None:
            mid_r = (ink_start + last_ink[2]) / 2.0
            return int(round(sx + dx * mid_r)), int(round(sy + dy * mid_r))
        if g <= 205:
            last_pad = (x, y)
            continue
        return last_pad
    if last_ink is not None:
        mid_r = (ink_start + last_ink[2]) / 2.0
        return int(round(sx + dx * mid_r)), int(round(sy + dy * mid_r))
    return last_pad


def fit_seed(sx: float, sy: float):
    # Snap seed onto a non-ink interior pixel
    ix, iy = int(round(sx)), int(round(sy))
    if not (0 <= ix < W and 0 <= iy < H) or gray[iy, ix] < 90:
        found = False
        for r in range(1, 12):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and gray[yy, xx] >= 110:
                        ix, iy = xx, yy
                        found = True
                        break
                if found:
                    break
            if found:
                break
    sx, sy = float(ix), float(iy)

    hits = []
    for i in range(36):
        ang = 2 * np.pi * i / 36
        hits.append(ray_ink_mid(sx, sy, float(np.cos(ang)), float(np.sin(ang))))
    hull = cv2.convexHull(np.array(hits, dtype=np.float32))
    if hull is None or len(hull) < 3:
        return None
    peri = float(cv2.arcLength(hull, True))
    approx = cv2.approxPolyDP(hull, max(0.6, 0.016 * peri), True)
    if len(approx) < 3:
        approx = hull
    poly = [(int(p[0][0]), int(p[0][1])) for p in approx]
    if len(poly) == 4:
        poly = order_poly(poly)
    arr = np.array(poly, dtype=np.float32)
    area_px = float(cv2.contourArea(arr))
    if area_px < 60:
        return None
    c = arr.mean(axis=0)
    return {
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in poly],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
        "_px": poly,
        "_seed": (sx, sy),
    }


# First: auto-discover seeds from existing polygon centers in region + shaded pads
path = ROOT / "static" / "units" / "lot_plan_polygons.json"
data = json.loads(path.read_text(encoding="utf-8"))
auto_seeds = []
for L in data["lots"]:
    cx, cy = L["cx"] * W, L["cy"] * H
    if X0 <= cx <= X1 and Y0 <= cy <= Y1:
        auto_seeds.append((float(cx), float(cy)))

# Shaded pad centroids in region
ink = (gray < 70).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
shaded = ((gray >= 140) & (gray <= 180)).astype(np.uint8) * 255
shaded = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
roi = np.zeros_like(shaded)
roi[Y0:Y1, X0:X1] = 255
shaded = cv2.bitwise_and(shaded, roi)
nlab, _labels, stats, cents = cv2.connectedComponentsWithStats(shaded, 8)
for i in range(1, nlab):
    a = int(stats[i, cv2.CC_STAT_AREA])
    if 80 <= a <= 5000:
        auto_seeds.append((float(cents[i][0]), float(cents[i][1])))

# Merge SEEDS + auto, dedupe by proximity
all_seeds = []
for s in list(SEEDS) + auto_seeds:
    if any((s[0] - t[0]) ** 2 + (s[1] - t[1]) ** 2 < 12**2 for t in all_seeds):
        continue
    # must be interior-ish
    ix, iy = int(round(s[0])), int(round(s[1]))
    if not (X0 <= ix <= X1 and Y0 <= iy <= Y1):
        continue
    if gray[iy, ix] < 100:
        continue
    all_seeds.append(s)

print("seeds", len(all_seeds))

vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
fixed = []
for sx, sy in all_seeds:
    hit = fit_seed(sx, sy)
    if hit is None:
        print("FAIL", sx, sy)
        continue
    # Drop if center drifted out of region or area huge (leaked)
    if not (X0 <= hit["cx"] * W <= X1 and Y0 <= hit["cy"] * H <= Y1):
        print("DROP oob", sx, sy, hit["cx"] * W, hit["cy"] * H)
        continue
    if hit["area"] > 0.008:  # ~4000 px — too big for this block
        print("DROP big", sx, sy, hit["area"])
        continue
    # Deduplicate overlapping fits
    if any(
        (hit["cx"] - f["cx"]) ** 2 + (hit["cy"] - f["cy"]) ** 2 < (8 / W) ** 2
        for f in fixed
    ):
        print("DROP dup", sx, sy)
        continue
    poly = hit.pop("_px")
    seed = hit.pop("_seed")
    dr.polygon(poly, fill=(40, 150, 255, 110), outline=(0, 70, 220, 255))
    dr.ellipse((int(seed[0]) - 1, int(seed[1]) - 1, int(seed[0]) + 1, int(seed[1]) + 1), fill=(255, 255, 255, 255))
    fixed.append(hit)
    print(f"OK {seed} n={len(poly)} area={hit['area']}")

vis.crop((X0, Y0, X1, Y1)).resize((600, 450), Image.NEAREST).save(
    ROOT / "scratch" / "midright_qa.png"
)

# Replace lots whose centers fall in this region
kept = [
    L
    for L in data["lots"]
    if not (X0 <= L["cx"] * W <= X1 and Y0 <= L["cy"] * H <= Y1)
]
kept.extend(fixed)
kept.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = kept
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("lots", len(kept), "fixed", len(fixed), "removed_region_old", len(data["lots"]) - len(kept) + len(fixed))
