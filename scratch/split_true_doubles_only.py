"""Surgical index-stable split of true 2-cell merges only (ink-separated)."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
POLY_PATH = ROOT / "static" / "units" / "lot_plan_polygons.json"
IMG_PATH = ROOT / "static" / "images" / "lot_plan_roads.png"

rgb = np.array(Image.open(IMG_PATH).convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
data = json.loads(POLY_PATH.read_text(encoding="utf-8"))
lots = data["lots"]
MED = float(np.median([L["area"] * W * H for L in lots]))
print(f"lots={len(lots)} med={MED:.0f}")


def r4(v: float) -> float:
    return round(float(v), 4)


def lot_from_comp(comp: np.ndarray) -> dict | None:
    cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(cnt)
    if not (8 <= w <= 90 and 8 <= h <= 90):
        return None
    box = cv2.boxPoints(cv2.minAreaRect(cnt)).astype(np.float64)
    c = box.mean(axis=0)
    box = c + (box - c) * 0.94
    angs = np.arctan2(box[:, 1] - c[1], box[:, 0] - c[0])
    box = box[np.argsort(angs)]
    area_px = abs(float(cv2.contourArea(box.astype(np.float32))))
    if area_px < MED * 0.45 or area_px > MED * 1.55:
        return None
    return {
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in box],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    }


def try_split(L: dict) -> tuple[dict, dict] | None:
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.int32)
    roi = np.zeros((H, W), np.uint8)
    cv2.fillConvexPoly(roi, pts, 255)
    roi = cv2.dilate(roi, np.ones((3, 3), np.uint8), 1)
    local_ink = ((gray < 140) & (roi > 0)).astype(np.uint8) * 255
    local_ink = cv2.dilate(local_ink, np.ones((2, 2), np.uint8), 1)
    cells = cv2.bitwise_and(roi, cv2.bitwise_not(local_ink))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cells, connectivity=4)
    found = []
    for k in range(1, n):
        _x, _y, w, h, area = stats[k]
        if not (90 <= area <= 1800 and 8 <= w <= 80 and 8 <= h <= 80):
            continue
        lot = lot_from_comp((labels == k).astype(np.uint8) * 255)
        if lot is not None:
            found.append(lot)
    found.sort(key=lambda p: -p["area"])
    if len(found) < 2:
        return None
    a, b = found[0], found[1]
    ra = max(a["area"], b["area"]) / min(a["area"], b["area"])
    d = np.hypot((a["cx"] - b["cx"]) * W, (a["cy"] - b["cy"]) * H)
    if ra > 1.8 or d < 10:
        return None
    return a, b


original_n = len(lots)
n_split = 0
for i in range(original_n):
    pair = try_split(lots[i])
    if pair is None:
        continue
    a, b = pair
    ox, oy = lots[i]["cx"], lots[i]["cy"]
    da = (a["cx"] - ox) ** 2 + (a["cy"] - oy) ** 2
    db = (b["cx"] - ox) ** 2 + (b["cy"] - oy) ** 2
    keep, extra = (a, b) if da <= db else (b, a)
    print(
        f"SPLIT {i} ({lots[i]['cx']*W:.0f},{lots[i]['cy']*H:.0f}) "
        f"-> ({keep['cx']*W:.0f},{keep['cy']*H:.0f}) + ({extra['cx']*W:.0f},{extra['cy']*H:.0f})"
    )
    lots[i] = keep
    lots.append(extra)
    n_split += 1

data["lots"] = lots
POLY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"{original_n} -> {len(lots)} splits={n_split}")
print(f"index 410 valid? {410 < len(lots)} (0-{len(lots)-1})")

vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for L in lots:
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, outline=(0, 170, 255, 200))
for L in lots[original_n:]:
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(40, 210, 80, 110), outline=(0, 140, 40, 255))
vis.crop((380, 150, 490, 300)).resize((440, 600), Image.NEAREST).save(
    ROOT / "scratch" / "b13_split_only.png"
)
print("QA scratch/b13_split_only.png")
