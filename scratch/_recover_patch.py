def recover_neighbor_gaps(
    gray: np.ndarray,
    lots: list[dict],
    quads: list[np.ndarray],
) -> tuple[list[dict], list[np.ndarray]]:
    """Recover missing lots at uncovered distance-transform peaks (true empty cells)."""
    if len(lots) < 8:
        return lots, quads

    H, W = gray.shape
    sides = [np.sqrt(L["area"] * W * H) for L in lots]
    med = float(np.median(sides)) if sides else 21.0

    cov = np.zeros((H, W), dtype=np.uint8)
    for q in quads:
        cv2.fillConvexPoly(cov, np.int32(q), 255)
    # Ignore shrink gaps between existing traces
    cov_pad = cv2.dilate(cov, np.ones((9, 9), np.uint8), 1)

    ink = (gray < 108).astype(np.uint8) * 255
    ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
    dist_ink = cv2.distanceTransform(cv2.bitwise_not(ink), cv2.DIST_L2, 5)

    mask = (
        (cov_pad == 0)
        & (gray >= 155)
        & (gray <= 200)
        & (dist_ink >= 5.5)
        & (dist_ink <= 11.0)
    )
    ys, xs = np.where(mask)

    peaks: list[tuple[float, float, float]] = []
    for x, y in zip(xs.tolist(), ys.tolist()):
        d = float(dist_ink[y, x])
        if d + 1e-6 < float(dist_ink[max(0, y - 2) : y + 3, max(0, x - 2) : x + 3].max()):
            continue
        if x < MARGIN + 8 or y < MARGIN + 8 or x >= W - MARGIN - 8 or y >= H - MARGIN - 8:
            continue
        if _enclosure_hits(gray, float(x), float(y), med) < 5:
            continue
        y0, y1 = max(0, y - 6), min(H, y + 7)
        x0, x1 = max(0, x - 6), min(W, x + 7)
        if float(gray[y0:y1, x0:x1].mean()) > 198:
            continue
        if any((x - px) ** 2 + (y - py) ** 2 < 100 for px, py, _ in peaks):
            continue
        peaks.append((float(x), float(y), d))

    extra: list[tuple[dict, np.ndarray]] = []
    for sx, sy, _d in sorted(peaks, key=lambda t: -t[2]):
        got = lot_from_seed(gray, sx, sy, med)
        if got is None:
            continue
        lot, box = got
        if lot["area"] < 0.00045:
            continue
        if any(aabb_iou(box, q.astype(np.float32)) >= IOU_DEDUP for q in quads):
            continue
        if any(aabb_iou(box, eb) >= IOU_DEDUP for _, eb in extra):
            continue
        icx, icy = int(round(sx)), int(round(sy))
        if cov_pad[icy, icx]:
            continue
        extra.append((lot, box))
        cv2.fillConvexPoly(cov, np.int32(box), 255)
        cov_pad = cv2.dilate(cov, np.ones((9, 9), np.uint8), 1)

    if not extra:
        return lots, quads
    for lot, box in extra:
        lots.append(lot)
        quads.append(np.int32(box))
    order = sorted(range(len(lots)), key=lambda i: (lots[i]["cy"], lots[i]["cx"]))
    return [lots[i] for i in order], [quads[i] for i in order]


