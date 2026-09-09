import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]

vis = rgb.copy()
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 600 <= cx <= 720 and 220 <= cy <= 320:
        pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], np.int32)
        cv2.polylines(vis, [pts], True, (0, 220, 255), 1)
        cv2.putText(vis, str(i), (int(cx) - 8, int(cy) + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)
        print(f"#{i} c=({cx:.0f},{cy:.0f}) area={L['area']} pts={L['points']}")

# probe coverage of the big empty looking cell
for x, y in [(630, 255), (640, 260), (650, 270), (635, 280), (645, 255)]:
    hit = None
    for i, L in enumerate(lots):
        poly = np.array([[p[0] * W, p[1] * H] for p in L["points"]], np.float32)
        if cv2.pointPolygonTest(poly, (float(x), float(y)), False) >= 0:
            hit = i
            break
    print(f"probe ({x},{y}) gray={gray[y,x]} in lot={hit}")

Image.fromarray(vis[200:320, 600:780]).save("scratch/crop_right_labeled.png")
print("wrote crop_right_labeled.png")
