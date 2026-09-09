"""Locate the empty-field ghost boxes and measure enclosure."""
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

# Bottom open field roughly y>280 or the large mid-gray region
weak = []
strong = []
for i, L in enumerate(lots):
    cx, cy = L["cx"] * W, L["cy"] * H
    ix, iy = int(round(cx)), int(round(cy))
    gv = int(gray[iy, ix])
    hits = g._enclosure_hits(gray, cx, cy, med)
    mid = 130 <= gv <= 178
    if hits < 6:
        weak.append((i, cx, cy, gv, hits, mid, L["area"]))
    elif mid:
        strong.append((i, cx, cy, gv, hits, L["area"]))

print(f"weak enclosure (<6): {len(weak)}")
for row in weak[:40]:
    print(f"  #{row[0]} ({row[1]:.0f},{row[2]:.0f}) g={row[3]} hits={row[4]} mid={row[5]} a={row[6]}")
print(f"\nstrong mid-gray: {len(strong)}")
for row in strong[:20]:
    print(f"  #{row[0]} ({row[1]:.0f},{row[2]:.0f}) g={row[3]} hits={row[4]} a={row[5]}")

# overlap count
quads = []
for L in lots:
    pts = np.array([[p[0] * W, p[1] * H] for p in L["points"]], dtype=np.float32)
    quads.append(pts)
olap = 0
for i in range(len(quads)):
    for j in range(i + 1, len(quads)):
        if g.aabb_iou(quads[i], quads[j]) >= 0.35:
            olap += 1
print(f"\npairs with IoU>=0.35: {olap}")
