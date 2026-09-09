"""Make every PNG lot cell its own clickable polygon.

Index-stable: replace lots[i] in place, append extras at the end.
Existing HousingUnit.plan_polygon_index values stay valid.
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
print(f"start lots={len(lots)} med={MED:.0f}px")

ink_global = (gray < 112).astype(np.uint8) * 255
ink_global = cv2.morphologyEx(ink_global, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8), 1)
interior = cv2.bitwise_not(ink_global)
interior = cv2.morphologyEx(interior, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)


def r4(v: float) -> float:
    return round(float(v), 4)


def order_pts(pts: np.ndarray) -> np.ndarray:
    c = pts.mean(axis=0)
    angs = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    return pts[np.argsort(angs)]


def lot_from_box(box: np.ndarray, shrink: float = 0.90) -> dict:
    box = np.asarray(box, dtype=np.float64)
    c = box.mean(axis=0)
    box = order_pts(c + (box - c) * shrink)
    area_px = abs(float(cv2.contourArea(box.astype(np.float32))))
    return {
        "points": [[r4(float(x) / W), r4(float(y) / H)] for x, y in box],
        "cx": r4(float(c[0]) / W),
        "cy": r4(float(c[1]) / H),
        "area": r4(area_px / (W * H)),
    }


def lot_from_comp(comp: np.ndarray, shrink: float = 0.90) -> dict | None:
    ys, xs = np.where(comp > 0)
    if len(xs) < 40:
        return None
    cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(cnt)
    if not (6 <= w <= 95 and 6 <= h <= 95):
        return None
    if max(w, h) / max(min(w, h), 1) > 3.6:
        return None
    rect = cv2.minAreaRect(cnt)
    (_cx, _cy), (rw, rh), _ = rect
    if min(rw, rh) < 6 or max(rw, rh) > 95:
        return None
    box = cv2.boxPoints(rect)
    lot = lot_from_box(box, shrink)
    a = lot["area"] * W * H
    if a < MED * 0.38 or a > MED * 1.70:
        return None
    return lot


def poly_mask(L: dict, dilate: int = 0) -> np.ndarray:
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.int32)
    m = np.zeros((H, W), np.uint8)
    cv2.fillConvexPoly(m, pts, 255)
    if dilate:
        m = cv2.dilate(m, np.ones((dilate, dilate), np.uint8), 1)
    return m


def similar_pair(a: dict, b: dict) -> bool:
    aa, bb = a["area"] * W * H, b["area"] * W * H
    if min(aa, bb) < MED * 0.42 or max(aa, bb) > MED * 1.70:
        return False
    if max(aa, bb) / max(min(aa, bb), 1) > 2.15:
        return False
    dpx = np.hypot((a["cx"] - b["cx"]) * W, (a["cy"] - b["cy"]) * H)
    return dpx >= 9.0


def ink_split(L: dict) -> tuple[dict, dict] | None:
    """Two lot cells separated by a drawn line inside this polygon."""
    roi = poly_mask(L, dilate=3)
    for ink_t in (130, 140, 150, 160, 170):
        local_ink = ((gray < ink_t) & (roi > 0)).astype(np.uint8) * 255
        local_ink = cv2.dilate(local_ink, np.ones((2, 2), np.uint8), 1)
        cells = cv2.bitwise_and(roi, cv2.bitwise_not(local_ink))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(cells, connectivity=4)
        found: list[dict] = []
        for k in range(1, n):
            _x, _y, w, h, area = stats[k]
            if not (80 <= area <= 2000 and 7 <= w <= 90 and 7 <= h <= 90):
                continue
            if max(w, h) / max(min(w, h), 1) > 3.5:
                continue
            lot = lot_from_comp((labels == k).astype(np.uint8) * 255)
            if lot is not None:
                found.append(lot)
        found.sort(key=lambda p: -p["area"])
        if len(found) >= 2 and similar_pair(found[0], found[1]):
            return found[0], found[1]
    return None


def oriented_split(L: dict) -> tuple[dict, dict] | None:
    """Halve min-area rect along the long axis; keep only if a wall sits on the cut."""
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.float32)
    if len(pts) < 3:
        return None
    rect = cv2.minAreaRect(pts)
    (cx, cy), (rw, rh), ang = rect
    if min(rw, rh) < 10:
        return None
    box = cv2.boxPoints(rect)
    # box order from boxPoints: 0-1-2-3 around the rect
    e01 = np.linalg.norm(box[1] - box[0])
    e12 = np.linalg.norm(box[2] - box[1])
    if e01 >= e12:
        # long edge is 0-1; midpoints of 0-1 and 3-2
        m_a = 0.5 * (box[0] + box[1])
        m_b = 0.5 * (box[3] + box[2])
        half_a = np.array([box[0], m_a, m_b, box[3]], dtype=np.float32)
        half_b = np.array([m_a, box[1], box[2], m_b], dtype=np.float32)
    else:
        m_a = 0.5 * (box[1] + box[2])
        m_b = 0.5 * (box[0] + box[3])
        half_a = np.array([box[0], box[1], m_a, m_b], dtype=np.float32)
        half_b = np.array([m_b, m_a, box[2], box[3]], dtype=np.float32)

    roi = poly_mask(L, dilate=2)
    fill = ((gray >= 115) & (gray <= 210) & (roi > 0)).astype(np.uint8) * 255

    def fit_half(quad: np.ndarray) -> dict | None:
        mask = np.zeros((H, W), np.uint8)
        cv2.fillConvexPoly(mask, np.int32(quad), 255)
        pix = cv2.bitwise_and(fill, mask)
        return lot_from_comp(pix)

    a = fit_half(half_a)
    b = fit_half(half_b)
    if a is None or b is None or not similar_pair(a, b):
        return None

    # require a darker seam between the two halves
    ma = poly_mask(a)
    mb = poly_mask(b)
    seam = cv2.bitwise_and(cv2.dilate(ma, np.ones((3, 3), np.uint8), 1), cv2.dilate(mb, np.ones((3, 3), np.uint8), 1))
    if seam.sum() == 0:
        return None
    seam_g = float(gray[seam > 0].mean())
    body_g = float(gray[(ma > 0) | (mb > 0)].mean())
    if seam_g > body_g - 10:
        return None
    return a, b


def should_try_split(L: dict) -> bool:
    area = L["area"] * W * H
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=float)
    bw = float(pts[:, 0].max() - pts[:, 0].min())
    bh = float(pts[:, 1].max() - pts[:, 1].min())
    return area >= MED * 1.58 or bh >= 32 or bw >= 36


def coverage_centers(lot_list: list[dict]):
    cov = np.zeros((H, W), np.uint8)
    centers = []
    for L in lot_list:
        pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.int32)
        cv2.fillConvexPoly(cov, pts, 255)
        centers.append((L["cx"] * W, L["cy"] * H))
    return cov, centers


def find_missed(lot_list: list[dict]):
    cov, centers = coverage_centers(lot_list)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(interior, connectivity=4)
    missed = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (70 <= area <= 2800 and 7 <= w <= 90 and 7 <= h <= 90):
            continue
        if max(w, h) / max(min(w, h), 1) > 3.5:
            continue
        cx, cy = float(cents[i][0]), float(cents[i][1])
        if not (1 <= cx < W - 1 and 1 <= cy < H - 1):
            continue
        hit = False
        for xx, yy in centers:
            ix, iy = int(round(xx)), int(round(yy))
            if 0 <= ix < W and 0 <= iy < H and labels[iy, ix] == i:
                hit = True
                break
        if hit:
            continue
        sub_lab = labels[y : y + h, x : x + w] == i
        if not sub_lab.any():
            continue
        if float(cov[y : y + h, x : x + w][sub_lab].mean()) > 40:
            continue
        gmean = float(gray[y : y + h, x : x + w][sub_lab].mean())
        if gmean < 100 or (gmean > 212 and min(w, h) < 12):
            continue
        missed.append(i)
    return missed, labels


def overlaps(new: dict, pool: list[dict], thresh: float = 0.28) -> bool:
    pts = np.array([[p[0] * W, p[1] * H] for p in new["points"]], dtype=np.int32)
    mask = np.zeros((H, W), np.uint8)
    cv2.fillConvexPoly(mask, pts, 255)
    new_area = max(int(mask.sum() // 255), 1)
    nx, ny = new["cx"] * W, new["cy"] * H
    for L in pool:
        d = np.hypot(L["cx"] * W - nx, L["cy"] * H - ny)
        if d < 5.5:
            return True
        if d > 55:
            continue
        other = poly_mask(L)
        inter = int(np.logical_and(mask > 0, other > 0).sum())
        if inter > new_area * thresh:
            return True
    return False


# --- split doubles ---
original_n = len(lots)
appended: list[dict] = []
split_n = 0

# process a growing list: splits of new lots also allowed (their indices are new)
i = 0
while i < len(lots):
    L = lots[i]
    if not should_try_split(L):
        i += 1
        continue
    pair = ink_split(L) or oriented_split(L)
    if pair is None:
        i += 1
        continue
    a, b = pair
    ox, oy = L["cx"], L["cy"]
    da = (a["cx"] - ox) ** 2 + (a["cy"] - oy) ** 2
    db = (b["cx"] - ox) ** 2 + (b["cy"] - oy) ** 2
    keep, extra = (a, b) if da <= db else (b, a)
    lots[i] = keep
    lots.append(extra)
    appended.append(extra)
    split_n += 1
    print(
        f"SPLIT idx={i} -> keep=({keep['cx']*W:.0f},{keep['cy']*H:.0f}) "
        f"append[{len(lots)-1}]=({extra['cx']*W:.0f},{extra['cy']*H:.0f}) "
        f"areas={[round(keep['area']*W*H), round(extra['area']*W*H)]}"
    )
    i += 1

print(f"after splits lots={len(lots)} splits={split_n}")

# --- append missed edge/interior cells ---
added = 0
for pass_n in range(3):
    missed, labels = find_missed(lots)
    print(f"miss pass {pass_n+1}: {len(missed)}")
    n_add = 0
    for lab in missed:
        lot = lot_from_comp((labels == lab).astype(np.uint8) * 255, shrink=0.90)
        if lot is None:
            # fallback AABB inset for tiny edge cells
            ys, xs = np.where(labels == lab)
            if len(xs) < 30:
                continue
            x0, x1 = float(xs.min()) + 0.8, float(xs.max()) - 0.8
            y0, y1 = float(ys.min()) + 0.8, float(ys.max()) - 0.8
            if x1 - x0 < 6 or y1 - y0 < 6:
                continue
            lot = lot_from_box(
                np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64),
                shrink=0.94,
            )
        if overlaps(lot, lots):
            continue
        lots.append(lot)
        n_add += 1
        added += 1
        print(f"  ADD ({lot['cx']*W:.0f},{lot['cy']*H:.0f}) area={lot['area']*W*H:.0f}")
    if n_add == 0:
        break

data["lots"] = lots
POLY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
verify = json.loads(POLY_PATH.read_text(encoding="utf-8"))["lots"]
print(f"WROTE {POLY_PATH}")
print(f"{original_n} -> {len(verify)}  old indices 0-{original_n-1} kept")
print(f"plan index 410 valid? {410 < len(verify)} (max {len(verify)-1})")

still, _ = find_missed(verify)
print(f"still_untraced_cells={len(still)}")

vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for L in verify:
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, outline=(0, 170, 255, 200))
for L in verify[original_n:]:
    pts = [(p[0] * W, p[1] * H) for p in L["points"]]
    dr.polygon(pts, fill=(50, 220, 80, 100), outline=(0, 140, 40, 255))
vis.save(ROOT / "scratch" / "trace_all_qa.png")
# B13 column (user hover)
vis.crop((380, 150, 490, 300)).resize((440, 600), Image.NEAREST).save(
    ROOT / "scratch" / "trace_b13_qa.png"
)
print("QA scratch/trace_all_qa.png  scratch/trace_b13_qa.png")
