"""Recentered oriented fit — box centered on ink walls."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
ink = (gray < 108).astype(np.uint8)

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]


def estimate_angle(sx, sy, win=22):
    ix, iy = int(round(sx)), int(round(sy))
    x0, x1 = max(0, ix - win), min(W, ix + win)
    y0, y1 = max(0, iy - win), min(H, iy + win)
    edges = cv2.Canny(gray[y0:y1, x0:x1], 60, 140)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=18, minLineLength=10, maxLineGap=4)
    if lines is None:
        return -12.0
    angs = []
    for x1l, y1l, x2l, y2l in lines[:, 0]:
        a = np.degrees(np.arctan2(y2l - y1l, x2l - x1l))
        while a > 90:
            a -= 180
        while a < -90:
            a += 180
        if abs(a) < 40 or abs(abs(a) - 90) < 40:
            angs.append(a if abs(a) <= 45 else a - 90 * np.sign(a))
    return float(np.median(angs)) if angs else -12.0


def ray_extent(sx, sy, ang_deg, max_t=28.0):
    rad = np.deg2rad(ang_deg)
    hit = max_t
    for t in np.linspace(2.0, max_t, 50):
        xx = int(round(sx + t * np.cos(rad)))
        yy = int(round(sy + t * np.sin(rad)))
        if not (0 <= xx < W and 0 <= yy < H) or ink[yy, xx]:
            hit = t
            break
    return hit


def fit(sx, sy):
    ang = estimate_angle(sx, sy)
    # Prefer map-typical tilt when angle estimate is unstable
    if abs(ang) < 3:
        ang = 12.0
    a0, a1 = ang, ang + 90.0
    r = ray_extent(sx, sy, a0)
    l = ray_extent(sx, sy, a0 + 180)
    d = ray_extent(sx, sy, a1)
    u = ray_extent(sx, sy, a1 + 180)
    # discard runaway (road leak)
    for name, val in [("r", r), ("l", l), ("d", d), ("u", u)]:
        pass
    r = min(r, 22.0)
    l = min(l, 22.0)
    d = min(d, 20.0)
    u = min(u, 20.0)
    ux = np.array([np.cos(np.deg2rad(a0)), np.sin(np.deg2rad(a0))])
    uy = np.array([np.cos(np.deg2rad(a1)), np.sin(np.deg2rad(a1))])
    # recenter onto wall midpoints
    c = np.array([sx, sy], dtype=float) + ux * ((r - l) / 2.0) + uy * ((d - u) / 2.0)
    half_w = (l + r) / 2.0 * 0.86
    half_h = (u + d) / 2.0 * 0.86
    box = np.array([
        c - ux * half_w - uy * half_h,
        c + ux * half_w - uy * half_h,
        c + ux * half_w + uy * half_h,
        c - ux * half_w + uy * half_h,
    ], dtype=np.float32)
    return box, ang, c, half_w * 2, half_h * 2


img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
for sx, sy in seeds:
    box, ang, c, w, h = fit(sx, sy)
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    print(f"({sx:.0f},{sy:.0f}) -> ({c[0]:.1f},{c[1]:.1f}) ang={ang:.1f} {w:.1f}x{h:.1f}")

out = ROOT / "scratch" / "shaded_recentered_fit.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
