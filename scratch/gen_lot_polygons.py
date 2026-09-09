"""
Detect lot fill regions on static/images/lot_plan_roads.png and write
static/units/lot_plan_polygons.json (normalized points, no block/lot labels).

Also resets slots/clusters to empty blocks (old spatial regions invalid).

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

# Tuned for lot_map.png (906x543, thick black roads, white + shaded lot fills)
BRIGHT_THRESH = 180
MID_GRAY_LO = 130
MID_GRAY_HI = 175
INK_THRESH = 100
MIN_AREA = 90
MAX_AREA = 4500
MIN_SIDE = 8
MAX_SIDE = 95
MARGIN = 6


def r4(v: float) -> float:
    return round(float(v), 4)


def detect_rects(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    H, W = gray.shape
    bright = (gray > BRIGHT_THRESH).astype(np.uint8) * 255
    mid = ((gray >= MID_GRAY_LO) & (gray <= MID_GRAY_HI)).astype(np.uint8) * 255
    ink = (gray < INK_THRESH).astype(np.uint8) * 255
    ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), iterations=1)
    fill = cv2.bitwise_or(bright, mid)
    mask = cv2.bitwise_and(fill, cv2.bitwise_not(ink))

    n, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
    rects: list[tuple[int, int, int, int]] = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (MIN_AREA <= area <= MAX_AREA):
            continue
        if not (MIN_SIDE <= w <= MAX_SIDE and MIN_SIDE <= h <= MAX_SIDE):
            continue
        aspect = max(w, h) / max(min(w, h), 1)
        if aspect > 4.5:
            continue
        x1 = x + 1
        y1 = y + 1
        x2 = x + w - 1
        y2 = y + h - 1
        if x2 - x1 < 6 or y2 - y1 < 6:
            continue
        # Drop thin edge artifacts outside the site drawing
        if x1 < MARGIN or y1 < MARGIN or x2 > W - MARGIN or y2 > H - MARGIN:
            if (x2 - x1) < 12 or (y2 - y1) < 12:
                continue
        rects.append((x1, y1, x2, y2))
    return rects


def rect_to_lot(rect: tuple[int, int, int, int], W: int, H: int) -> dict:
    x1, y1, x2, y2 = rect
    nx1, ny1, nx2, ny2 = x1 / W, y1 / H, x2 / W, y2 / H
    return {
        "points": [
            [r4(nx1), r4(ny1)],
            [r4(nx2), r4(ny1)],
            [r4(nx2), r4(ny2)],
            [r4(nx1), r4(ny2)],
        ],
        "cx": r4((nx1 + nx2) / 2),
        "cy": r4((ny1 + ny2) / 2),
        "area": r4((nx2 - nx1) * (ny2 - ny1)),
    }


def write_debug(rgb: np.ndarray, rects: list[tuple[int, int, int, int]]) -> None:
    out = rgb.copy()
    for x1, y1, x2, y2 in rects:
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 180, 255), 1)
    Image.fromarray(out).save(DEBUG_PATH)


def main() -> None:
    if not IMG_PATH.exists():
        print(f"Missing image: {IMG_PATH}", file=sys.stderr)
        sys.exit(1)

    rgb = np.array(Image.open(IMG_PATH).convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    H, W = gray.shape

    rects = detect_rects(gray)
    # Stable order: top-to-bottom, then left-to-right
    rects.sort(key=lambda r: (r[1], r[0]))

    lots = [rect_to_lot(r, W, H) for r in rects]
    payload = {"image": {"w": W, "h": H}, "lots": lots}
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    empty = {"blocks": {}}
    SLOTS_PATH.write_text(json.dumps(empty, indent=2) + "\n", encoding="utf-8")
    CLUSTERS_PATH.write_text(json.dumps(empty, indent=2) + "\n", encoding="utf-8")

    write_debug(rgb, rects)

    ws = [r[2] - r[0] for r in rects]
    hs = [r[3] - r[1] for r in rects]
    print(f"Image {W}x{H}; lots={len(lots)}", file=sys.stderr)
    if lots:
        print(
            f"Median box ~{float(np.median(ws)):.1f}x{float(np.median(hs)):.1f}px",
            file=sys.stderr,
        )
    print(f"Wrote {OUT_PATH}", file=sys.stderr)
    print(f"QA overlay {DEBUG_PATH}", file=sys.stderr)
    print("Reset slots/clusters to empty blocks", file=sys.stderr)

    if len(lots) < 50:
        print("WARNING: very few lots detected — check thresholds / QA PNG.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
