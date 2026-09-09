"""Hand quads expanded outward to last pad pixel before black ink."""
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

# Seed centers for the 8 cells
SEEDS = [
    (108.0, 96.0),
    (138.0, 101.0),
    (167.0, 106.0),
    (196.0, 111.0),
    (104.0, 116.0),
    (133.0, 126.0),
    (161.0, 134.0),
    (194.0, 145.0),
]

# Approximate corner directions from center (NW, NE, SE, SW) in unit vectors
# Adjusted slightly for map slant
CORNER_DIRS = [
    (-0.85, -0.55),
    (0.90, -0.40),
    (0.75, 0.70),
    (-0.80, 0.65),
]


def r4(v: float) -> float:
    return round(float(v), 4)


def order_quad(pts):
    arr = np.array(pts, dtype=float)
    c = arr.mean(axis=0)
    ang = np.arctan2(arr[:, 1] - c[1], arr[:, 0] - c[0])
    return [pts[int(j)] for j in np.argsort(ang)]


def is_pad(x: int, y: int) -> bool:
    # Include darker fringe next to thick black borders
    return 0 <= x < W and 0 <= y < H and 105 <= gray[y, x] <= 195


def is_ink(x: int, y: int) -> bool:
    return 0 <= x < W and 0 <= y < H and gray[y, x] < 65


def ray_to_pad_edge(sx: float, sy: float, dx: float, dy: float, max_r: int = 24) -> tuple[int, int]:
    """Walk from seed toward corner; stop at last pad pixel before ink/non-pad."""
    last = (int(round(sx)), int(round(sy)))
    n = (dx * dx + dy * dy) ** 0.5
    dx, dy = dx / n, dy / n
    for r in range(1, max_r + 1):
        x = int(round(sx + dx * r))
        y = int(round(sy + dy * r))
        if is_ink(x, y):
            return last
        if is_pad(x, y):
            last = (x, y)
            continue
        return last
    return last


vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
fixed = []
for sx, sy in SEEDS:
    corners = [ray_to_pad_edge(sx, sy, dx, dy) for dx, dy in CORNER_DIRS]
    # Also cast more rays and take convex hull for better shape
    extra_dirs = []
    for i in range(24):
        ang = 2 * np.pi * i / 24
        extra_dirs.append((np.cos(ang), np.sin(ang)))
    hits = [ray_to_pad_edge(sx, sy, dx, dy, max_r=26) for dx, dy in extra_dirs]
    hull = cv2.convexHull(np.array(hits, dtype=np.float32))
    peri = float(cv2.arcLength(hull, True))
    approx = cv2.approxPolyDP(hull, max(0.8, 0.02 * peri), True)
    if len(approx) < 3:
        approx = hull
    pts = approx.reshape(-1, 2).astype(np.float32)
    # Slight expand toward ink
    c = pts.mean(axis=0)
    pts = c + (pts - c) * 1.06
    clamped = []
    for x, y in pts:
        xi, yi = int(round(x)), int(round(y))
        if is_pad(xi, yi) and not is_ink(xi, yi):
            clamped.append((xi, yi))
        else:
            for t in np.linspace(0.99, 0.55, 16):
                xx = int(round(c[0] + (x - c[0]) * t))
                yy = int(round(c[1] + (y - c[1]) * t))
                if is_pad(xx, yy) and not is_ink(xx, yy):
                    clamped.append((xx, yy))
                    break
            else:
                clamped.append((int(c[0]), int(c[1])))
    snapped = order_quad(clamped) if len(clamped) == 4 else clamped
    if len(snapped) > 8:
        # keep hull approx as-is (better shape than 4-corner fallback)
        snapped = [(int(p[0]), int(p[1])) for p in clamped]

    arr = np.array(snapped, dtype=np.int32)
    dr.polygon([tuple(p) for p in snapped], fill=(40, 150, 255, 120), outline=(0, 70, 220, 255))
    for p in snapped:
        dr.ellipse((p[0] - 1, p[1] - 1, p[0] + 1, p[1] + 1), fill=(255, 0, 0, 255))
    dr.ellipse((int(sx) - 1, int(sy) - 1, int(sx) + 1, int(sy) + 1), fill=(255, 255, 255, 255))

    pts_n = [[r4(x / W), r4(y / H)] for x, y in snapped]
    cf = arr.mean(axis=0).astype(float)
    area_px = float(cv2.contourArea(arr.astype(np.float32)))
    fixed.append({
        "points": pts_n,
        "cx": r4(float(cf[0]) / W),
        "cy": r4(float(cf[1]) / H),
        "area": r4(area_px / (W * H)),
    })
    print(f"seed {sx,sy} n={len(snapped)} area={area_px:.0f} pts={snapped}")

vis.crop((85, 70, 230, 180)).save(ROOT / "scratch" / "shaded_mask_fill_qa.png")
vis.crop((85, 70, 230, 180)).resize((435, 330), Image.NEAREST).save(
    ROOT / "scratch" / "shaded_mask_fill_qa_big.png"
)

path = ROOT / "static" / "units" / "lot_plan_polygons.json"
data = json.loads(path.read_text(encoding="utf-8"))
lots = [
    L
    for L in data["lots"]
    if not (95 <= L["cx"] * W <= 215 and 80 <= L["cy"] * H <= 160)
]
lots.extend(fixed)
lots.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = lots
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("lots", len(lots), "shaded", len(fixed))
