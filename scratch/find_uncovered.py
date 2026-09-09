import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
data = json.loads((ROOT / "static/units/lot_plan_polygons.json").read_text())
lots = data["lots"]

cov = np.zeros((H, W), dtype=np.uint8)
for L in lots:
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.int32)
    cv2.fillConvexPoly(cov, pts, 255)

bright = (gray > 155).astype(np.uint8) * 255
mid = ((gray >= 120) & (gray <= 185)).astype(np.uint8) * 255
ink = (gray < 100).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
fill = cv2.bitwise_or(bright, mid)
mask = cv2.bitwise_and(fill, cv2.bitwise_not(ink))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)

unc = cv2.bitwise_and(mask, cv2.bitwise_not(cov))
n, labels, stats, cents = cv2.connectedComponentsWithStats(unc, connectivity=4)
cands = []
for i in range(1, n):
    x, y, w, h, area = stats[i]
    if area < 70 or area > 3600:
        continue
    if w < 8 or h < 8 or w > 95 or h > 95:
        continue
    if max(w, h) / max(min(w, h), 1) > 3.8:
        continue
    sub = unc[y : y + h, x : x + w]
    if float((sub > 0).mean()) < 0.4:
        continue
    cx, cy = int(cents[i][0]), int(cents[i][1])
    if not (4 <= cx < W - 4 and 4 <= cy < H - 4):
        continue
    if gray[cy, cx] < 110:
        continue
    cands.append((area, x, y, w, h, cx, cy))

cands.sort(reverse=True)
print(f"uncovered candidates: {len(cands)}")
for a, x, y, w, h, cx, cy in cands[:50]:
    print(f"  area={a:4d} box=({x},{y},{w}x{h}) c=({cx},{cy}) gray={gray[cy, cx]}")

dbg = rgb.copy()
for a, x, y, w, h, cx, cy in cands:
    cv2.rectangle(dbg, (x, y), (x + w, y + h), (255, 0, 0), 1)
for L in lots:
    pts = np.array([[int(p[0] * W), int(p[1] * H)] for p in L["points"]], dtype=np.int32)
    cv2.polylines(dbg, [pts], True, (0, 200, 255), 1)
out = ROOT / "scratch/lot_map_uncovered_debug.png"
Image.fromarray(dbg).save(out)
print(f"wrote {out}")
