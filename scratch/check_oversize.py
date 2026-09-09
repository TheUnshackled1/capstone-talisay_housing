import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location("gen", "scratch/gen_lot_polygons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
W, H = 906, 543
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]

print("near circle 109,182:")
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    if abs(cx - 109) < 45 and abs(cy - 182) < 35:
        bw = (max(p[0] for p in L["points"]) - min(p[0] for p in L["points"])) * W
        bh = (max(p[1] for p in L["points"]) - min(p[1] for p in L["points"])) * H
        print(
            f"  #{i} ({cx:.0f},{cy:.0f}) area={L['area']} "
            f"box={bw:.1f}x{bh:.1f} road={gen.is_road_center(gray, cx, cy, 21)}"
        )

print("oversized near shaded:")
for i, L in enumerate(lots):
    if L["area"] >= 0.0020 and 90 <= L["cx"] * W <= 220 and 80 <= L["cy"] * H <= 160:
        print(f"  #{i} ({L['cx']*W:.0f},{L['cy']*H:.0f}) area={L['area']}")
