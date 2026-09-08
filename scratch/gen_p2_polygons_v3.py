"""
Phase 2 lot polygons — fill-region detector (matches drawn lot sizes).

Detects light lot interiors as connected components across multiple
thresholds, fits axis-aligned rects, and writes JSON WITHOUT block/lot
labels (staff enter B/L on Add; map binds via plan_polygon_index).

Also refreshes slots/clusters stubs so stale B13–21 scaffolds cannot
poison spatial assignment.

Run: python scratch/gen_p2_polygons_v3.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).parent.parent
IMG_PATH = ROOT / "static" / "images" / "lot_plan_roads_p2.png"
OUT_PATH = ROOT / "static" / "units" / "lot_plan_polygons_p2.json"
SLOTS_PATH = ROOT / "static" / "units" / "lot_plan_slots_p2.json"
CLUSTERS_PATH = ROOT / "static" / "units" / "lot_plan_clusters_p2.json"
DEBUG_PATH = ROOT / "scratch" / "p2_polygons_debug.png"

# Match Phase 1 lot scale (~39x24 median)
MIN_W, MAX_W = 10, 95
MIN_H, MAX_H = 10, 95
MIN_AREA, MAX_AREA = 140, 6500
MAX_ASPECT = 6.0
FILL_RATIO = 0.55
DEDUP_PX = 7


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
        if x2 - x1 < 7 or y2 - y1 < 7:
            continue
        cx, cy = float(centroids[i][0]), float(centroids[i][1])
        if cx < 16 or cy < 16 or cx > W - 16 or cy > H - 16:
            continue
        rects.append((x1, y1, x2, y2, cx, cy))
    return rects


def detect_rects(gray: np.ndarray) -> list[tuple]:
    H, W = gray.shape
    blur = cv2.GaussianBlur(gray, (3, 3), 0)

    # Thin ink separator so adjacent lots stay distinct
    ink = (blur < 150).astype(np.uint8) * 255
    ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), iterations=1)

    merged: list[tuple] = []

    def accept(r: tuple) -> None:
        if any(abs(r[4] - m[4]) < DEDUP_PX and abs(r[5] - m[5]) < DEDUP_PX for m in merged):
            return
        merged.append(r)

    for thr in (170, 185, 200, 210, 160):
        _, bright = cv2.threshold(blur, thr, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_and(bright, cv2.bitwise_not(ink))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
        for r in _rects_from_mask(mask, W, H):
            accept(r)

    # Contour pass: closed bright regions after stronger ink carve
    ink2 = cv2.dilate((blur < 160).astype(np.uint8) * 255, np.ones((2, 2), np.uint8), iterations=1)
    _, bright2 = cv2.threshold(blur, 188, 255, cv2.THRESH_BINARY)
    mask2 = cv2.bitwise_and(bright2, cv2.bitwise_not(ink2))
    contours, _ = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
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
        if x2 - x1 < 7 or y2 - y1 < 7:
            continue
        cx, cy = x + w / 2.0, y + h / 2.0
        if cx < 16 or cy < 16 or cx > W - 16 or cy > H - 16:
            continue
        accept((x1, y1, x2, y2, cx, cy))

    return merged


def coverage_pct(gray: np.ndarray, rects: list[tuple]) -> float:
    H, W = gray.shape
    bright = gray > 185
    ink = gray < 145
    lotish = bright & ~ink
    cover = np.zeros_like(lotish, dtype=bool)
    for x1, y1, x2, y2, _cx, _cy in rects:
        cover[max(0, y1):min(H, y2 + 1), max(0, x1):min(W, x2 + 1)] = True
    total = int(lotish.sum())
    if not total:
        return 0.0
    return 100.0 * int((lotish & cover).sum()) / total


def main() -> None:
    bgr = cv2.imread(str(IMG_PATH))
    if bgr is None:
        raise SystemExit(f"Cannot read {IMG_PATH}")
    H, W = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    rects = detect_rects(gray)
    # Stable order: top→bottom, left→right
    rects.sort(key=lambda r: (round(r[5] / 12) * 12, r[4]))
    cov = coverage_pct(gray, rects)
    print(f"Image {W}x{H}; lots={len(rects)}; bright coverage≈{cov:.1f}%", file=sys.stderr)

    lots_out = []
    debug = bgr.copy()
    for x1, y1, x2, y2, _cx, _cy in rects:
        nx1, ny1 = r4(x1 / W), r4(y1 / H)
        nx2, ny2 = r4(x2 / W), r4(y2 / H)
        # Intentionally omit block/lot — index-based map binding only
        lots_out.append({
            "points": [[nx1, ny1], [nx2, ny1], [nx2, ny2], [nx1, ny2]],
            "cx": r4((nx1 + nx2) / 2),
            "cy": r4((ny1 + ny2) / 2),
            "area": r4((nx2 - nx1) * (ny2 - ny1)),
        })
        cv2.rectangle(debug, (int(x1), int(y1)), (int(x2), int(y2)), (40, 140, 255), 1)

    payload = {"image": {"w": W, "h": H}, "lots": lots_out}
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    # Neutral stubs — spatial cluster scaffold was wrong for this drawing
    SLOTS_PATH.write_text(json.dumps({"blocks": {}}, indent=2) + "\n")
    CLUSTERS_PATH.write_text(json.dumps({"blocks": {}}, indent=2) + "\n")
    cv2.imwrite(str(DEBUG_PATH), debug)

    print(f"Wrote {len(lots_out)} lots → {OUT_PATH}", file=sys.stderr)
    print(f"Reset slots/clusters stubs → {SLOTS_PATH.name}, {CLUSTERS_PATH.name}", file=sys.stderr)
    print(f"Debug → {DEBUG_PATH}", file=sys.stderr)
    if lots_out:
        ws = [(l["points"][1][0] - l["points"][0][0]) * W for l in lots_out]
        hs = [(l["points"][2][1] - l["points"][1][1]) * H for l in lots_out]
        print(
            f"Size px median {sorted(ws)[len(ws)//2]:.0f}x{sorted(hs)[len(hs)//2]:.0f} "
            f"(range {min(ws):.0f}x{min(hs):.0f} .. {max(ws):.0f}x{max(hs):.0f})",
            file=sys.stderr,
        )
    if cov < 45:
        print(
            "NOTE: raw bright-pixel coverage under 45% often includes courtyards/parks, "
            "not only housing lots — check scratch/p2_polygons_debug.png for QA.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
