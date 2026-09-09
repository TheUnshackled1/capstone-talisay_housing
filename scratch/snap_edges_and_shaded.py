"""Snap every lot to PNG ink walls; split shaded pads that cover 2+ cells.

Index-stable: in-place replace + append only.
"""
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
lots: list[dict] = data["lots"]
MED = float(np.median([L["area"] * W * H for L in lots]))
print(f"snap start lots={len(lots)}")


def r4(v: float) -> float:
    return round(float(v), 4)


def order_pts(pts: np.ndarray) -> np.ndarray:
    c = pts.mean(axis=0)
    angs = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    return pts[np.argsort(angs)]


def to_lot(box: np.ndarray) -> dict:
    box = order_pts(np.asarray(box, dtype=np.float64))
    c = box.mean(axis=0)
    area_px = abs(float(cv2.contourArea(box.astype(np.float32))))
    return {
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in box],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    }


def ray_to_ink(sx: float, sy: float, dx: float, dy: float, max_r: int = 28) -> tuple[float, float]:
    n = float(np.hypot(dx, dy)) or 1.0
    dx, dy = dx / n, dy / n
    last = (float(sx), float(sy))
    for r in range(1, max_r + 1):
        x = sx + dx * r
        y = sy + dy * r
        ix, iy = int(round(x)), int(round(y))
        if not (0 <= ix < W and 0 <= iy < H):
            break
        if gray[iy, ix] < 78:
            # one pixel back from ink
            return last
        last = (x, y)
    return last


def snap_lot(L: dict) -> dict:
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.float32)
    if len(pts) < 3:
        return L
    rect = cv2.minAreaRect(pts)
    (cx, cy), (rw, rh), ang = rect
    if min(rw, rh) < 6:
        return L
    rad = np.deg2rad(ang)
    # local axes of the min-area rect
    ax = np.array([np.cos(rad), np.sin(rad)])
    ay = np.array([-np.sin(rad), np.cos(rad)])
    # hit ink along +/- each axis
    p_x = np.array(ray_to_ink(cx, cy, ax[0], ax[1], int(rw / 2) + 8))
    n_x = np.array(ray_to_ink(cx, cy, -ax[0], -ax[1], int(rw / 2) + 8))
    p_y = np.array(ray_to_ink(cx, cy, ay[0], ay[1], int(rh / 2) + 8))
    n_y = np.array(ray_to_ink(cx, cy, -ay[0], -ay[1], int(rh / 2) + 8))
    # reconstruct rectangle from axis hits (inset 0.8px)
    hx = (p_x - n_x) / 2.0
    hy = (p_y - n_y) / 2.0
    if np.linalg.norm(hx) < 4 or np.linalg.norm(hy) < 4:
        return L
    # shrink 0.8px toward center so stroke stays inside the cell
    nx = hx / (np.linalg.norm(hx) + 1e-9)
    ny = hy / (np.linalg.norm(hy) + 1e-9)
    hx = hx - nx * 0.8
    hy = hy - ny * 0.8
    c = 0.25 * (p_x + n_x + p_y + n_y)
    box = np.array([c - hx - hy, c + hx - hy, c + hx + hy, c - hx + hy])
    snapped = to_lot(box)
    a = snapped["area"] * W * H
    if a < MED * 0.30 or a > MED * 2.4:
        return L
    return snapped


# 1) snap every existing lot to ink (in place)
snapped_n = 0
for i, L in enumerate(lots):
    s = snap_lot(L)
    if s is not L and (
        abs(s["cx"] - L["cx"]) > 1e-5
        or abs(s["cy"] - L["cy"]) > 1e-5
        or abs(s["area"] - L["area"]) > 1e-5
    ):
        lots[i] = s
        snapped_n += 1
print(f"snapped {snapped_n} lots to ink edges")


# 2) split / fill shaded pad cells
ink = cv2.dilate((gray < 100).astype(np.uint8) * 255, np.ones((2, 2), np.uint8), 1)
pad = ((gray >= 128) & (gray <= 178)).astype(np.uint8) * 255
pad = cv2.bitwise_and(pad, cv2.bitwise_not(ink))
split = cv2.erode(pad, np.ones((3, 3), np.uint8), 1)
n, labels, stats, cents = cv2.connectedComponentsWithStats(split, connectivity=8)

