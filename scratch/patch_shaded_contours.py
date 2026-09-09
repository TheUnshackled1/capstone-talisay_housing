"""Competitive dilation: expand separated pads until they meet at ink / each other."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

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

# Separators only for INITIAL seed flood (keep cells distinct)
sep = (gray < 85).astype(np.uint8) * 255
sep = cv2.dilate(sep, np.ones((2, 2), np.uint8), 1)
pad_seed = ((gray >= 150) & (gray <= 178)).astype(np.uint8) * 255
pad_seed = cv2.bitwise_and(pad_seed, cv2.bitwise_not(sep))

# Space we are allowed to claim: everything in ROI that isn't hard black core
roi = np.zeros((H, W), np.uint8)
roi[78:172, 92:222] = 255
hard_ink = gray < 55  # only the darkest core of borders
claimable = (roi > 0) & (~hard_ink) & (gray <= 200)


def initial_mask(sx: float, sy: float) -> np.ndarray | None:
    ix, iy = int(round(sx)), int(round(sy))
    if pad_seed[iy, ix] == 0:
        for r in range(1, 20):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and pad_seed[yy, xx]:
                        ix, iy = xx, yy
                        break
                else:
                    continue
                break
            else:
                continue
            break
    if pad_seed[iy, ix] == 0:
        return None
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = pad_seed.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    return (flood == 200).astype(np.uint8)


# Build label map
labels = np.zeros((H, W), np.int32)
for i, (sx, sy) in enumerate(SEEDS, start=1):
    m = initial_mask(sx, sy)
    if m is None:
        print("no seed", sx, sy)
        continue
    labels[m > 0] = i

kernel = np.ones((3, 3), np.uint8)
for _ in range(30):
    changed = False
    # Snapshot so growth is simultaneous
    prev = labels.copy()
    for i in range(1, 9):
        cell = (prev == i).astype(np.uint8) * 255
        if cell.sum() == 0:
            continue
        grown = cv2.dilate(cell, kernel, 1)
        # claim pixels that are claimable and currently unlabeled
        claim = (grown > 0) & (prev == 0) & claimable
        if claim.any():
            labels[claim] = i
            changed = True
    if not changed:
        break

vis = rgb.copy()
fixed: list[dict] = []


def r4(v: float) -> float:
    return round(float(v), 4)


for i, (sx, sy) in enumerate(SEEDS, start=1):
    cell = (labels == i).astype(np.uint8) * 255
    # Remove residual dark border from fill (hover on gray only)
    cell[gray < 85] = 0
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        print("FAIL", i)
        continue
    cnt = max(cnts, key=cv2.contourArea)
    peri = float(cv2.arcLength(cnt, True))
    approx = cv2.approxPolyDP(cnt, max(0.5, 0.005 * peri), True)
    if len(approx) < 3:
        approx = cnt
    pts = approx.reshape(-1, 2).astype(np.float32)
    px = np.round(pts).astype(np.int32)
    ys, xs = np.where(cell > 0)
    vis[ys, xs] = (vis[ys, xs] * 0.35 + np.array([40, 150, 255]) * 0.65).astype(np.uint8)
    cv2.polylines(vis, [px], True, (0, 50, 220), 1)
    c = pts.mean(axis=0)
    area_px = float(cv2.contourArea(pts))
    pts_n = [[r4(float(x) / W), r4(float(y) / H)] for x, y in pts]
    lot = {
        "points": pts_n,
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    }
    fixed.append(lot)
    print(f"OK {i} {sx,sy} n={len(pts_n)} area={area_px:.0f} px={len(ys)}")

Image.fromarray(vis).crop((85, 70, 230, 180)).save(ROOT / "scratch" / "shaded_mask_fill_qa.png")

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
