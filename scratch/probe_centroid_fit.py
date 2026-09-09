"""Centroid-seeded oriented fit for shaded cluster."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

ink_soft = (gray < 108).astype(np.uint8)
ink_hard = cv2.dilate((gray < 108).astype(np.uint8) * 255, np.ones((3, 3), np.uint8), 1)
shaded = ((gray >= 125) & (gray <= 185)).astype(np.uint8) * 255
cells = cv2.bitwise_and(shaded, cv2.bitwise_not(ink_hard))
cells = cv2.morphologyEx(cells, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]


def cell_centroid(sx, sy):
    ix, iy = int(round(sx)), int(round(sy))
    if cells[iy, ix] == 0:
        found = False
        for r in range(1, 10):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and cells[yy, xx]:
                        ix, iy, found = xx, yy, True
                        break
                if found:
                    break
            if found:
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


def estimate_angle(sx, sy, win=22):
    ix, iy = int(round(sx)), int(round(sy))
    x0, x1 = max(0, ix - win), min(W, ix + win)
    y0, y1 = max(0, iy - win), min(H, iy + win)
    edges = cv2.Canny(gray[y0:y1, x0:x1], 60, 140)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=18, minLineLength=10, maxLineGap=4)
    if lines is None:
        return 12.0
    angs = []
    for x1l, y1l, x2l, y2l in lines[:, 0]:
        a = float(np.degrees(np.arctan2(y2l - y1l, x2l - x1l)))
        while a > 90:
            a -= 180
        while a < -90:
            a += 180
        if abs(a) < 40 or abs(abs(a) - 90) < 40:
            angs.append(a if abs(a) <= 45 else a - 90 * np.sign(a))
    if not angs:
        return 12.0
    med = float(np.median(angs))
    return 12.0 if abs(med) < 3 else med


def ray(sx, sy, ang, max_t=26.0):
    rad = np.deg2rad(ang)
    hit = max_t
    for t in np.linspace(1.5, max_t, 60):
        xx = int(round(sx + t * np.cos(rad)))
        yy = int(round(sy + t * np.sin(rad)))
        if not (0 <= xx < W and 0 <= yy < H) or ink_soft[yy, xx]:
            hit = float(t)
            break
    return hit


def fit(sx0, sy0):
    sx, sy = cell_centroid(sx0, sy0)
    ang = estimate_angle(sx, sy)
    a0, a1 = ang, ang + 90.0
    r = min(ray(sx, sy, a0), 20.0)
    l = min(ray(sx, sy, a0 + 180), 20.0)
    d = min(ray(sx, sy, a1), 18.0)
    u = min(ray(sx, sy, a1 + 180), 18.0)
    ux = np.array([np.cos(np.deg2rad(a0)), np.sin(np.deg2rad(a0))])
    uy = np.array([np.cos(np.deg2rad(a1)), np.sin(np.deg2rad(a1))])
    c = np.array([sx, sy]) + ux * ((r - l) / 2) + uy * ((d - u) / 2)
    # second pass from corrected center
    sx, sy = float(c[0]), float(c[1])
    r = min(ray(sx, sy, a0), 20.0)
    l = min(ray(sx, sy, a0 + 180), 20.0)
    d = min(ray(sx, sy, a1), 18.0)
    u = min(ray(sx, sy, a1 + 180), 18.0)
    c = np.array([sx, sy]) + ux * ((r - l) / 2) + uy * ((d - u) / 2)
    half_w = (l + r) / 2 * 0.94
    half_h = (u + d) / 2 * 0.94
    box = np.array([
        c - ux * half_w - uy * half_h,
        c + ux * half_w - uy * half_h,
        c + ux * half_w + uy * half_h,
        c - ux * half_w + uy * half_h,
    ], dtype=np.float32)
    return box, ang, c


img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
for sx, sy in seeds:
    box, ang, c = fit(sx, sy)
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    print(f"({sx:.0f},{sy:.0f}) -> ({c[0]:.1f},{c[1]:.1f}) ang={ang:.1f}")

out = ROOT / "scratch" / "shaded_centroid_fit.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