pad_cells: list[tuple[int, float, float, int, int, int]] = []
for i in range(1, n):
    x, y, w, h, area = stats[i]
    if not (70 <= area <= 900):
        continue
    if not (7 <= w <= 55 and 7 <= h <= 55):
        continue
    if max(w, h) / max(min(w, h), 1) > 2.9:
        continue
    cx, cy = float(cents[i][0]), float(cents[i][1])
    pad_cells.append((i, cx, cy, int(w), int(h), int(area)))


def lot_from_label(lab: int) -> dict | None:
    cell = (labels == lab).astype(np.uint8) * 255
    cell = cv2.dilate(cell, np.ones((3, 3), np.uint8), 1)
    cell = cv2.bitwise_and(cell, pad)
    ys, xs = np.where(cell > 0)
    if len(xs) < 40:
        return None
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    box = cv2.boxPoints(cv2.minAreaRect(cnt))
    c = box.mean(axis=0)
    box = c + (box - c) * 0.96
    lot = to_lot(box)
    a = lot["area"] * W * H
    if a < MED * 0.35 or a > MED * 1.8:
        return None
    return lot


def center_in_lot(cx: float, cy: float, L: dict) -> bool:
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.float32)
    return cv2.pointPolygonTest(pts, (float(cx), float(cy)), False) >= 0


# map pad cell -> existing lot index whose polygon contains the pad center
owner: dict[int, list[int]] = {i: [] for i in range(len(lots))}
unclaimed: list[int] = []
for lab, cx, cy, w, h, area in pad_cells:
    found = None
    for li, L in enumerate(lots):
        if center_in_lot(cx, cy, L):
            found = li
            break
    if found is None:
        unclaimed.append(lab)
    else:
        owner[found].append(lab)

split_n = 0
add_n = 0
for li, labs in owner.items():
    if len(labs) < 2:
        continue
    # keep the pad whose center is closest to the existing lot center
    L = lots[li]
    ox, oy = L["cx"] * W, L["cy"] * H
    labs_sorted = sorted(
        labs,
        key=lambda lab: (cents[lab][0] - ox) ** 2 + (cents[lab][1] - oy) ** 2,
    )
    keep = lot_from_label(labs_sorted[0])
    if keep is None:
        continue
    extras = []
    ok = True
    for lab in labs_sorted[1:]:
        extra = lot_from_label(lab)
        if extra is None:
            ok = False
            break
        extras.append(extra)
    if not ok:
        continue
    lots[li] = keep
    lots.extend(extras)
    split_n += 1
    add_n += len(extras)
    print(f"SHADED split idx={li} -> {1+len(extras)} cells")

for lab in unclaimed:
    extra = lot_from_label(lab)
    if extra is None:
        continue
    # skip if too close to an existing center
    if any(
        np.hypot((extra["cx"] - L["cx"]) * W, (extra["cy"] - L["cy"]) * H) < 8
        for L in lots
    ):
        continue
    lots.append(extra)
    add_n += 1
    print(f"SHADED add ({extra['cx']*W:.0f},{extra['cy']*H:.0f})")

data["lots"] = lots
POLY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"wrote lots={len(lots)} shaded_splits={split_n} added={add_n}")
print(f"index 410 valid? {410 < len(lots)} max={len(lots)-1}")

vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for L in lots:
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, outline=(0, 180, 255, 220))
vis.save(ROOT / "scratch" / "snap_edges_qa.png")
vis.crop((80, 70, 230, 180)).resize((450, 330), Image.NEAREST).save(
    ROOT / "scratch" / "snap_shaded_tl.png"
)
vis.crop((580, 220, 760, 360)).resize((540, 420), Image.NEAREST).save(
    ROOT / "scratch" / "snap_shaded_mr.png"
)
print("QA snap_edges_qa.png snap_shaded_tl.png snap_shaded_mr.png")
