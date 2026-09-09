import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

H, W = 543, 906
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]
rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))

print("lots in bottom of user region:")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 140 <= cx <= 220 and 400 <= cy <= 445:
        print(f"  #{i} ({cx:.0f},{cy:.0f}) area={L['area']}")

vis = rgb.copy()
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 130 <= cx <= 230 and 330 <= cy <= 450:
        pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], np.int32)
        cv2.polylines(vis, [pts], True, (0, 200, 255), 1)
        cv2.putText(vis, str(i), (int(cx) - 10, int(cy) + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (255, 0, 0), 1)
Image.fromarray(vis[330:450, 130:230]).save("scratch/crop_user_labeled.png")
print("wrote labeled")
