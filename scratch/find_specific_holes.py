import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
H, W = gray.shape
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]

# Right gray cluster column
print("lots x=615-655, y=200-310:")
col = []
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 615 <= cx <= 655 and 200 <= cy <= 310:
        col.append((cy, cx, i, L["area"]))
col.sort()
for cy, cx, i, a in col:
    print(f"  #{i} ({cx:.0f},{cy:.0f}) area={a}")

# User match bottom row y~400-430, x~150-210
print("\nlots x=145-215, y=380-440:")
row = []
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 145 <= cx <= 215 and 380 <= cy <= 440:
        row.append((cx, cy, i, L["area"]))
row.sort()
for cx, cy, i, a in row:
    print(f"  #{i} ({cx:.0f},{cy:.0f}) area={a}")

# Visualize uncovered enclosed peaks in right crop
cov = np.zeros((H, W), np.uint8)
for L in lots:
    p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], np.int32)
    cv2.fillConvexPoly(cov, p, 255)
ink = (gray < 108).astype(np.uint8)
dbg = np.array(Image.open("scratch/lot_map_polygons_debug.png").convert("RGB"))
for y in range(250, 310):
    for x in range(615, 660):
        if cov[y, x] or gray[y, x] < 160 or ink[y, x]:
            continue
        # local peak-ish
        if gray[y, x] < gray[max(0, y - 1), x] or gray[y, x] < gray[y, max(0, x - 1)]:
            continue
        hits = 0
        for ang in (0, 90, 180, 270):
            rad = np.deg2rad(ang)
            for t in range(5, 18):
                xx = int(x + t * np.cos(rad))
                yy = int(y + t * np.sin(rad))
                if 0 <= xx < W and 0 <= yy < H and ink[yy, xx]:
                    hits += 1
                    break
        if hits >= 3:
            cv2.circle(dbg, (x, y), 2, (255, 0, 0), -1)
            print(f"hole candidate ({x},{y}) gray={gray[y,x]} hits={hits}")
Image.fromarray(dbg[200:320, 600:780]).save("scratch/crop_right_holes.png")
print("wrote crop_right_holes.png")
