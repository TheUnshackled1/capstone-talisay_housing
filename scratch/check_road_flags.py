import importlib.util
import cv2
import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location("g", "scratch/gen_lot_polygons.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

gray = cv2.cvtColor(np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB")), cv2.COLOR_RGB2GRAY)
med = 21.0
for pt in [(114, 161), (136, 170), (109, 182), (107.7, 96.3), (92.8, 153.6)]:
    sx, sy = pt
    print(pt, "road=", g.is_road_center(gray, sx, sy, med), "hits=", g._enclosure_hits(gray, sx, sy, med), "g=", int(gray[int(sy), int(sx)]))
