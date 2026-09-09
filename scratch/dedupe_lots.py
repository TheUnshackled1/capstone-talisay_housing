"""Dedupe heavily overlapping polygons; keep larger area."""
import json
from pathlib import Path

import numpy as np

path = Path("static/units/lot_plan_polygons.json")
data = json.loads(path.read_text(encoding="utf-8"))
lots = data["lots"]
W, H = data["image"]["w"], data["image"]["h"]


def aabb(L):
    pts = np.array(L["points"], dtype=float)
    return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()


def iou(a, b):
    ax1, ay1, ax2, ay2 = aabb(a)
    bx1, by1, bx2, by2 = aabb(b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    aa = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    bb = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / max(aa + bb - inter, 1e-9)


ordered = sorted(lots, key=lambda L: -L["area"])
kept = []
for L in ordered:
    if any(iou(L, K) >= 0.40 for K in kept):
        continue
    kept.append(L)
kept.sort(key=lambda L: (L["cy"], L["cx"]))
print(f"{len(lots)} -> {len(kept)}")
data["lots"] = kept
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
