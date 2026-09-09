"""Voronoi clip of pad pixels to 8 seeds — fills each gray pad to ink."""
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

SEEDS = np.array([
    [108.0, 96.0],
    [138.0, 101.0],
    [167.0, 106.0],
    [196.0, 111.0],
    [104.0, 116.0],
    [133.0, 126.0],
    [161.0, 134.0],
    [194.0, 145.0],
], dtype=np.float32)

# Pad pixels in the shaded cluster (include dark fringe next to ink)
roi = np.zeros((H, W), np.uint8)
roi[80:168, 90:222] = 255
pad = ((gray >= 85) & (gray <= 198)).astype(np.uint8) * 255
pad = cv2.bitwise_and(pad, roi)
# Keep off the darkest ink cores only
pad[gray < 55] = 0
# Also block bright road
pad[gray > 198] = 0

ys, xs = np.where(pad > 0)
pts = np.column_stack([xs, ys]).astype(np.float32)  # N x 2

# Squared distance to each seed → nearest seed label
# pts: N x 2, seeds: 8 x 2
d2 = ((pts[:, None, :] - SEEDS[None, :, :]) ** 2).sum(axis=2)  # N x 8
labels = np.argmin(d2, axis=1)

vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
fixed = []


def r4(v: float) -> float:
    return round(float(v), 4)


for i in range(8):
    sel = pts[labels == i]
    if len(sel) < 40:
        print("FAIL", i, len(sel))
        continue
    # Build mask and contour
    mask = np.zeros((H, W), np.uint8)
    mask[sel[:, 1].astype(int), sel[:, 0].astype(int)] = 255
    # Close small holes from voronoi noise
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 2)
    # One-pixel grow toward ink, stay in ROI / non-road
    grown = cv2.dilate(mask, np.ones((3, 3), np.uint8), 1)
    allow = ((roi > 0) & (gray >= 55) & (gray <= 198)).astype(np.uint8) * 255
    mask = cv2.bitwise_and(grown, allow)
    # Don't steal neighbors: drop pixels closer to another seed
    ys2, xs2 = np.where(mask > 0)
    if len(xs2):
        p2 = np.column_stack([xs2, ys2]).astype(np.float32)
        d2b = ((p2[:, None, :] - SEEDS[None, :, :]) ** 2).sum(axis=2)
        keep = np.argmin(d2b, axis=1) == i
        mask[:] = 0
        mask[ys2[keep], xs2[keep]] = 255
    mask = cv2.bitwise_and(mask, allow)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        print("FAIL cnt", i)
        continue
    cnt = max(cnts, key=cv2.contourArea)
    peri = float(cv2.arcLength(cnt, True))
    approx = cv2.approxPolyDP(cnt, max(0.5, 0.004 * peri), True)
    if len(approx) < 3:
        approx = cnt
    poly = [(int(p[0][0]), int(p[0][1])) for p in approx]
    dr.polygon(poly, fill=(40, 150, 255, 120), outline=(0, 70, 220, 255))
    for p in poly:
        dr.ellipse((p[0] - 1, p[1] - 1, p[0] + 1, p[1] + 1), fill=(255, 0, 0, 255))
    sx, sy = SEEDS[i]
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
    print(f"OK {i} n={len(poly)} area={area_px:.0f} px={int(mask.sum()//255)}")

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
