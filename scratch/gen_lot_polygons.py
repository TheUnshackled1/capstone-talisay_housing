"""
Detect lot fill regions on static/images/lot_plan_roads.png and write
static/units/lot_plan_polygons.json.

Multi-pass ink thresholds recover missed cells; AABB-IoU dedupes.
Drops cul-de-sac / circular marker traces. No block/lot labels.

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
SHRINK = 0.85
IOU_DEDUP = 0.35


def r4(v: float) -> float:
    return round(float(v), 4)


def find_map_circles(gray: np.ndarray) -> np.ndarray:
    """Detect drawn circular markers (cul-de-sacs / junctions)."""
    blur = cv2.medianBlur(gray, 5)
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=18,
        param1=85,
        param2=24,
        minRadius=5,
        maxRadius=16,
    )
    if circles is None:
        return np.zeros((0, 3), dtype=np.float32)
    return circles[0].astype(np.float32)


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
        peri = float(cv2.arcLength(cnt, True)) or 1.0
        circularity = 4.0 * np.pi * c_area / (peri * peri)
        # Only reject clearly circular marker blobs (not rectangular lots)
        if circularity >= 0.85 and max(w, h) <= 28:
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


def drop_circle_traces(
    lots: list[dict],
    quads: list[np.ndarray],
    circles: np.ndarray,
    shape: tuple[int, int],
) -> tuple[list[dict], list[np.ndarray]]:
    """Remove traces that are the circular markers themselves — keep real rectangular lots."""
    if circles.size == 0:
        return lots, quads
    H, W = shape
    kept_lots: list[dict] = []
    kept_quads: list[np.ndarray] = []
    for lot, quad in zip(lots, quads):
        lx, ly = lot["cx"] * W, lot["cy"] * H
        bw = float(quad[:, 0].max() - quad[:, 0].min())
        bh = float(quad[:, 1].max() - quad[:, 1].min())
        aspect = max(bw, bh) / max(min(bw, bh), 1.0)
        # Real lots are usually elongated enough — never drop those
        if aspect >= 1.35 and min(bw, bh) >= 12:
            kept_lots.append(lot)
            kept_quads.append(quad)
            continue
        drop = False
        for cx, cy, r in circles:
            dist = float(np.hypot(lx - cx, ly - cy))
            # Compact blob centered on marker
            if aspect <= 1.35 and max(bw, bh) <= float(r) * 2.8:
                if dist <= max(6.0, float(r) * 1.05):
                    drop = True
                    break
            # Any lot whose center sits inside the marker disk
            if dist <= float(r) * 0.75 and max(bw, bh) <= float(r) * 3.2:
                drop = True
                break
        if drop:
            continue
        kept_lots.append(lot)
        kept_quads.append(quad)
    return kept_lots, kept_quads


def mask_out_circles(mask: np.ndarray, circles: np.ndarray, pad: int = 3) -> np.ndarray:
    """Erase fill under circular markers so they never become lot traces."""
    if circles.size == 0:
        return mask
    out = mask.copy()
    for cx, cy, r in circles:
        cv2.circle(out, (int(round(cx)), int(round(cy))), int(round(r)) + pad, 0, -1)
    return out


def lot_from_seed(gray: np.ndarray, sx: float, sy: float, approx_side: float) -> tuple[dict, np.ndarray] | None:
    """Build a shrunk axis-aligned-ish quad locked to the seed (no flood leak)."""
    H, W = gray.shape
    x, y = int(round(sx)), int(round(sy))
    if not (MARGIN + 2 <= x < W - MARGIN - 2 and MARGIN + 2 <= y < H - MARGIN - 2):
        return None
    if gray[y, x] < 125:
        return None

    ink = (gray < 108).astype(np.uint8)
    half = max(8.0, min(approx_side * 0.7, 28.0))
    extents = []
    for ang in (0.0, 90.0, 180.0, 270.0):
        rad = np.deg2rad(ang)
        hit = half
        for t in np.linspace(3.0, half, 20):
            xx = int(round(sx + t * np.cos(rad)))
            yy = int(round(sy + t * np.sin(rad)))
            if not (0 <= xx < W and 0 <= yy < H) or ink[yy, xx]:
                hit = t
                break
        extents.append(hit)

    right, down, left, up = extents
    right = right if right < half * 0.95 else approx_side * 0.45
    left = left if left < half * 0.95 else approx_side * 0.45
    down = down if down < half * 0.95 else approx_side * 0.40
    up = up if up < half * 0.95 else approx_side * 0.40

    pad = 0.88
    x0 = sx - left * pad
    x1 = sx + right * pad
    y0 = sy - up * pad
    y1 = sy + down * pad
    bw = x1 - x0
    bh = y1 - y0
    if bw < MIN_SIDE - 1 or bh < MIN_SIDE - 1:
        return None
    if max(bw, bh) / max(min(bw, bh), 1) > MAX_ASPECT:
        return None
    if bw * bh > MAX_AREA * 1.2 or bw * bh < MIN_AREA * 0.45:
        return None

    box = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32)
    box = shrink_quad(box, 0.97)
    icx, icy = int(round(sx)), int(round(sy))
    if gray[icy, icx] < 115:
        return None

    pts = order_quad([[r4(float(px) / W), r4(float(py) / H)] for px, py in box])
    lot = {
        "points": pts,
        "cx": r4(sx / W),
        "cy": r4(sy / H),
        "area": r4((bw * bh) / (W * H)),
    }
    return lot, box.astype(np.float32)


def _enclosure_hits(gray: np.ndarray, sx: float, sy: float, med: float) -> int:
    H, W = gray.shape
    ink = (gray < 108).astype(np.uint8)
    hits = 0
    for ang in (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0):
        rad = np.deg2rad(ang)
        for t in np.linspace(med * 0.28, med * 0.70, 10):
            xx = int(round(sx + t * np.cos(rad)))
            yy = int(round(sy + t * np.sin(rad)))
            if not (0 <= xx < W and 0 <= yy < H):
                break
            if ink[yy, xx]:
                hits += 1
                break
    return hits



def is_road_center(gray: np.ndarray, sx: float, sy: float, med: float) -> bool:
    """True if seed sits in an open road / empty field rather than a lot cell."""
    H, W = gray.shape
    ix, iy = int(round(sx)), int(round(sy))
    if not (0 <= ix < W and 0 <= iy < H):
        return True
    g = int(gray[iy, ix])
    hits = _enclosure_hits(gray, sx, sy, med)

    # Mid-gray: real shaded lots have ink walls; empty fields do not.
    if 130 <= g <= 178:
        return hits <= 2

    ink = (gray < 108).astype(np.uint8)
    clear_dirs = 0
    max_clear = 0
    for ang in (0.0, 90.0, 180.0, 270.0):
        rad = np.deg2rad(ang)
        clear = 0
        for t in range(2, int(med * 2.5)):
            xx = int(round(sx + t * np.cos(rad)))
            yy = int(round(sy + t * np.sin(rad)))
            if not (0 <= xx < W and 0 <= yy < H):
                break
            if ink[yy, xx]:
                break
            clear += 1
        max_clear = max(max_clear, clear)
        if clear >= int(med * 1.35):
            clear_dirs += 1
    if clear_dirs >= 2:
        return True
    # Bright open strip with weak walls = road
    if g >= 185 and max_clear >= int(med * 1.5) and hits < 6:
        return True
    if hits < 5:
        return True
    return False


def _shaded_mask(gray: np.ndarray) -> np.ndarray:
    ink = (gray < 100).astype(np.uint8) * 255
    ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
    shaded = ((gray >= 130) & (gray <= 178)).astype(np.uint8) * 255
    shaded = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
    return cv2.morphologyEx(shaded, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1)


def drop_merged_shaded(
    lots: list[dict],
    quads: list[np.ndarray],
    gray: np.ndarray,
) -> tuple[list[dict], list[np.ndarray]]:
    """Drop oversized mid-gray traces that swallowed multiple shaded cells."""
    H, W = gray.shape
    med_area = float(np.median([L["area"] for L in lots])) if lots else 0.001
    kept_lots: list[dict] = []
    kept_quads: list[np.ndarray] = []
    for lot, quad in zip(lots, quads):
        sx, sy = lot["cx"] * W, lot["cy"] * H
        ix, iy = int(round(sx)), int(round(sy))
        g = int(gray[iy, ix]) if 0 <= ix < W and 0 <= iy < H else 0
        # Merged shaded blob: mid-gray center + area well above typical lot
        if 130 <= g <= 178 and lot["area"] >= max(0.0020, med_area * 1.85):
            continue
        kept_lots.append(lot)
        kept_quads.append(quad)
    return kept_lots, kept_quads


def drop_open_field(
    lots: list[dict],
    quads: list[np.ndarray],
    gray: np.ndarray,
) -> tuple[list[dict], list[np.ndarray]]:
    """Remove ghost boxes in empty mid-gray regions (no drawn lot walls)."""
    H, W = gray.shape
    sides = [np.sqrt(L["area"] * W * H) for L in lots] or [21.0]
    med = float(np.median(sides))
    kept_lots: list[dict] = []
    kept_quads: list[np.ndarray] = []
    for lot, quad in zip(lots, quads):
        sx, sy = lot["cx"] * W, lot["cy"] * H
        ix, iy = int(round(sx)), int(round(sy))
        if not (0 <= ix < W and 0 <= iy < H):
            continue
        g = int(gray[iy, ix])
        hits = _enclosure_hits(gray, sx, sy, med)
        # Empty field: mid-gray + almost no surrounding ink walls
        if 130 <= g <= 178 and hits <= 2:
            continue
        # Tiny mid-gray crumbs from aggressive recovery
        if 130 <= g <= 178 and lot["area"] < 0.00055 and hits <= 4:
            continue
        kept_lots.append(lot)
        kept_quads.append(quad)
    return kept_lots, kept_quads


def dedupe_close_centers(
    lots: list[dict],
    quads: list[np.ndarray],
    min_dist: float = 12.0,
) -> tuple[list[dict], list[np.ndarray]]:
    """Keep larger lot when two centers land almost on top of each other."""
    order = sorted(range(len(lots)), key=lambda i: -lots[i]["area"])
    kept_idx: list[int] = []
    centers: list[tuple[float, float]] = []
    for i in order:
        q = quads[i]
        px = float(q[:, 0].mean())
        py = float(q[:, 1].mean())
        if any((px - ox) ** 2 + (py - oy) ** 2 < min_dist**2 for ox, oy in centers):
            continue
        centers.append((px, py))
        kept_idx.append(i)
    kept_idx.sort(key=lambda i: (lots[i]["cy"], lots[i]["cx"]))
    return [lots[i] for i in kept_idx], [quads[i] for i in kept_idx]


def recover_shaded_lots(
    gray: np.ndarray,
    lots: list[dict],
    quads: list[np.ndarray],
) -> tuple[list[dict], list[np.ndarray]]:
    """Recover enclosed mid-gray lot cells only (never empty open fields)."""
    H, W = gray.shape
    cov = np.zeros((H, W), dtype=np.uint8)
    for q in quads:
        cv2.fillConvexPoly(cov, np.int32(q), 255)

    shaded = _shaded_mask(gray)
    # Thick hatch merges cells — light erode to split, then seed each enclosed cell
    split = cv2.erode(shaded, np.ones((3, 3), np.uint8), 1)
    n, _labels, stats, cents = cv2.connectedComponentsWithStats(split, connectivity=8)

    sides = [np.sqrt(L["area"] * W * H) for L in lots] or [21.0]
    med = float(np.median(sides))

    seeds: list[tuple[float, float]] = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (80 <= area <= 900):
            continue
        if not (8 <= w <= 55 and 8 <= h <= 55):
            continue
        if max(w, h) / max(min(w, h), 1) > 2.8:
            continue
        cx, cy = float(cents[i][0]), float(cents[i][1])
        ix, iy = int(round(cx)), int(round(cy))
        if not (MARGIN + 2 <= ix < W - MARGIN - 2 and MARGIN + 2 <= iy < H - MARGIN - 2):
            continue
        if cov[iy, ix]:
            continue
        if not (130 <= int(gray[iy, ix]) <= 178):
            continue
        # Must look like a real lot cell (ink on most sides) — kills empty fields
        if _enclosure_hits(gray, cx, cy, med) < 4:
            continue
        seeds.append((cx, cy))

    if not seeds:
        return lots, quads
    return force_seed_lots(gray, lots, quads, seeds)


def drop_road_traces(
    lots: list[dict],
    quads: list[np.ndarray],
    gray: np.ndarray,
) -> tuple[list[dict], list[np.ndarray]]:
    """Remove false boxes that landed in road corridors."""
    H, W = gray.shape
    sides = [np.sqrt(L["area"] * W * H) for L in lots] or [21.0]
    med = float(np.median(sides))
    kept_lots: list[dict] = []
    kept_quads: list[np.ndarray] = []
    for lot, quad in zip(lots, quads):
        sx, sy = lot["cx"] * W, lot["cy"] * H
        if is_road_center(gray, sx, sy, med):
            continue
        kept_lots.append(lot)
        kept_quads.append(quad)
    return kept_lots, kept_quads


def force_seed_lots(
    gray: np.ndarray,
    lots: list[dict],
    quads: list[np.ndarray],
    seeds: list[tuple[float, float]],
) -> tuple[list[dict], list[np.ndarray]]:
    """Add a few known missing lot cells (oriented from nearest neighbor)."""
    if not seeds or not lots:
        return lots, quads
    H, W = gray.shape
    sides = [np.sqrt(L["area"] * W * H) for L in lots]
    med = float(np.median(sides))
    centers = np.array([[L["cx"] * W, L["cy"] * H] for L in lots], dtype=np.float64)

    extra: list[tuple[dict, np.ndarray]] = []
    for sx, sy in seeds:
        ix, iy = int(round(sx)), int(round(sy))
        if not (MARGIN <= ix < W - MARGIN and MARGIN <= iy < H - MARGIN):
            continue
        g0 = int(gray[iy, ix])
        shaded_seed = 130 <= g0 <= 178
        # Bright lots need >=140; shaded mid-gray cells are valid from 130
        if g0 < (130 if shaded_seed else 140):
            continue
        if is_road_center(gray, sx, sy, med):
            continue
        if shaded_seed and _enclosure_hits(gray, sx, sy, med) < 4:
            continue
        # Nudge only for near-ink bright lots — keep shaded mid-gray seeds put
        if not shaded_seed and g0 < 160:
            best = (ix, iy, g0)
            for yy in range(iy - 5, iy + 6):
                for xx in range(ix - 5, ix + 6):
                    if 0 <= xx < W and 0 <= yy < H and int(gray[yy, xx]) > best[2]:
                        best = (xx, yy, int(gray[yy, xx]))
            if best[2] >= 155 and not is_road_center(gray, float(best[0]), float(best[1]), med):
                sx, sy = float(best[0]), float(best[1])
            else:
                continue
        d2 = (centers[:, 0] - sx) ** 2 + (centers[:, 1] - sy) ** 2
        ni = int(np.argmin(d2))
        covered = False
        for q in quads:
            if cv2.pointPolygonTest(q.astype(np.float32), (float(sx), float(sy)), False) >= 0:
                covered = True
                break
        if covered:
            continue
        ref = lots[ni]
        ref_pts = np.array(ref["points"], dtype=float) * np.array([W, H])
        edges = np.array([b - a for a, b in zip(ref_pts, np.roll(ref_pts, -1, axis=0))])
        lengths = np.linalg.norm(edges, axis=1)
        ux = edges[int(np.argmax(lengths))]
        ux = ux / (np.linalg.norm(ux) + 1e-9)
        uy = np.array([-ux[1], ux[0]])
        side = float(sides[ni])
        # Slightly tighter boxes for shaded cells so they stay inside thick borders
        scale = 0.88 if shaded_seed else 1.0
        half_w, half_h = side * 0.45 * scale, side * 0.40 * scale
        box = np.array(
            [
                [sx, sy] - ux * half_w - uy * half_h,
                [sx, sy] + ux * half_w - uy * half_h,
                [sx, sy] + ux * half_w + uy * half_h,
                [sx, sy] - ux * half_w + uy * half_h,
            ],
            dtype=np.float32,
        )
        box = shrink_quad(box, SHRINK if not shaded_seed else max(SHRINK, 0.80))
        if any(aabb_iou(box, q.astype(np.float32)) >= IOU_DEDUP for q in quads):
            continue
        if any(aabb_iou(box, eb) >= IOU_DEDUP for _, eb in extra):
            continue
        pts_n = order_quad([[r4(float(px) / W), r4(float(py) / H)] for px, py in box])
        lot = {
            "points": pts_n,
            "cx": r4(sx / W),
            "cy": r4(sy / H),
            "area": r4((half_w * 2 * half_h * 2) / (W * H)),
        }
        extra.append((lot, box))

    if not extra:
        return lots, quads
    for lot, box in extra:
        lots.append(lot)
        quads.append(np.int32(box))
    order = sorted(range(len(lots)), key=lambda i: (lots[i]["cy"], lots[i]["cx"]))
    return [lots[i] for i in order], [quads[i] for i in order]


def detect_lots(gray: np.ndarray) -> tuple[list[dict], list[np.ndarray], np.ndarray]:
    masks = [
        build_mask(gray, dilate=3, close=True, bright_t=185, ink_t=90),
        build_mask(gray, dilate=2, close=True, bright_t=178, ink_t=100),
        build_mask(gray, dilate=2, close=False, bright_t=170, ink_t=110),
        build_mask(gray, dilate=2, close=True, bright_t=155, ink_t=70),
        build_mask(gray, dilate=1, close=False, bright_t=160, ink_t=120),
    ]
    cands: list[tuple[dict, np.ndarray]] = []
    for m in masks:
        cands.extend(extract_from_mask(gray, m))
    lots, quads = dedupe(cands)

    circles = find_map_circles(gray)

    lots, quads = drop_circle_traces(lots, quads, circles, gray.shape)
    before_road = len(lots)
    lots, quads = drop_road_traces(lots, quads, gray)
    print(f"dropped road FPs -{before_road - len(lots)}", file=sys.stderr)
    before_field = len(lots)
    lots, quads = drop_open_field(lots, quads, gray)
    print(f"dropped open-field FPs -{before_field - len(lots)}", file=sys.stderr)
    before_merge = len(lots)
    lots, quads = drop_merged_shaded(lots, quads, gray)
    print(f"dropped merged shaded -{before_merge - len(lots)}", file=sys.stderr)
    before_sh = len(lots)
    lots, quads = recover_shaded_lots(gray, lots, quads)
    print(f"shaded recovery +{len(lots) - before_sh}", file=sys.stderr)
    before = len(lots)
    lots, quads = force_seed_lots(gray, lots, quads, [(163.4, 407.4)])
    print(f"surgical seeds +{len(lots) - before}", file=sys.stderr)
    before_c = len(lots)
    lots, quads = drop_circle_traces(lots, quads, circles, gray.shape)
    lots, quads = drop_road_traces(lots, quads, gray)
    lots, quads = drop_open_field(lots, quads, gray)
    lots, quads = dedupe_close_centers(lots, quads, min_dist=12.0)
    print(f"final cleanup -{before_c - len(lots)}", file=sys.stderr)
    return lots, quads, circles


def write_debug(rgb: np.ndarray, quads: list[np.ndarray], circles: np.ndarray) -> None:
    out = rgb.copy()
    for q in quads:
        cv2.polylines(out, [q.reshape(-1, 1, 2)], True, (0, 200, 255), 1, cv2.LINE_AA)
    for cx, cy, r in circles.astype(int):
        cv2.circle(out, (int(cx), int(cy)), int(r), (0, 80, 255), 1, cv2.LINE_AA)
    Image.fromarray(out).save(DEBUG_PATH)


def main() -> None:
    if not IMG_PATH.exists():
        print(f"Missing image: {IMG_PATH}", file=sys.stderr)
        sys.exit(1)

    rgb = np.array(Image.open(IMG_PATH).convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    H, W = gray.shape

    lots, quads, circles = detect_lots(gray)
    OUT_PATH.write_text(
        json.dumps({"image": {"w": W, "h": H}, "lots": lots}, indent=2),
        encoding="utf-8",
    )
    empty = {"blocks": {}}
    SLOTS_PATH.write_text(json.dumps(empty, indent=2) + "\n", encoding="utf-8")
    CLUSTERS_PATH.write_text(json.dumps(empty, indent=2) + "\n", encoding="utf-8")
    write_debug(rgb, quads, circles)

    if lots:
        sides = [np.sqrt(L["area"] * W * H) for L in lots]
        print(
            f"Image {W}x{H}; lots={len(lots)}; circles={len(circles)}; "
            f"median~{float(np.median(sides)):.1f}px",
            file=sys.stderr,
        )
    print(f"Wrote {OUT_PATH}", file=sys.stderr)
    print(f"QA {DEBUG_PATH}", file=sys.stderr)
    if len(lots) < 100:
        print("WARNING: low lot count", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
