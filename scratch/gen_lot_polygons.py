"""
Detect lot fill regions on static/images/lot_plan_roads.png and write
static/units/lot_plan_polygons.json.

Rotated min-area quads follow tilted lots. No block/lot labels.
Resets slots/clusters to empty.

Run: python scratch/gen_lot_polygons.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG_PATH = ROOT / "static" / "images" / "lot_plan_roads.png"
OUT_PATH = ROOT / "static" / "units" / "lot_plan_polygons.json"
SLOTS_PATH = ROOT / "static" / "units" / "lot_plan_slots.json"
CLUSTERS_PATH = ROOT / "static" / "units" / "lot_plan_clusters.json"
DEBUG_PATH = ROOT / "scratch" / "lot_map_polygons_debug.png"

BRIGHT_THRESH = 185
INK_THRESH = 90
MIN_AREA = 140
MAX_AREA = 2400
MIN_SIDE = 11
MAX_SIDE = 58
MAX_ASPECT = 2.8
MIN_SOLIDITY = 0.72
MARGIN = 10
SHRINK = 0.82


def r4(v: float) -> float:
    return round(float(v), 4)


def build_mask(gray: np.ndarray) -> np.ndarray:
    bright = (gray > BRIGHT_THRESH).astype(np.uint8) * 255
    mid = ((gray >= 135) & (gray <= 178)).astype(np.uint8) * 255
    ink = (gray < INK_THRESH).astype(np.uint8) * 255
    # Seal broken lot borders so interiors become separate cells
    ink = cv2.dilate(ink, np.ones((3, 3), np.uint8), iterations=1)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    fill = cv2.bitwise_or(bright, mid)
    mask = cv2.bitwise_and(fill, cv2.bitwise_not(ink))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
    return mask


def shrink_quad(pts: np.ndarray, factor: float) -> np.ndarray:
    c = pts.mean(axis=0)
    return c + (pts - c) * factor


def order_quad(pts: list[list[float]]) -> list[list[float]]:
    arr = np.array(pts, dtype=float)
    angles = np.arctan2(arr[:, 1] - arr[:, 1].mean(), arr[:, 0] - arr[:, 0].mean())
    return [pts[int(j)] for j in np.argsort(angles)]


def detect_lots(gray: np.ndarray) -> tuple[list[dict], list[np.ndarray]]:
    H, W = gray.shape
    mask = build_mask(gray)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)

    lots: list[dict] = []
    debug_quads: list[np.ndarray] = []

    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (MIN_AREA <= area <= MAX_AREA):
            continue
        if not (MIN_SIDE <= w <= MAX_SIDE and MIN_SIDE <= h <= MAX_SIDE):
            continue
        if max(w, h) / max(min(w, h), 1) > MAX_ASPECT:
            continue
        if x < MARGIN or y < MARGIN or (x + w) > W - MARGIN or (y + h) > H - MARGIN:
            continue

        comp = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        cnt = max(contours, key=cv2.contourArea)
        c_area = float(cv2.contourArea(cnt))
        if c_area < MIN_AREA * 0.75:
            continue
        hull = cv2.convexHull(cnt)
        hull_area = float(cv2.contourArea(hull)) or 1.0
        if c_area / hull_area < MIN_SOLIDITY:
            continue

        rect = cv2.minAreaRect(cnt)
        (cx, cy), (rw, rh), _ang = rect
        side_a, side_b = sorted([rw, rh])
        if side_a < MIN_SIDE or side_b > MAX_SIDE:
            continue
        if side_b / max(side_a, 1) > MAX_ASPECT:
            continue

        # Reject road scraps: rect fill should stay mostly bright
        box = cv2.boxPoints(rect)
        box_i = np.int32(box)
        probe = np.zeros((H, W), dtype=np.uint8)
        cv2.fillConvexPoly(probe, box_i, 255)
        ys, xs = np.where(probe > 0)
        if len(xs) < 20:
            continue
        mean_g = float(gray[ys, xs].mean())
        if mean_g < 150:
            continue
        dark_frac = float((gray[ys, xs] < INK_THRESH).mean())
        if dark_frac > 0.22:
            continue
        bright_frac = float((gray[ys, xs] > 180).mean())
        # Shaded lots are mid-gray; allow either bright or mid fill dominance
        mid_frac = float(((gray[ys, xs] >= 135) & (gray[ys, xs] <= 178)).mean())
        if bright_frac + mid_frac < 0.75:
            continue

        box = shrink_quad(box, SHRINK)
        icx, icy = int(round(cx)), int(round(cy))
        if not (MARGIN <= icx < W - MARGIN and MARGIN <= icy < H - MARGIN):
            continue
        if gray[icy, icx] < 140:
            continue

        pts = order_quad([[r4(float(px) / W), r4(float(py) / H)] for px, py in box])
        lots.append(
            {
                "points": pts,
                "cx": r4(float(cx) / W),
                "cy": r4(float(cy) / H),
                "area": r4((side_a * side_b) / (W * H)),
            }
        )
        debug_quads.append(np.int32(box))

    paired = sorted(zip(lots, debug_quads), key=lambda t: (t[0]["cy"], t[0]["cx"]))
    return [t[0] for t in paired], [t[1] for t in paired]


def write_debug(rgb: np.ndarray, quads: list[np.ndarray]) -> None:
    out = rgb.copy()
    for q in quads:
        cv2.polylines(out, [q.reshape(-1, 1, 2)], True, (0, 200, 255), 1, cv2.LINE_AA)
    Image.fromarray(out).save(DEBUG_PATH)


def main() -> None:
    if not IMG_PATH.exists():
        print(f"Missing image: {IMG_PATH}", file=sys.stderr)
        sys.exit(1)

    rgb = np.array(Image.open(IMG_PATH).convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    H, W = gray.shape

    lots, quads = detect_lots(gray)
    OUT_PATH.write_text(
        json.dumps({"image": {"w": W, "h": H}, "lots": lots}, indent=2),
        encoding="utf-8",
    )
    empty = {"blocks": {}}
    SLOTS_PATH.write_text(json.dumps(empty, indent=2) + "\n", encoding="utf-8")
    CLUSTERS_PATH.write_text(json.dumps(empty, indent=2) + "\n", encoding="utf-8")
    write_debug(rgb, quads)

    if lots:
        sides = [np.sqrt(L["area"] * W * H) for L in lots]
        print(
            f"Image {W}x{H}; lots={len(lots)}; median~{float(np.median(sides)):.1f}px",
            file=sys.stderr,
        )
    print(f"Wrote {OUT_PATH}", file=sys.stderr)
    print(f"QA {DEBUG_PATH}", file=sys.stderr)
    if len(lots) < 80:
        print("WARNING: low lot count", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
