import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
H, W = gray.shape
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]
print("lots in matched region:")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 140 <= cx <= 220 and 340 <= cy <= 450:
        print(f"  #{i} ({cx:.0f},{cy:.0f}) area={L['area']}")

# Check coverage around lower circle ~173,388 — SE cell
cov = np.zeros((H, W), np.uint8)
for L in lots:
    p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], np.int32)
    cv2.fillConvexPoly(cov, p, 255)

for x, y in [(185, 398), (190, 400), (195, 395), (180, 400), (200, 400), (175, 405)]:
    print(f"pt ({x},{y}) gray={gray[y,x]} cov={bool(cov[y,x])}")
