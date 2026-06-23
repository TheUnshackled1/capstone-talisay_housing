"""Trace lot polygons from the GK Cabatangan lot plan raster.

Reads ``static/images/lot_plan.png`` (a clean line drawing of the subdivision),
detects each enclosed lot cell, simplifies it to a polygon, normalizes the
vertices to 0..1 of the image, and writes ``static/units/lot_plan_polygons.json``.

The line drawing has no labels/scale, so this only recovers the *shape* of each
lot. Identity (which lot is "Block 2 Lot 7") is assigned later, on the frontend,
by spatial reading order.

Build-time only: requires ``opencv-python-headless`` and ``numpy``. The Django
runtime never imports this; it consumes the generated JSON instead.

Usage:
    python scripts/trace_lot_plan.py [--debug]

``--debug`` also writes ``static/units/lot_plan_debug.png`` with the detected
polygons drawn over the original image so coverage can be eyeballed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
IMG_PATH = BASE_DIR / "static" / "images" / "lot_plan.png"
OUT_PATH = BASE_DIR / "static" / "units" / "lot_plan_polygons.json"
DEBUG_PATH = BASE_DIR / "static" / "units" / "lot_plan_debug.png"

# --- Detection tuning knobs -------------------------------------------------
# Pixels darker than this are treated as drawn lines (walls between lots).
LINE_THRESHOLD = 200
# A detected cell must cover at least this fraction of the image to be a lot
# (drops anti-alias specks and dot noise).
MIN_AREA_FRAC = 0.00035
# ...and at most this fraction (drops the big outer background / open plazas).
MAX_AREA_FRAC = 0.020
# Roads are long thin ribbons: drop components whose bounding box is extremely
# elongated (w/h or h/w beyond this) AND large.
MAX_ASPECT = 7.0
# Polygon simplification: epsilon as a fraction of each contour's perimeter.
APPROX_EPS_FRAC = 0.012
# Row banding tolerance (fraction of height) used when sorting reading order.
ROW_BAND_FRAC = 0.025


def load_line_mask(gray: np.ndarray) -> np.ndarray:
    """Return a uint8 mask where lot interiors are 255 and lines are 0."""
    # Lines are dark, cells are light. THRESH_BINARY -> cells become 255.
    _, cells = cv2.threshold(gray, LINE_THRESHOLD, 255, cv2.THRESH_BINARY)
    # Seal tiny gaps in the line work so neighbouring cells stay separated.
    # We dilate the *lines* (erode the cells) a touch, then keep cells.
    line = cv2.bitwise_not(cells)
    line = cv2.morphologyEx(
        line, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1
    )
    cells = cv2.bitwise_not(line)
    return cells


def detect_polygons(gray: np.ndarray, debug: bool):
    h, w = gray.shape
    img_area = float(h * w)
    cells = load_line_mask(gray)

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(
        cells, connectivity=4
    )

    min_area = MIN_AREA_FRAC * img_area
    max_area = MAX_AREA_FRAC * img_area
    polys = []

    for i in range(1, num):  # skip label 0 (the line network itself)
        x, y, bw, bh, area = stats[i]
        if area < min_area or area > max_area:
            continue
        # Drop components that touch the image border (outer background slivers).
        if x <= 1 or y <= 1 or (x + bw) >= (w - 1) or (y + bh) >= (h - 1):
            continue
        # Drop very elongated ribbons (roads).
        long_side = max(bw, bh)
        short_side = max(min(bw, bh), 1)
        if long_side / short_side > MAX_ASPECT:
            continue

        mask = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            continue
        cnt = max(contours, key=cv2.contourArea)
        eps = APPROX_EPS_FRAC * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, eps, True).reshape(-1, 2)
        if len(approx) < 3:
            continue

        cx, cy = centroids[i]
        polys.append(
            {
                "pts": approx.astype(float),
                "cx": float(cx),
                "cy": float(cy),
                "area": float(area),
            }
        )

    # Reading order: top-to-bottom in horizontal bands, then left-to-right.
    band = ROW_BAND_FRAC * h
    polys.sort(key=lambda p: (round(p["cy"] / band), p["cx"]))

    lots = []
    for p in polys:
        pts = [[round(px / w, 5), round(py / h, 5)] for px, py in p["pts"]]
        lots.append(
            {
                "points": pts,
                "cx": round(p["cx"] / w, 5),
                "cy": round(p["cy"] / h, 5),
                "area": round(p["area"] / img_area, 6),
            }
        )

    if debug:
        canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        for idx, p in enumerate(polys):
            pts = p["pts"].astype(np.int32)
            cv2.polylines(canvas, [pts], True, (0, 0, 255), 1, cv2.LINE_AA)
            cv2.circle(
                canvas, (int(p["cx"]), int(p["cy"])), 2, (0, 160, 0), -1
            )
        cv2.imwrite(str(DEBUG_PATH), canvas)

    return {"image": {"w": w, "h": h}, "lots": lots}


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace lot polygons from the plan.")
    parser.add_argument("--debug", action="store_true", help="write debug overlay")
    args = parser.parse_args()

    if not IMG_PATH.exists():
        raise SystemExit(f"Plan image not found: {IMG_PATH}")

    img = cv2.imread(str(IMG_PATH), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise SystemExit(f"Could not read image: {IMG_PATH}")

    data = detect_polygons(img, args.debug)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data), encoding="utf-8")

    print(f"Detected {len(data['lots'])} lot polygons -> {OUT_PATH}")
    if args.debug:
        print(f"Debug overlay -> {DEBUG_PATH}")


if __name__ == "__main__":
    main()
