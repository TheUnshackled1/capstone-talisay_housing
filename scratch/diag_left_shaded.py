"""Locate left shaded cells and whether cyan covers them."""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

W, H = 906, 543
gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
dbg = np.array(Image.open("scratch/lot_map_polygons_debug.png").convert("RGB"))
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]

# Focus left half of shaded block
x0, y0, ww, hh = 95, 85, 60, 55
roi = gray[y0 : y0 + hh, x0 : x0 + ww]
ink = (roi < 100).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
shaded = ((roi >= 130) & (roi <= 178)).astype(np.uint8) * 255
shaded = cv2.bitwise_and(shaded, cv2.bitwise_not(ink))
split = cv2.erode(shaded, np.ones((3, 3), np.uint8), 1)
n, _, stats, cents = cv2.connectedComponentsWithStats(split, 8)
print("left pocket eroded CCs:")
for i in range(1, n):
    a = stats[i, cv2.CC_STAT_AREA]
    if a < 30:
        continue
    cx = cents[i][0] + x0
    cy = cents[i][1] + y0
    # cyan nearby in debug? cyan is roughly (0,200,255) BGR -> RGB (255,200,0)
    covered = False
    for L in lots:
        lx, ly = L["cx"] * W, L["cy"] * H
        if abs(lx - cx) < 12 and abs(ly - cy) < 12:
            covered = True
            print(f"  CC ({cx:.0f},{cy:.0f}) area={a} covered by lot center ({lx:.0f},{ly:.0f})")
            break
    if not covered:
        print(f"  CC ({cx:.0f},{cy:.0f}) area={a} MISSING")

# Check road corridor below shaded for lot centers on tan
print("\nlots with centers in road strip y=155-175, x=90-200:")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 90 <= cx <= 200 and 155 <= cy <= 175:
        g = int(gray[int(cy), int(cx)])
        print(f"  #{i} ({cx:.0f},{cy:.0f}) gray={g} area={L['area']}")

# Draw expected left seeds on crop
vis = dbg[y0 - 10 : y0 + hh + 20, x0 - 10 : x0 + ww + 80].copy()
Image.fromarray(vis).save("scratch/crop_left_shaded.png")
print("wrote scratch/crop_left_shaded.png")
