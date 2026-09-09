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
H, W = gray.shape
lots = json.loads(Path("static/units/lot_plan_polygons.json").read_text())["lots"]
med = float(np.median([np.sqrt(L["area"] * W * H) for L in lots]))

ink = (gray < 108).astype(np.uint8) * 255
ink = cv2.dilate(ink, np.ones((2, 2), np.uint8), 1)
dist_ink = cv2.distanceTransform(cv2.bitwise_not(ink), cv2.DIST_L2, 5)

for sx, sy in [(160, 400), (200, 410), (630, 255), (185, 400)]:
    ix, iy = int(sx), int(sy)
    print(f"\nseed ({sx},{sy})")
    print(f"  gray={gray[iy,ix]} dist_ink={dist_ink[iy,ix]:.1f} hits={gen._enclosure_hits(gray,sx,sy,med)}")
    got = gen.lot_from_seed(gray, sx, sy, med)
    print(f"  lot_from_seed={None if got is None else (got[0]['area'], got[0]['cx']*W, got[0]['cy']*H)}")
