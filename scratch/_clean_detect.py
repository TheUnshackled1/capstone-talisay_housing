# Replacement from recover_neighbor_gaps through force_seed_lots (before write_debug)

def is_road_center(gray: np.ndarray, sx: float, sy: float, med: float) -> bool:
    """True if seed sits in an open road corridor rather than a lot cell."""
    H, W = gray.shape
    ix, iy = int(round(sx)), int(round(sy))
    if not (0 <= ix < W and 0 <= iy < H):
        return True
    ink = (gray < 108).astype(np.uint8)
    clear_dirs = 0
    for ang in (0.0, 90.0, 180.0, 270.0):
        rad = np.deg2rad(ang)
        clear = 0
        for t in range(2, int(med * 2.2)):
            xx = int(round(sx + t * np.cos(rad)))
            yy = int(round(sy + t * np.sin(rad)))
            if not (0 <= xx < W and 0 <= yy < H):
                break
            if ink[yy, xx]:
                break
            clear += 1
        if clear >= int(med * 1.35):
            clear_dirs += 1
    if clear_dirs >= 2:
        return True
    if _enclosure_hits(gray, sx, sy, med) < 5:
        return True
    return False


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
        if gray[iy, ix] < 150:
            continue
        if is_road_center(gray, sx, sy, med):
            continue
        d2 = (centers[:, 0] - sx) ** 2 + (centers[:, 1] - sy) ** 2
        ni = int(np.argmin(d2))
        if float(np.sqrt(d2[ni])) < med * 0.55:
            continue
        ref = lots[ni]
        ref_pts = np.array(ref["points"], dtype=float) * np.array([W, H])
        edges = np.array([b - a for a, b in zip(ref_pts, np.roll(ref_pts, -1, axis=0))])
        lengths = np.linalg.norm(edges, axis=1)
        ux = edges[int(np.argmax(lengths))]
        ux = ux / (np.linalg.norm(ux) + 1e-9)
        uy = np.array([-ux[1], ux[0]])
        side = float(sides[ni])
        half_w, half_h = side * 0.45, side * 0.40
        box = np.array(
            [
                [sx, sy] - ux * half_w - uy * half_h,
                [sx, sy] + ux * half_w - uy * half_h,
                [sx, sy] + ux * half_w + uy * half_h,
                [sx, sy] - ux * half_w + uy * half_h,
            ],
            dtype=np.float32,
        )
        box = shrink_quad(box, SHRINK)
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

    blur = cv2.medianBlur(gray, 5)
    raw = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=20,
        param1=85,
        param2=24,
        minRadius=5,
        maxRadius=16,
    )
    strict = raw[0].astype(np.float32) if raw is not None else np.zeros((0, 3), dtype=np.float32)
    H, W = gray.shape
    road_circles = []
    for cx, cy, r in strict:
        x, y, rr = int(round(cx)), int(round(cy)), int(round(r))
        if not (rr + 4 < x < W - rr - 4 and rr + 4 < y < H - rr - 4):
            continue
        ring = np.zeros((H, W), dtype=np.uint8)
        cv2.circle(ring, (x, y), rr + 4, 255, 3)
        ys, xs = np.where(ring > 0)
        if len(xs) < 8:
            continue
        if float(gray[ys, xs].mean()) < 160:
            continue
        road_circles.append([cx, cy, r])
    circles = np.array(road_circles, dtype=np.float32) if road_circles else np.zeros((0, 3), dtype=np.float32)

    lots, quads = drop_circle_traces(lots, quads, circles, gray.shape)
    before_road = len(lots)
    lots, quads = drop_road_traces(lots, quads, gray)
    print(f"dropped road FPs -{before_road - len(lots)}", file=sys.stderr)
    before = len(lots)
    lots, quads = force_seed_lots(gray, lots, quads, [(163.4, 407.4)])
    print(f"surgical seeds +{len(lots) - before}", file=sys.stderr)
    return lots, quads, circles

