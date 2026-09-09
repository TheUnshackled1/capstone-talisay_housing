"""Match user crop landmarks onto full map; list polygons near that junction."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(r"C:\Users\jtcor\.cursor\projects\c-Users-jtcor-Documents-capstone\assets")
crop_paths = list(ASSETS.glob("*.png"))
print("crops:", [p.name for p in crop_paths])

full = cv2.cvtColor(np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
H, W = full.shape

for cp in crop_paths:
    crop = cv2.cvtColor(np.array(Image.open(cp).convert("RGB")), cv2.COLOR_RGB2GRAY)
    # drop UI blue overlays roughly by working on edges
    ch, cw = crop.shape
    if ch > H or cw > W:
        # screenshot may be zoomed - scale down candidates
        for scale in (0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7, 0.8):
            small = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if small.shape[0] >= H or small.shape[1] >= W:
                continue
            res = cv2.matchTemplate(full, small, cv2.TM_CCOEFF_NORMED)
            minv, maxv, minl, maxl = cv2.minMaxLoc(res)
            if maxv > 0.35:
                print(f"{cp.name} scale={scale:.2f} match={maxv:.3f} at {maxl} size={small.shape[::-1]}")
    else:
        res = cv2.matchTemplate(full, crop, cv2.TM_CCOEFF_NORMED)
        minv, maxv, minl, maxl = cv2.minMaxLoc(res)
        print(f"{cp.name} match={maxv:.3f} at {maxl}")

# Also: find small black circles via Hough and list 4-quadrant coverage
lots = json.loads((ROOT / "static/units/lot_plan_polygons.json").read_text())["lots"]
cov = np.zeros((H, W), dtype=np.uint8)
for L in lots:
    p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], dtype=np.int32)
    cv2.fillConvexPoly(cov, p, 255)

blur = cv2.medianBlur(full, 5)
raw = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1.1, 12, param1=70, param2=18, minRadius=4, maxRadius=18)
circles = raw[0] if raw is not None else []
print(f"\nloose circles={len(circles)}")
for cx, cy, r in circles:
    cx, cy, r = float(cx), float(cy), float(r)
    quads = {}
    for dx, dy, name in [(-11, -9, "NW"), (11, -9, "NE"), (-11, 9, "SW"), (11, 9, "SE")]:
        x, y = int(cx + dx), int(cy + dy)
        if 0 <= x < W and 0 <= y < H:
            quads[name] = (bool(cov[y, x]), int(full[y, x]), (x, y))
    # flag NE covered SE not
    if quads.get("NE", (False,))[0] and not quads.get("SE", (True,))[0]:
        if quads["SE"][1] > 140:
            print(f"CANDIDATE junction ({cx:.0f},{cy:.0f}) r={r:.1f} {quads}")
