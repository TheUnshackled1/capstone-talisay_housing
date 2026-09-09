"""QA crop of shaded block + coverage check."""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

W, H = 906, 543
rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
dbg = np.array(Image.open("scratch/lot_map_polygons_debug.png").convert("RGB"))
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]

x0, y0, w, h = 40, 25, 200, 190
Image.fromarray(dbg[y0 : y0 + h, x0 : x0 + w]).save("scratch/crop_shaded_final.png")
Image.fromarray(rgb[y0 : y0 + h, x0 : x0 + w]).save("scratch/crop_shaded_base.png")

print("lots in shaded 2x4 pocket (95-210, 85-155):")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 95 <= cx <= 210 and 85 <= cy <= 155:
        print(f"  #{i:3d} ({cx:6.1f},{cy:6.1f}) area={L['area']:.4f}")

# circle area
print("\nnear (109,182):")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if abs(cx - 109) < 25 and abs(cy - 182) < 25:
        print(f"  #{i:3d} ({cx:6.1f},{cy:6.1f}) area={L['area']:.4f}")
