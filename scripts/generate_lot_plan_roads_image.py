"""Generate display image with solid black ROAD corridors only.

Keeps the original lot-plan drawing inside each block (white lots, thin walls).
Road corridors are detected as wide white regions between blocks; the hand-
annotated strokes pick which corridors become solid black (gaps filled).

Usage:
    python scripts/generate_lot_plan_roads_image.py
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_PATH = BASE_DIR / "static" / "images" / "lot_plan.png"
ANNOTATED_PATH = BASE_DIR / "static" / "images" / "lot_plan_roads_annotated.png"
BOUNDARY_PATH = BASE_DIR / "static" / "images" / "lot_plan_site_boundary.png"
OUT_PATH = BASE_DIR / "static" / "images" / "lot_plan_roads.png"

LINE_THRESHOLD = 200
MIN_AREA_FRAC = 0.00035
MAX_AREA_FRAC = 0.020
MAX_ASPECT = 7.0

ANNOTATED_DARK_THRESHOLD = 140
MARKER_DILATE_KERNEL = 7
MARKER_DILATE_ITERATIONS = 2
ROAD_CLOSE_KERNEL = 9


def load_line_mask(gray: np.ndarray) -> np.ndarray:
    _, cells = cv2.threshold(gray, LINE_THRESHOLD, 255, cv2.THRESH_BINARY)
    line = cv2.bitwise_not(cells)
    line = cv2.morphologyEx(
        line, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1
    )
    return cv2.bitwise_not(line)


def is_lot_cell(
    area: float, x: int, y: int, bw: int, bh: int, w: int, h: int, img_area: float
) -> bool:
    min_area = MIN_AREA_FRAC * img_area
    max_area = MAX_AREA_FRAC * img_area
    if area < min_area or area > max_area:
        return False
    if x <= 1 or y <= 1 or (x + bw) >= (w - 1) or (y + bh) >= (h - 1):
        return False
    long_side = max(bw, bh)
    short_side = max(min(bw, bh), 1)
    if long_side / short_side > MAX_ASPECT:
        return False
    return True


def build_lot_interior_mask(gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    img_area = float(h * w)
    cells = load_line_mask(gray)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(cells, connectivity=4)
    lot_interior = np.zeros((h, w), dtype=np.uint8)
    for i in range(1, num):
        x, y, bw, bh, area = stats[i]
        if is_lot_cell(float(area), x, y, bw, bh, w, h, img_area):
            lot_interior[labels == i] = 255
    return lot_interior


def build_corridor_components(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """White regions that are not individual lots = road corridors / open space."""
    h, w = gray.shape
    img_area = float(h * w)
    cells = load_line_mask(gray)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(cells, connectivity=4)
    corridor = np.zeros((h, w), dtype=np.uint8)
    for i in range(1, num):
        x, y, bw, bh, area = stats[i]
        if not is_lot_cell(float(area), x, y, bw, bh, w, h, img_area):
            corridor[labels == i] = 255
    return corridor, labels


def build_marker_mask(original_gray: np.ndarray, annotated_gray: np.ndarray) -> np.ndarray:
    """Hand-drawn road strokes only — exclude the original thin lot grid lines."""
    orig_lines = (original_gray < LINE_THRESHOLD).astype(np.uint8) * 255
    orig_lines = cv2.dilate(orig_lines, np.ones((3, 3), np.uint8), iterations=2)
    annot_dark = (annotated_gray < ANNOTATED_DARK_THRESHOLD).astype(np.uint8) * 255
    marker = cv2.bitwise_and(annot_dark, cv2.bitwise_not(orig_lines))
    kernel = np.ones((MARKER_DILATE_KERNEL, MARKER_DILATE_KERNEL), np.uint8)
    return cv2.dilate(marker, kernel, iterations=MARKER_DILATE_ITERATIONS)


def build_road_mask(
    original_gray: np.ndarray,
    annotated_gray: np.ndarray,
) -> np.ndarray:
    """Solid road mask: full corridor components touched by annotated strokes."""
    corridor, labels = build_corridor_components(original_gray)
    marker = build_marker_mask(original_gray, annotated_gray)

    road = np.zeros_like(corridor)
    num = labels.max()
    for i in range(1, num + 1):
        component = labels == i
        if not np.any(corridor[component]):
            continue
        if np.any(marker[component]):
            road[component] = 255

    kernel = np.ones((ROAD_CLOSE_KERNEL, ROAD_CLOSE_KERNEL), np.uint8)
    road = cv2.morphologyEx(road, cv2.MORPH_CLOSE, kernel, iterations=2)

    lot_interior = build_lot_interior_mask(original_gray)
    road = cv2.bitwise_and(road, cv2.bitwise_not(lot_interior))
    return road


def _flood_outside_from_border(passable: np.ndarray) -> np.ndarray:
    """Pixels reachable from the image border without crossing walls (0 in passable)."""
    h, w = passable.shape
    flood = passable.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    for x in range(w):
        if flood[0, x] == 255:
            cv2.floodFill(flood, mask, (x, 0), 128)
        if flood[h - 1, x] == 255:
            cv2.floodFill(flood, mask, (x, h - 1), 128)
    for y in range(h):
        if flood[y, 0] == 255:
            cv2.floodFill(flood, mask, (0, y), 128)
        if flood[y, w - 1] == 255:
            cv2.floodFill(flood, mask, (w - 1, y), 128)
    return flood == 128


def build_site_mask_from_boundary(boundary_bgr: np.ndarray) -> np.ndarray:
    """Inside the hand-drawn red site perimeter (development area)."""
    hsv = cv2.cvtColor(boundary_bgr, cv2.COLOR_BGR2HSV)
    red_low = cv2.inRange(hsv, (0, 80, 80), (12, 255, 255))
    red_high = cv2.inRange(hsv, (168, 80, 80), (180, 255, 255))
    red = cv2.bitwise_or(red_low, red_high)
    red = cv2.dilate(red, np.ones((7, 7), np.uint8), iterations=2)
    passable = cv2.bitwise_not(red)
    outside = _flood_outside_from_border(passable)
    site = (~outside).astype(np.uint8) * 255
    return site


def build_site_mask_from_plan(gray: np.ndarray) -> np.ndarray:
    """Fallback: site = drawing area not connected to outer white margin."""
    white = (gray > 200).astype(np.uint8) * 255
    outside = _flood_outside_from_border(white)
    return (~outside).astype(np.uint8) * 255


def build_filled_roads_image(
    original_gray: np.ndarray,
    annotated_gray: np.ndarray,
    boundary_bgr: np.ndarray | None = None,
) -> np.ndarray:
    if original_gray.shape != annotated_gray.shape:
        raise ValueError(
            f"Size mismatch: original {original_gray.shape} vs annotated {annotated_gray.shape}"
        )

    road = build_road_mask(original_gray, annotated_gray)
    base = cv2.cvtColor(original_gray, cv2.COLOR_GRAY2BGR)
    out = base.copy()
    out[road > 0] = (0, 0, 0)

    if boundary_bgr is not None and boundary_bgr.shape[:2] == original_gray.shape:
        site = build_site_mask_from_boundary(boundary_bgr)
    else:
        site = build_site_mask_from_plan(original_gray)
    out[site == 0] = (255, 255, 255)
    return out


def main() -> None:
    if not SRC_PATH.exists():
        raise SystemExit(f"Source image not found: {SRC_PATH}")
    if not ANNOTATED_PATH.exists():
        raise SystemExit(
            f"Annotated roads image not found: {ANNOTATED_PATH}\n"
            "Copy your hand-drawn road annotation to that path first."
        )

    original = cv2.imread(str(SRC_PATH), cv2.IMREAD_GRAYSCALE)
    annotated = cv2.imread(str(ANNOTATED_PATH), cv2.IMREAD_GRAYSCALE)
    boundary = None
    if BOUNDARY_PATH.exists():
        boundary = cv2.imread(str(BOUNDARY_PATH))
    if original is None:
        raise SystemExit(f"Could not read image: {SRC_PATH}")
    if annotated is None:
        raise SystemExit(f"Could not read image: {ANNOTATED_PATH}")

    filled = build_filled_roads_image(original, annotated, boundary)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT_PATH), filled)
    print(f"Wrote road-corridor image -> {OUT_PATH}")


if __name__ == "__main__":
    main()
