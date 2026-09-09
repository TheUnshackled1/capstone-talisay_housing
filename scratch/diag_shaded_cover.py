import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

W, H = 906, 543
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]
rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

print("lots in shaded region:")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 50 <= cx <= 220 and 40 <= cy <= 175:
        print(f"  #{i:3d} ({cx:6.1f},{cy:6.1f}) area={L['area']:.4f}")

# mid-gray mask in crop
x0, y0, w, h = 49, 33, 172, 157
crop = gray[y0 : y0 + h, x0 : x0 + w]
mid = ((crop >= 130) & (crop <= 178)).astype(np.uint8) * 255
# close small gaps
mid = cv2.morphologyEx(mid, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
n, labels, stats, cents = cv2.connectedComponentsWithStats(mid, 8)
print(f"\nshaded CCs in crop: {n-1}")
for i in range(1, n):
    a = stats[i, cv2.CC_STAT_AREA]
    if a < 80:
        continue
    cx = cents[i][0] + x0
    cy = cents[i][1] + y0
    # covered?
    covered = False
    for L in lots:
        lx, ly = L["cx"] * W, L["cy"] * H
        if abs(lx - cx) < 14 and abs(ly - cy) < 14:
            covered = True
            break
    print(f"  CC area={a:4d} center=({cx:.0f},{cy:.0f}) covered={covered}")
