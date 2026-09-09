"""Add clickable trace left of B1 L4; refit the lot below B1 L5 (idx 79)."""
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

ink = (gray < 95).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
fillable = ((gray >= 140) & (gray <= 210)).astype(np.uint8) * 255
fillable = cv2.bitwise_and(fillable, cv2.bitwise_not(ink))


def r4(v: float) -> float:
    return round(float(v), 4)


def flood_lot(sx: float, sy: float, roi_box: tuple[int, int, int, int]) -> dict | None:
    x0, y0, x1, y1 = roi_box
    roi = np.zeros((H, W), np.uint8)
    roi[y0:y1, x0:x1] = 255
    region = cv2.bitwise_and(fillable, roi)
    ix, iy = int(round(sx)), int(round(sy))
    if region[iy, ix] == 0:
        found = False
        for r in range(1, 12):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and region[yy, xx]:
                        ix, iy = xx, yy
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if not found:
            return None
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = region.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    # grow to ink midline
    hard = (gray < 55).astype(np.uint8) * 255
    allow = cv2.bitwise_and(roi, cv2.bitwise_not(hard))
    for _ in range(2):
        cell = cv2.bitwise_and(cv2.dilate(cell, np.ones((3, 3), np.uint8), 1), allow)
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    box = cv2.boxPoints(cv2.minAreaRect(cnt)).astype(np.float64)
    c = box.mean(axis=0)
    box = c + (box - c) * 0.94
    angs = np.arctan2(box[:, 1] - c[1], box[:, 0] - c[0])
    box = box[np.argsort(angs)]
    area_px = abs(float(cv2.contourArea(box.astype(np.float32))))
    if area_px < 120:
        return None
    return {
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in box],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    }


# 1) left of B1 L4 (idx 54 at ~489,104)
left = flood_lot(467, 104, (448, 82, 482, 122))
if left is None:
    raise SystemExit("FAIL left of L4")
print(f"LEFT of L4: ({left['cx']*W:.0f},{left['cy']*H:.0f}) area={left['area']}")

# 2) below geographic L5 (idx 51 at ~509,102) — refit idx 79
below = flood_lot(505, 126, (488, 112, 525, 145))
if below is None:
    raise SystemExit("FAIL below L5")
print(f"BELOW L5 refit 79: ({below['cx']*W:.0f},{below['cy']*H:.0f}) area={below['area']}")

# keep indices: replace 79, append left
print(f"idx 79 was ({lots[79]['cx']*W:.0f},{lots[79]['cy']*H:.0f})")
lots[79] = below
lots.append(left)
new_idx = len(lots) - 1
print(f"appended left-of-L4 as idx {new_idx}")

data["lots"] = lots
POLY.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"lots={len(lots)}  index 410 valid={410 < len(lots)}")

vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if not (440 <= cx <= 540 and 80 <= cy <= 160):
        continue
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    fill = None
    if i == 54:
        outline = (220, 40, 40, 255)
    elif i == 51:
        outline = (40, 180, 40, 255)
    elif i == 79:
        fill = (40, 200, 80, 110)
        outline = (0, 140, 40, 255)
    elif i == new_idx:
        fill = (40, 120, 255, 110)
        outline = (0, 70, 220, 255)
    else:
        outline = (0, 170, 255, 200)
    dr.polygon(pts, fill=fill, outline=outline)
vis.crop((440, 75, 540, 160)).resize((500, 425), Image.NEAREST).save(
    ROOT / "scratch" / "b1_l4_l5_fixed.png"
)
print("QA scratch/b1_l4_l5_fixed.png")
