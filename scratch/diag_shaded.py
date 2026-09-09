"""Find shaded lot fills missing polygons; also try stronger ink recovery."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
lots = json.loads((ROOT / "static/units/lot_plan_polygons.json").read_text())["lots"]

cov = np.zeros((H, W), dtype=np.uint8)
for L in lots:
    p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], dtype=np.int32)
    cv2.fillConvexPoly(cov, p, 255)

# Shaded lots: mid-gray plateaus
shaded = ((gray >= 130) & (gray <= 175)).astype(np.uint8) * 255
ink = (gray < 100).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
shaded = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
shaded = cv2.morphologyEx(shaded, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1)
n, labels, stats, cents = cv2.connectedComponentsWithStats(shaded, connectivity=4)
print("shaded CCs (area 80-2500):")
missed_shaded = []
for i in range(1, n):
    x, y, w, h, area = stats[i]
    if not (80 <= area <= 2500):
        continue
    if not (8 <= w <= 90 and 8 <= h <= 90):
        continue
    if max(w, h) / max(min(w, h), 1) > 3.5:
        continue
    cx, cy = int(cents[i][0]), int(cents[i][1])
    covered = bool(cov[cy, cx])
    print(f"  ({cx},{cy}) {w}x{h} area={area} cov={covered} mean={gray[cy,cx]}")
    if not covered:
        missed_shaded.append((cx, cy, w, h, area))

print(f"missed shaded={len(missed_shaded)}")

# Stronger ink seal recovery
for close_k, dil in [(3, 3), (5, 2), (3, 4)]:
    ink2 = (gray < 115).astype(np.uint8) * 255
    ink2 = cv2.dilate(ink2, np.ones((dil, dil), np.uint8), 1)
    ink2 = cv2.morphologyEx(ink2, cv2.MORPH_CLOSE, np.ones((close_k, close_k), np.uint8), 2)
    bright = (gray > 150).astype(np.uint8) * 255
    mid = ((gray >= 120) & (gray <= 185)).astype(np.uint8) * 255
    fill = cv2.bitwise_or(bright, mid)
    mask = cv2.bitwise_and(fill, cv2.bitwise_not(ink2))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)
    n2, _, stats2, cents2 = cv2.connectedComponentsWithStats(mask, connectivity=4)
    good = 0
    new_uncov = 0
    for i in range(1, n2):
        x, y, w, h, area = stats2[i]
        if not (85 <= area <= 3600):
            continue
        if not (8 <= w <= 95 and 8 <= h <= 95):
            continue
        if max(w, h) / max(min(w, h), 1) > 3.8:
            continue
        good += 1
        cx, cy = int(cents2[i][0]), int(cents2[i][1])
        if 4 <= cx < W - 4 and 4 <= cy < H - 4 and not cov[cy, cx] and gray[cy, cx] >= 120:
            new_uncov += 1
    print(f"seal close={close_k} dil={dil}: goodCCs={good} uncovered_centers={new_uncov}")

# Visualize missed shaded
dbg = rgb.copy()
for L in lots:
    p = np.array([[int(pp[0] * W), int(pp[1] * H)] for pp in L["points"]], dtype=np.int32)
    cv2.polylines(dbg, [p], True, (0, 200, 255), 1)
for cx, cy, w, h, area in missed_shaded:
    cv2.rectangle(dbg, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2), (255, 0, 0), 2)
Image.fromarray(dbg).save(ROOT / "scratch/lot_map_missed_shaded.png")
print("wrote scratch/lot_map_missed_shaded.png")
