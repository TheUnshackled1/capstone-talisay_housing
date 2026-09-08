"""
Phase 2 lot polygons — fill-region detector (matches drawn lot sizes).

Detects light lot interiors as connected components, fits axis-aligned
rects, filters to Phase-1-like sizes. Writes JSON + debug overlay.

Run: python scratch/gen_p2_polygons_v3.py
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import defaultdict

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).parent.parent
IMG_PATH = ROOT / "static" / "images" / "lot_plan_roads_p2.png"
OUT_PATH = ROOT / "static" / "units" / "lot_plan_polygons_p2.json"
DEBUG_PATH = ROOT / "scratch" / "p2_polygons_debug.png"

# Match Phase 1 lot scale (~39x24 median) — allow variance for P2 drawing
MIN_W, MAX_W = 12, 90
MIN_H, MAX_H = 12, 90
MIN_AREA, MAX_AREA = 180, 5500
MAX_ASPECT = 5.5
# How much of bbox must be "lot fill" (rejects road-straddling blobs)
FILL_RATIO = 0.62


def r4(v: float) -> float:
    return round(float(v), 4)


def _rects_from_mask(mask: np.ndarray, W: int, H: int) -> list[tuple]:
    n, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
    rects = []
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if not (MIN_AREA <= area <= MAX_AREA):
            continue
        if not (MIN_W <= w <= MAX_W and MIN_H <= h <= MAX_H):
            continue
        aspect = max(w / max(h, 1), h / max(w, 1))
        if aspect > MAX_ASPECT:
            continue
        if area / max(w * h, 1) < FILL_RATIO:
            continue
        x1, y1 = x + 1, y + 1
        x2, y2 = x + w - 2, y + h - 2
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue
        cx, cy = float(centroids[i][0]), float(centroids[i][1])
        if cx < 20 or cy < 20 or cx > W - 20 or cy > H - 20:
            continue
        rects.append((x1, y1, x2, y2, cx, cy))
    return rects


def detect_rects(gray: np.ndarray) -> list[tuple]:
    """Return list of (x1,y1,x2,y2,cx,cy) for lot-sized light regions."""
    H, W = gray.shape
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    ink = (blur < 145).astype(np.uint8) * 255
    ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), iterations=1)

    merged: list[tuple] = []
    for thr in (190, 205, 175):
        _, bright = cv2.threshold(blur, thr, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_and(bright, cv2.bitwise_not(ink))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
        for r in _rects_from_mask(mask, W, H):
            if any(abs(r[4] - m[4]) < 8 and abs(r[5] - m[5]) < 8 for m in merged):
                continue
            merged.append(r)
    return merged


def cluster_blocks(rects: list, W: int, H: int) -> list[list]:
    """Group lots into spatial blocks via occupancy-grid CC."""
    if not rects:
        return []
    cell = 40
    gw, gh = W // cell + 2, H // cell + 2
    grid = np.zeros((gh, gw), dtype=np.uint8)
    for _x1, _y1, _x2, _y2, cx, cy in rects:
        gx, gy = int(cx) // cell, int(cy) // cell
        if 0 <= gy < gh and 0 <= gx < gw:
            grid[gy, gx] = 255
    # Light dilate — keep separate block clusters apart across roads
    grid = cv2.dilate(grid, np.ones((2, 2), np.uint8), iterations=1)
    _nlab, lab = cv2.connectedComponents(grid, connectivity=8)
    groups: dict[int, list] = defaultdict(list)
    for r in rects:
        gx, gy = int(r[4]) // cell, int(r[5]) // cell
        if 0 <= gy < gh and 0 <= gx < gw and lab[gy, gx] != 0:
            groups[int(lab[gy, gx])].append(r)
        else:
            groups[-1].append(r)
    blocks = [g for lbl, g in groups.items() if lbl > 0 and g]
    mid_x, mid_y = W * 0.49, H * 0.49

    def bkey(g):
        cx = sum(r[4] for r in g) / len(g)
        cy = sum(r[5] for r in g) / len(g)
        q = (0 if cy < mid_y else 2) + (0 if cx < mid_x else 1)
        return (q, cy, cx)

    blocks.sort(key=bkey)
    return blocks


def main() -> None:
    bgr = cv2.imread(str(IMG_PATH))
    if bgr is None:
        raise SystemExit(f"Cannot read {IMG_PATH}")
    H, W = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    rects = detect_rects(gray)
    print(f"Image {W}x{H}; detected lot rects={len(rects)}", file=sys.stderr)

    blocks = cluster_blocks(rects, W, H)
    print(f"Blocks={len(blocks)}", file=sys.stderr)

    lots_out = []
    debug = bgr.copy()
    start_block = 22
    row_tol = 14

    for bi, group in enumerate(blocks):
        block_num = start_block + bi
        group = sorted(group, key=lambda r: (round(r[5] / row_tol) * row_tol, r[4]))
        print(f"  Block {block_num}: {len(group)} lots", file=sys.stderr)
        for lot_num, (x1, y1, x2, y2, _cx, _cy) in enumerate(group, start=1):
            nx1, ny1 = r4(x1 / W), r4(y1 / H)
            nx2, ny2 = r4(x2 / W), r4(y2 / H)
            lots_out.append({
                "points": [[nx1, ny1], [nx2, ny1], [nx2, ny2], [nx1, ny2]],
                "cx": r4((nx1 + nx2) / 2),
                "cy": r4((ny1 + ny2) / 2),
                "area": r4((nx2 - nx1) * (ny2 - ny1)),
                "block": block_num,
                "lot": lot_num,
            })
            cv2.rectangle(debug, (int(x1), int(y1)), (int(x2), int(y2)), (40, 140, 255), 1)

    OUT_PATH.write_text(json.dumps({"image": {"w": W, "h": H}, "lots": lots_out}, indent=2))
    cv2.imwrite(str(DEBUG_PATH), debug)
    print(f"\nTotal: {len(lots_out)} lots → {OUT_PATH}", file=sys.stderr)
    print(f"Debug → {DEBUG_PATH}", file=sys.stderr)
    if lots_out:
        ws = [(l["points"][1][0] - l["points"][0][0]) * W for l in lots_out]
        hs = [(l["points"][2][1] - l["points"][1][1]) * H for l in lots_out]
        print(
            f"Size px median {sorted(ws)[len(ws)//2]:.0f}x{sorted(hs)[len(hs)//2]:.0f} "
            f"(range {min(ws):.0f}x{min(hs):.0f} .. {max(ws):.0f}x{max(hs):.0f})",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
