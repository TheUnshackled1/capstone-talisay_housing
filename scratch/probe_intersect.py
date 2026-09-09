"""Find all polygons that intersect the shaded cluster bbox."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
data = json.loads(Path("static/units/lot_plan_polygons.json").read_text(encoding="utf-8"))
rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")

x0, x1, y0, y1 = 90, 222, 80, 168
hits = []
for i, L in enumerate(data["lots"]):
    pts = np.array(L["points"], dtype=np.float32)
    px = pts * np.array([W, H], dtype=np.float32)
    cx, cy = float(L["cx"]) * W, float(L["cy"]) * H
    # intersects bbox?
    minx, miny = px.min(axis=0)
    maxx, maxy = px.max(axis=0)
    if maxx < x0 or minx > x1 or maxy < y0 or miny > y1:
        continue
    area = float(L.get("area", 0))
    hits.append((i, cx, cy, len(L["points"]), area))
    # color by whether center in cluster
    in_c = 95 <= cx <= 215 and 80 <= cy <= 160
    col = (0, 200, 255, 100) if in_c else (255, 0, 0, 140)
    outline = (0, 100, 255, 255) if in_c else (255, 0, 0, 255)
    dr.polygon([tuple(map(int, p)) for p in px], fill=col, outline=outline)

print("intersecting", len(hits))
for h in hits:
    print(h)

vis.crop((85, 70, 230, 180)).resize((435, 330), Image.NEAREST).save(
    "scratch/shaded_all_intersect.png"
)
print("wrote shaded_all_intersect.png")
