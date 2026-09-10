"""Refit shaded grey cluster near B1/B2 into one clickable poly per cell.

Index-stable: replace existing owners in place; append only if no owner.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
POLY = ROOT / "static" / "units" / "lot_plan_polygons.json"
IMG = ROOT / "static" / "images" / "lot_plan_roads.png"

rgb = np.array(Image.open(IMG).convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
data = json.loads(POLY.read_text(encoding="utf-8"))
lots = data["lots"]

ink = cv2.dilate((gray < 100).astype(np.uint8) * 255, np.ones((2, 2), np.uint8), 1)
pad = ((gray >= 128) & (gray <= 178)).astype(np.uint8) * 255
pad = cv2.bitwise_and(pad, cv2.bitwise_not(ink))
split = cv2.erode(pad, np.ones((3, 3), np.uint8), 1)
n, labels, stats, cents = cv2.connectedComponentsWithStats(split, connectivity=8)


def r4(v: float) -> float:
    return round(float(v), 4)


def to_lot(box: np.ndarray) -> dict:
    box = np.asarray(box, dtype=np.float64)
    c = box.mean(axis=0)
    angs = np.arctan2(box[:, 1] - c[1], box[:, 0] - c[0])
    box = box[np.argsort(angs)]
    area = abs(float(cv2.contourArea(box.astype(np.float32))))
    return {
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in box],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area / (W * H)),
    }


def lot_from_label(lab: int) -> dict | None:
    cell = (labels == lab).astype(np.uint8) * 255
    cell = cv2.dilate(cell, np.ones((3, 3), np.uint8), 1)
    cell = cv2.bitwise_and(cell, pad)
    ys, xs = np.where(cell > 0)
    if len(xs) < 40:
        return None
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    box = cv2.boxPoints(cv2.minAreaRect(cnt)).astype(np.float64)
    c = box.mean(axis=0)
    box = c + (box - c) * 0.94
    return to_lot(box)


def find_owner(cx: float, cy: float) -> int | None:
    best = None
    bestd = 1e9
    for i, L in enumerate(lots):
        if not L.get("points"):
            continue
        d = ((L["cx"] * W - cx) ** 2 + (L["cy"] * H - cy) ** 2) ** 0.5
        if d < bestd:
            bestd = d
            best = i
    return best if bestd <= 28 else None


# Top shaded cluster only (near B1/B2)
cells = []
for i in range(1, n):
    x, y, w, h, area = stats[i]
    cx, cy = float(cents[i][0]), float(cents[i][1])
    if not (80 <= cx <= 230 and 70 <= cy <= 165):
        continue
    if not (70 <= area <= 1200 and 7 <= w <= 55 and 7 <= h <= 55):
        continue
    if max(w, h) / max(min(w, h), 1) > 2.9:
        continue
    cells.append((i, cx, cy, int(area)))

print(f"shaded cells in cluster: {len(cells)}")
updated = 0
appended = 0
for lab, cx, cy, area in cells:
    lot = lot_from_label(lab)
    if lot is None:
        print(f"FAIL ({cx:.0f},{cy:.0f})")
        continue
    owner = find_owner(cx, cy)
    if owner is None:
        lots.append(lot)
        appended += 1
        print(f"ADD ({lot['cx']*W:.0f},{lot['cy']*H:.0f}) area={lot['area']}")
    else:
        old = lots[owner]
        print(
            f"REFIT idx={owner} ({old['cx']*W:.0f},{old['cy']*H:.0f}/{old['area']}) "
            f"-> ({lot['cx']*W:.0f},{lot['cy']*H:.0f}/{lot['area']})"
        )
        lots[owner] = lot
        updated += 1

data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"done updated={updated} appended={appended} count={len(lots)}")

vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for L in lots:
    if not L.get("points"):
        continue
    cx, cy = L["cx"] * W, L["cy"] * H
    if not (70 <= cx <= 260 and 60 <= cy <= 180):
        continue
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(40, 200, 80, 90), outline=(0, 140, 40, 255))
vis.crop((70, 60, 260, 180)).resize((570, 360), Image.NEAREST).save(
    ROOT / "scratch" / "shaded_cluster_traced.png"
)
print("QA scratch/shaded_cluster_traced.png")
