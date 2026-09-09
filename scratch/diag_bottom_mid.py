import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location("g", "scratch/gen_lot_polygons.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

W, H = 906, 543
gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]
med = 21.0

print("bottom mid-gray lots (y>300):")
n = 0
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if cy < 300:
        continue
    g0 = int(gray[int(cy), int(cx)])
    if not (130 <= g0 <= 178):
        continue
    hits = g._enclosure_hits(gray, cx, cy, med)
    print(f"  #{i} ({cx:.0f},{cy:.0f}) g={g0} hits={hits} a={L['area']}")
    n += 1
print("count", n)

print("\nall mid hits<=3:")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    g0 = int(gray[int(cy), int(cx)])
    if not (130 <= g0 <= 178):
        continue
    hits = g._enclosure_hits(gray, cx, cy, med)
    if hits <= 3:
        print(f"  #{i} ({cx:.0f},{cy:.0f}) hits={hits} a={L['area']}")
