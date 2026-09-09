"""Locate user crop and analyze shaded block + road boxes."""
from pathlib import Path

import cv2
import json
import numpy as np
from PIL import Image

ROOT = Path(".")
ASSETS = Path(r"C:\Users\jtcor\.cursor\projects\c-Users-jtcor-Documents-capstone\assets")
crop_path = next(ASSETS.glob("*image-45be89d4*"))
full_rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
full = cv2.cvtColor(full_rgb, cv2.COLOR_RGB2GRAY)
H, W = full.shape

rgb = np.array(Image.open(crop_path).convert("RGB"))
crop = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
# suppress blue UI
b, g, r = cv2.split(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
blueish = (b.astype(int) > r.astype(int) + 30) & (b.astype(int) > g.astype(int) + 15)
crop = crop.copy()
crop[blueish] = int(np.median(crop[~blueish])) if (~blueish).any() else 180
crop_e = cv2.Canny(crop, 50, 120)
full_e = cv2.Canny(full, 50, 120)

best = (-1, None, None)
for scale in np.linspace(0.25, 1.0, 30):
    small = cv2.resize(crop_e, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if small.shape[0] >= H or small.shape[1] >= W or min(small.shape) < 40:
        continue
    res = cv2.matchTemplate(full_e, small, cv2.TM_CCOEFF_NORMED)
    _, maxv, _, maxl = cv2.minMaxLoc(res)
    if maxv > best[0]:
        best = (maxv, maxl, scale)
print("match", best)
x, y = best[1]
scale = best[2]
w, h = int(crop.shape[1] * scale), int(crop.shape[0] * scale)
print(f"region ({x},{y}) {w}x{h}")

lots = json.loads((ROOT / "static/units/lot_plan_polygons.json").read_text())["lots"]
cov = np.zeros((H, W), np.uint8)
for L in lots:
    p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], np.int32)
    cv2.fillConvexPoly(cov, p, 255)

# Lots whose centers fall in this region
print("lots in region:")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if x <= cx <= x + w and y <= cy <= y + h:
        print(f"  #{i} ({cx:.0f},{cy:.0f}) area={L['area']} gray={full[int(cy),int(cx)]}")

# Shaded fill in region (mid-gray lots)
sub = full[y : y + h, x : x + w]
shaded = ((sub >= 130) & (sub <= 175)).astype(np.uint8) * 255
ink = (sub < 100).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
shaded = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
shaded = cv2.morphologyEx(shaded, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1)
n, labels, stats, cents = cv2.connectedComponentsWithStats(shaded, connectivity=4)
print("shaded CCs in crop:")
miss = []
for i in range(1, n):
    sx, sy, sw, sh, area = stats[i]
    if area < 80 or sw < 8 or sh < 8:
        continue
    if max(sw, sh) / max(min(sw, sh), 1) > 3.5:
        continue
    cx, cy = int(cents[i][0]) + x, int(cents[i][1]) + y
    covered = bool(cov[cy, cx])
    print(f"  ({cx},{cy}) {sw}x{sh} area={area} cov={covered} mean={full[cy,cx]}")
    if not covered:
        miss.append((cx, cy))

# Road-band lots in crop: bright centers with weak enclosure
import importlib.util

spec = importlib.util.spec_from_file_location("gen", "scratch/gen_lot_polygons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)
print("roadish lots in/near region:")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if not (x - 20 <= cx <= x + w + 20 and y - 20 <= cy <= y + h + 20):
        continue
    if gen.is_road_center(full, cx, cy, 21):
        print(f"  ROAD #{i} ({cx:.0f},{cy:.0f})")

dbg = np.array(Image.open(ROOT / "scratch/lot_map_polygons_debug.png").convert("RGB"))
vis = dbg[y : y + h, x : x + w].copy()
for cx, cy in miss:
    cv2.circle(vis, (cx - x, cy - y), 4, (255, 0, 0), -1)
Image.fromarray(vis).save(ROOT / "scratch/crop_user_shaded.png")
cv2.rectangle(dbg, (x, y), (x + w, y + h), (255, 0, 0), 2)
Image.fromarray(dbg).save(ROOT / "scratch/locate_shaded_region.png")
print("wrote crops; missed shaded", miss)
