"""Add SVG polygons for lot cells that exist on the PNG but lack traces."""
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


def r4(v: float) -> float:
    return round(float(v), 4)


def coverage_mask(lot_list: list[dict]) -> np.ndarray:
    cov = np.zeros((H, W), dtype=np.uint8)
    for L in lot_list:
        pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.int32)
        cv2.fillConvexPoly(cov, pts, 255)
    return cov


def find_missed(lot_list: list[dict]) -> list[dict]:
    cov = coverage_mask(lot_list)
    centers = [(L["cx"] * W, L["cy"] * H) for L in lot_list]

    ink = (gray < 110).astype(np.uint8) * 255
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8), 1)
    cells = cv2.bitwise_not(ink)
    cells = cv2.morphologyEx(cells, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(cells, connectivity=4)

    missed = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (80 <= area <= 2800 and 8 <= w <= 90 and 8 <= h <= 90):
            continue
        if max(w, h) / max(min(w, h), 1) > 3.5:
            continue
        cx, cy = float(cents[i][0]), float(cents[i][1])
        if not (6 <= cx < W - 6 and 6 <= cy < H - 6):
            continue
        if any(labels[int(round(yy)), int(round(xx))] == i for xx, yy in centers):
            continue
        sub_cov = cov[y : y + h, x : x + w]
        sub_lab = labels[y : y + h, x : x + w] == i
        sub_gray = gray[y : y + h, x : x + w]
        if not sub_lab.any():
            continue
        if float(sub_cov[sub_lab].mean()) > 40:
            continue
        gmean = float(sub_gray[sub_lab].mean())
        if gmean < 100:
            continue
        if gmean > 210 and min(w, h) < 12:
            continue
        missed.append(
            {
                "label": i,
                "cx": cx,
                "cy": cy,
                "x": int(x),
                "y": int(y),
                "w": int(w),
                "h": int(h),
                "area": int(area),
                "gmean": gmean,
            }
        )
    missed.sort(key=lambda r: -r["area"])
    return missed, labels


def flood_poly(sx: float, sy: float, labels: np.ndarray, label_id: int) -> dict | None:
    """Build a slightly inset convex-ish polygon from the connected cell."""
    cell = (labels == label_id).astype(np.uint8) * 255
    # Grow a couple pixels toward ink midlines so the clickable area fills the box
    hard = (gray < 55).astype(np.uint8) * 255
    allow = cv2.bitwise_not(hard)
    for _ in range(2):
        grown = cv2.dilate(cell, np.ones((3, 3), np.uint8), 1)
        cell = cv2.bitwise_and(grown, allow)

    area = int(cell.sum() // 255)
    if area < 60 or area > 5000:
        return None

    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    peri = float(cv2.arcLength(cnt, True))
    approx = cv2.approxPolyDP(cnt, max(0.5, 0.015 * peri), True)
    if len(approx) < 3:
        # AABB fallback
        x, y, w, h = cv2.boundingRect(cnt)
        inset = 1.2
        corners = np.array(
            [
                [x + inset, y + inset],
                [x + w - inset, y + inset],
                [x + w - inset, y + h - inset],
                [x + inset, y + h - inset],
            ],
            dtype=np.float32,
        )
    else:
        corners = approx.reshape(-1, 2).astype(np.float32)
        # Shrink slightly toward centroid so strokes don't bleed into neighbors
        c = corners.mean(axis=0)
        corners = c + (corners - c) * 0.92

    # Order CCW by angle
    c = corners.mean(axis=0)
    angs = np.arctan2(corners[:, 1] - c[1], corners[:, 0] - c[0])
    corners = corners[np.argsort(angs)]

    area_px = float(cv2.contourArea(corners))
    if area_px < 50:
        return None

    pts = [[r4(float(x) / W), r4(float(y) / H)] for x, y in corners]
    return {
        "points": pts,
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    }


def overlaps_existing(new: dict, lot_list: list[dict], thresh: float = 0.30) -> bool:
    pts = np.array([[p[0] * W, p[1] * H] for p in new["points"]], dtype=np.int32)
    mask = np.zeros((H, W), dtype=np.uint8)
    cv2.fillConvexPoly(mask, pts, 255)
    new_area = max(int(mask.sum() // 255), 1)
    nx, ny = new["cx"] * W, new["cy"] * H
    for L in lot_list:
        d = ((L["cx"] * W - nx) ** 2 + (L["cy"] * H - ny) ** 2) ** 0.5
        if d < 6:
            return True
        if d > 55:
            continue
        lpts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.int32)
        other = np.zeros((H, W), dtype=np.uint8)
        cv2.fillConvexPoly(other, lpts, 255)
        inter = int(np.logical_and(mask > 0, other > 0).sum())
        if inter > new_area * thresh:
            return True
    return False


missed, labels = find_missed(lots)
print(f"missed candidates: {len(missed)}")

added = []
for m in missed:
    poly = flood_poly(m["cx"], m["cy"], labels, m["label"])
    if poly is None:
        print(f"FAIL flood ({m['cx']:.0f},{m['cy']:.0f})")
        continue
    if overlaps_existing(poly, lots + added):
        print(f"DROP overlap ({m['cx']:.0f},{m['cy']:.0f})")
        continue
    added.append(poly)
    print(
        f"OK ({m['cx']:.0f},{m['cy']:.0f}) -> "
        f"({poly['cx']*W:.0f},{poly['cy']*H:.0f}) n={len(poly['points'])} area={poly['area']}"
    )

before = len(lots)
lots = lots + added
lots.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = lots
POLY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"lots {before} -> {len(lots)} (+{len(added)})")

# QA overlays
vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for L in lots:
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, outline=(0, 180, 255, 220))
for m in missed:
    dr.ellipse(
        (m["cx"] - 3, m["cy"] - 3, m["cx"] + 3, m["cy"] + 3),
        fill=(255, 40, 40, 220),
    )
for L in added:
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(40, 200, 80, 90), outline=(0, 180, 40, 255))

vis.save(ROOT / "scratch" / "missing_lots_all.png")
# Right columns crop (B15/B17)
vis.crop((600, 0, 860, 420)).resize((520, 840), Image.NEAREST).save(
    ROOT / "scratch" / "miss_R1.png"
)
# Center shaded strip
vis.crop((500, 140, 650, 400)).resize((450, 780), Image.NEAREST).save(
    ROOT / "scratch" / "miss_R2.png"
)

# Re-run miss detection
still, _ = find_missed(lots)
print(f"still_missed_after_patch: {len(still)}")
for m in still:
    print(f"  remaining ({m['cx']:.0f},{m['cy']:.0f}) area={m['area']} gmean={m['gmean']:.0f}")
