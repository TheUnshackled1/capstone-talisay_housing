"""Fit shaded pads to OUTER edge of thick black borders (flush with drawing)."""
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


def r4(v: float) -> float:
    return round(float(v), 4)


def order_poly(pts):
    arr = np.array(pts, dtype=float)
    c = arr.mean(axis=0)
    ang = np.arctan2(arr[:, 1] - c[1], arr[:, 0] - c[0])
    return [pts[int(j)] for j in np.argsort(ang)]


def ray_outer_ink(sx: float, sy: float, dx: float, dy: float, max_r: int = 28):
    """Walk from seed; return midpoint of first ink band (center of thick border)."""
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
        if g < 75:  # ink
            if ink_start is None:
                ink_start = r
            last_ink = (x, y, r)
            continue
        if ink_start is not None:
            # left the ink band — use center of band
            mid_r = (ink_start + last_ink[2]) / 2.0
            return (
                int(round(sx + dx * mid_r)),
                int(round(sy + dy * mid_r)),
            )
        # still on pad / fringe
        if g <= 198:
            last_pad = (x, y)
            continue
        # bright road without hitting ink — stop at last pad
        return last_pad
    if last_ink is not None:
        mid_r = (ink_start + last_ink[2]) / 2.0
        return (
            int(round(sx + dx * mid_r)),
            int(round(sy + dy * mid_r)),
        )
    return last_pad


vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
fixed = []
for sx, sy in SEEDS:
    hits = []
    for i in range(32):
        ang = 2 * np.pi * i / 32
        hits.append(ray_outer_ink(sx, sy, float(np.cos(ang)), float(np.sin(ang))))
    hull = cv2.convexHull(np.array(hits, dtype=np.float32))
    peri = float(cv2.arcLength(hull, True))
    approx = cv2.approxPolyDP(hull, max(0.7, 0.018 * peri), True)
    if len(approx) < 3:
        approx = hull
    poly = [(int(p[0][0]), int(p[0][1])) for p in approx]
    poly = order_poly(poly) if len(poly) == 4 else poly

    dr.polygon(poly, fill=(40, 150, 255, 120), outline=(0, 70, 220, 255))
    for p in poly:
        dr.ellipse((p[0] - 1, p[1] - 1, p[0] + 1, p[1] + 1), fill=(255, 0, 0, 255))
    dr.ellipse((int(sx) - 1, int(sy) - 1, int(sx) + 1, int(sy) + 1), fill=(255, 255, 255, 255))

    arr = np.array(poly, dtype=np.float32)
    area_px = float(cv2.contourArea(arr))
    c = arr.mean(axis=0)
    pts_n = [[r4(float(x) / W), r4(float(y) / H)] for x, y in poly]
    fixed.append({
        "points": pts_n,
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    })
    print(f"OK {sx,sy} n={len(poly)} area={area_px:.0f}")

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
