"""Axis-aligned ink-wall fit from cell centroids."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
ink = (gray < 108).astype(np.uint8)
ink_hard = cv2.dilate((gray < 108).astype(np.uint8) * 255, np.ones((3, 3), np.uint8), 1)
shaded = ((gray >= 125) & (gray <= 185)).astype(np.uint8) * 255
cells = cv2.bitwise_and(shaded, cv2.bitwise_not(ink_hard))
cells = cv2.morphologyEx(cells, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]


def centroid(sx, sy):
    ix, iy = int(round(sx)), int(round(sy))
    if cells[iy, ix] == 0:
        for r in range(1, 10):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and cells[yy, xx]:
                        ix, iy = xx, yy
                        break
                else:
                    continue
                break
            else:
                continue
            break
    if cells[iy, ix] == 0:
        return sx, sy
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = cells.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    ys, xs = np.where(flood == 200)
    if len(xs) < 20:
        return sx, sy
    return float(xs.mean()), float(ys.mean())


def ray(sx, sy, ang, max_t=24.0):
    rad = np.deg2rad(ang)
    hit = max_t
    for t in np.linspace(1.5, max_t, 60):
        xx = int(round(sx + t * np.cos(rad)))
        yy = int(round(sy + t * np.sin(rad)))
        if not (0 <= xx < W and 0 <= yy < H) or ink[yy, xx]:
            hit = float(t)
            break
    return hit


def fit(sx0, sy0):
    sx, sy = centroid(sx0, sy0)
    # slight map tilt (~8 deg) — use that fixed angle for this cluster
    ang = 8.0
    a0, a1 = ang, ang + 90.0
    r = min(ray(sx, sy, a0), 18.0)
    l = min(ray(sx, sy, a0 + 180), 18.0)
    d = min(ray(sx, sy, a1), 16.0)
    u = min(ray(sx, sy, a1 + 180), 16.0)
    ux = np.array([np.cos(np.deg2rad(a0)), np.sin(np.deg2rad(a0))])
    uy = np.array([np.cos(np.deg2rad(a1)), np.sin(np.deg2rad(a1))])
    c = np.array([sx, sy]) + ux * ((r - l) / 2) + uy * ((d - u) / 2)
    sx, sy = float(c[0]), float(c[1])
    r = min(ray(sx, sy, a0), 18.0)
    l = min(ray(sx, sy, a0 + 180), 18.0)
    d = min(ray(sx, sy, a1), 16.0)
    u = min(ray(sx, sy, a1 + 180), 16.0)
    c = np.array([sx, sy]) + ux * ((r - l) / 2) + uy * ((d - u) / 2)
    half_w = (l + r) / 2 * 0.96
    half_h = (u + d) / 2 * 0.96
    box = np.array([
        c - ux * half_w - uy * half_h,
        c + ux * half_w - uy * half_h,
        c + ux * half_w + uy * half_h,
        c - ux * half_w + uy * half_h,
    ], dtype=np.float32)
    return box, c


img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
for sx, sy in seeds:
    box, c = fit(sx, sy)
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    print(f"({sx:.0f},{sy:.0f}) -> ({c[0]:.1f},{c[1]:.1f})")

out = ROOT / "scratch" / "shaded_fixed8_fit.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
