"""Check for remaining ghost boxes near empty field / roads."""
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
rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
dbg = np.array(Image.open("scratch/lot_map_polygons_debug.png").convert("RGB"))
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]
med = 21.0

# Lots in bottom-left region of user screenshot
print("lots in bottom-left viewport (x<250, y>300):")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if cx < 250 and cy > 300:
        hits = g._enclosure_hits(gray, cx, cy, med)
        print(f"  #{i} ({cx:.0f},{cy:.0f}) g={int(gray[int(cy),int(cx)])} hits={hits} a={L['area']}")

# Wider empty field y>360 anywhere mid-gray or weak
print("\nany weak mid/open below y=360:")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if cy < 360:
        continue
    hits = g._enclosure_hits(gray, cx, cy, med)
    g0 = int(gray[int(cy), int(cx)])
    if hits <= 4 or (130 <= g0 <= 178):
        print(f"  #{i} ({cx:.0f},{cy:.0f}) g={g0} hits={hits} a={L['area']} road={g.is_road_center(gray,cx,cy,med)}")

# Save full bottom band QA
Image.fromarray(dbg[350:543, 0:450]).save("scratch/crop_bottom_band.png")
Image.fromarray(rgb[350:543, 0:450]).save("scratch/crop_bottom_band_base.png")
print("wrote bottom band crops")
