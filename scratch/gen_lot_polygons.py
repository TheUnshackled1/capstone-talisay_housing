"""
Detect lot fill regions on static/images/lot_plan_roads.png and write
static/units/lot_plan_polygons.json.

Multi-pass ink thresholds recover missed cells; AABB-IoU dedupes.
Rotated quads follow tilted lots. No block/lot labels.

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

MIN_AREA = 100
MAX_AREA = 3600
MIN_SIDE = 9
MAX_SIDE = 95
MAX_ASPECT = 3.6
MIN_SOLIDITY = 0.55
MARGIN = 4
SHRINK = 0.92
IOU_DEDUP = 0.35


def r4(v: float) -> float:
    return round(float(v), 4)


def build_mask(gray: np.ndarray, *, dilate: int, close: bool, bright_t: int, ink_t: int) -> np.ndarray:
    bright = (gray > bright_t).astype(np.uint8) * 255
    mid = ((gray >= 120) & (gray <= 185)).astype(np.uint8) * 255
    ink = (gray < ink_t).astype(np.uint8) * 255
    ink = cv2.dilate(ink, np.ones((dilate, dilate), np.uint8), iterations=1)
    if close:
        ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    fill = cv2.bitwise_or(bright, mid)
    mask = cv2.bitwise_and(fill, cv2.bitwise_not(ink))
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)


def shrink_quad(pts: np.ndarray, factor: float) -> np.ndarray:
    c = pts.mean(axis=0)
    return c + (pts - c) * factor


def order_quad(pts: list[list[float]]) -> list[list[float]]:
    arr = np.array(pts, dtype=float)
    angles = np.arctan2(arr[:, 1] - arr[:, 1].mean(), arr[:, 0] - arr[:, 0].mean())
    return [pts[int(j)] for j in np.argsort(angles)]


def aabb_iou(a: np.ndarray, b: np.ndarray) -> float:
    ax1, ay1 = float(a[:, 0].min()), float(a[:, 1].min())
    ax2, ay2 = float(a[:, 0].max()), float(a[:, 1].max())
    bx1, by1 = float(b[:, 0].min()), float(b[:, 1].min())
    bx2, by2 = float(b[:, 0].max()), float(b[:, 1].max())
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-9)


def extract_from_mask(gray: np.ndarray, mask: np.ndarray) -> list[tuple[dict, np.ndarray]]:
    H, W = gray.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    out: list[tuple[dict, np.ndarray]] = []

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
        if c_area < MIN_AREA * 0.6:
            continue
        hull_area = float(cv2.contourArea(cv2.convexHull(cnt))) or 1.0
        if c_area / hull_area < MIN_SOLIDITY:
            continue

        rect = cv2.minAreaRect(cnt)
        (cx, cy), (rw, rh), _ang = rect
        side_a, side_b = sorted([rw, rh])
        if side_a < MIN_SIDE - 1 or side_b > MAX_SIDE:
            continue
        if side_b / max(side_a, 1) > MAX_ASPECT:
            continue

        box = cv2.boxPoints(rect)
        probe = np.zeros((H, W), dtype=np.uint8)
        cv2.fillConvexPoly(probe, np.int32(box), 255)
        ys, xs = np.where(probe > 0)
        if len(xs) < 16:
            continue
        vals = gray[ys, xs]
        if float((vals < 95).mean()) > 0.35:
            continue
        bright_frac = float((vals > 175).mean())
        mid_frac = float(((vals >= 120) & (vals <= 185)).mean())
        if bright_frac + mid_frac < 0.55:
            continue

        box = shrink_quad(box, SHRINK)
        icx, icy = int(round(cx)), int(round(cy))
        if not (MARGIN <= icx < W - MARGIN and MARGIN <= icy < H - MARGIN):
            continue
        if gray[icy, icx] < 110:
            continue

        pts = order_quad([[r4(float(px) / W), r4(float(py) / H)] for px, py in box])
        lot = {
            "points": pts,
            "cx": r4(float(cx) / W),
            "cy": r4(float(cy) / H),
            "area": r4((side_a * side_b) / (W * H)),
        }
        out.append((lot, box.astype(np.float32)))
    return out


def dedupe(cands: list[tuple[dict, np.ndarray]]) -> tuple[list[dict], list[np.ndarray]]:
    cands = sorted(cands, key=lambda t: -t[0]["area"])
    kept: list[tuple[dict, np.ndarray]] = []
    for lot, box in cands:
        if any(aabb_iou(box, kbox) >= IOU_DEDUP for _, kbox in kept):
            continue
        kept.append((lot, box))
    kept.sort(key=lambda t: (t[0]["cy"], t[0]["cx"]))
    return [t[0] for t in kept], [np.int32(t[1]) for t in kept]


def detect_lots(gray: np.ndarray) -> tuple[list[dict], list[np.ndarray]]:
    masks = [
        build_mask(gray, dilate=3, close=True, bright_t=185, ink_t=90),
        build_mask(gray, dilate=2, close=True, bright_t=178, ink_t=100),
        build_mask(gray, dilate=2, close=False, bright_t=170, ink_t=110),
        # Shaded/hatched lots: ignore light hatch ink, keep real borders only
        build_mask(gray, dilate=2, close=True, bright_t=155, ink_t=70),
    ]
    cands: list[tuple[dict, np.ndarray]] = []
    for m in masks:
        cands.extend(extract_from_mask(gray, m))
    return dedupe(cands)


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
    if len(lots) < 100:
        print("WARNING: low lot count", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
