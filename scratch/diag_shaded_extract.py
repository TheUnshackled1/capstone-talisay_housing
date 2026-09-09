import importlib.util

import cv2
import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location("gen", "scratch/gen_lot_polygons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
seeds = [(102, 92), (167, 103), (194, 110), (161, 134), (194, 131)]

for bright_t, ink_t, dil in [(155, 70, 2), (160, 100, 2), (170, 110, 1), (150, 80, 3)]:
    m = gen.build_mask(gray, dilate=dil, close=True, bright_t=bright_t, ink_t=ink_t)
    print(f"mask bright={bright_t} ink={ink_t} dil={dil}")
    for x, y in seeds:
        print(f"  ({x},{y}) mask={m[y,x]}")
    cands = gen.extract_from_mask(gray, m)
    for lot, box in cands:
        cx, cy = lot["cx"] * 906, lot["cy"] * 543
        for sx, sy in seeds:
            if abs(cx - sx) < 18 and abs(cy - sy) < 18:
                print(f"  FOUND near ({sx},{sy}): ({cx:.0f},{cy:.0f}) area={lot['area']}")
