"""Inspect specific uncovered bright points and nearby lots."""
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

# rebuild unshrunk-ish by expanding points
def near_lots(px, py, r=40):
    hits = []
    for i, L in enumerate(lots):
        cx, cy = L["cx"] * W, L["cy"] * H
        d = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
        if d < r:
            hits.append((d, i, cx, cy, L["area"]))
    hits.sort()
    return hits

pts = [
    (525, 220),
    (525, 240),
    (525, 260),
    (525, 280),
    (600, 220),
    (600, 280),
    (650, 220),
    (762, 135),  # south of circle 1
    (744, 117),  # west of circle 1
    (846, 37),
    (846, 57),
]
for px, py in pts:
    print(f"\n({px},{py}) gray={gray[py,px]}")
    for d, i, cx, cy, a in near_lots(px, py)[:5]:
        print(f"  lot#{i} d={d:.1f} c=({cx:.0f},{cy:.0f}) area={a}")

# Try flood-fill limited recovery from uncovered bright seeds
from scratch.gen_lot_polygons import build_mask, extract_from_mask, shrink_quad, order_quad, r4, aabb_iou

# More aggressive: weaker ink so cells separate better? Or stronger ink to close gaps?
for ink_t, dil in [(100, 3), (90, 4), (80, 3), (110, 2)]:
    m = build_mask(gray, dilate=dil, close=True, bright_t=150, ink_t=ink_t)
    cands = extract_from_mask(gray, m)
    print(f"mask ink={ink_t} dil={dil} -> raw cands={len(cands)}")

# Check if merging neighbors: look at fill CC sizes around (525,240)
m = build_mask(gray, dilate=2, close=True, bright_t=160, ink_t=100)
n, labels, stats, cents = cv2.connectedComponentsWithStats(m, connectivity=4)
lab = labels[240, 525]
print(f"\nCC at (525,240): label={lab} area={stats[lab,4]} box={stats[lab,:4]}")
lab2 = labels[135, 762]
print(f"CC at (762,135): label={lab2} area={stats[lab2,4]} box={stats[lab2,:4]}")
lab3 = labels[117, 744]
print(f"CC at (744,117): label={lab3} area={stats[lab3,4]} box={stats[lab3,:4]}")
