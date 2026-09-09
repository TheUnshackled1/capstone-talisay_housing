"""Oriented ray-cast fit for shaded lots — parallelograms along map tilt."""
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
    """Local dominant ink edge angle (degrees)."""
    ix, iy = int(round(sx)), int(round(sy))
    x0, x1 = max(0, ix - win), min(W, ix + win)
    y0, y1 = max(0, iy - win), min(H, iy + win)
    patch = gray[y0:y1, x0:x1]
    edges = cv2.Canny(patch, 60, 140)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=18, minLineLength=10, maxLineGap=4)
    if lines is None:
        return -12.0  # map default tilt
    angs = []
    for x1l, y1l, x2l, y2l in lines[:, 0]:
        a = np.degrees(np.arctan2(y2l - y1l, x2l - x1l))
        # normalize to [-90, 90]
        while a > 90:
            a -= 180
        while a < -90:
            a += 180
        # prefer near-horizontal-ish lot long edges (~ -10 to -20)
        if abs(a) < 40 or abs(abs(a) - 90) < 40:
            angs.append(a if abs(a) <= 45 else a - 90 * np.sign(a))
    if not angs:
        return -12.0
    return float(np.median(angs))


def ray_extent(sx, sy, ang_deg, max_t=28.0):
    rad = np.deg2rad(ang_deg)
    hit = max_t
    for t in np.linspace(2.0, max_t, 40):
        xx = int(round(sx + t * np.cos(rad)))
        yy = int(round(sy + t * np.sin(rad)))
        if not (0 <= xx < W and 0 <= yy < H) or ink[yy, xx]:
            hit = t
            break
    return hit


def fit_oriented(sx, sy):
    ang = estimate_angle(sx, sy)
    # long axis ~ ang, short ~ ang+90
    a0 = ang
    a1 = ang + 90.0
    r = ray_extent(sx, sy, a0)
    l = ray_extent(sx, sy, a0 + 180)
    d = ray_extent(sx, sy, a1)
    u = ray_extent(sx, sy, a1 + 180)
    # clamp runaway open rays
    med = 12.0
    r = r if r < 26 else med
    l = l if l < 26 else med
    d = d if d < 26 else med * 0.9
    u = u if u < 26 else med * 0.9
    pad = 0.90
    ux = np.array([np.cos(np.deg2rad(a0)), np.sin(np.deg2rad(a0))])
    uy = np.array([np.cos(np.deg2rad(a1)), np.sin(np.deg2rad(a1))])
    c = np.array([sx, sy], dtype=float)
    box = np.array([
        c - ux * l * pad - uy * u * pad,
        c + ux * r * pad - uy * u * pad,
        c + ux * r * pad + uy * d * pad,
        c - ux * l * pad + uy * d * pad,
    ], dtype=np.float32)
    return box, ang, (l + r) * pad, (u + d) * pad


img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
for sx, sy in seeds:
    box, ang, w, h = fit_oriented(sx, sy)
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    print(f"({sx:.0f},{sy:.0f}) ang={ang:.1f} {w:.1f}x{h:.1f}")

out = ROOT / "scratch" / "shaded_oriented_fit.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
