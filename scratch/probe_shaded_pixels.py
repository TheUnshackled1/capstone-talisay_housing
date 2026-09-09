"""Probe shaded-region pixel values and separation."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

# Sample known pad centers and border midpoints between pads
samples = {
    "pad_tl": (108, 96),
    "pad_tr": (196, 111),
    "pad_bl": (104, 116),
    "pad_br": (194, 145),
    "between_top": (123, 98),
    "between_mid": (152, 103),
    "between_bot": (147, 130),
    "vert_between": (120, 108),
    "road_below": (150, 165),
    "open_tan": (250, 100),
}
for name, (x, y) in samples.items():
    print(f"{name:14} ({x:3},{y:3}) gray={gray[y,x]:3} rgb={tuple(rgb[y,x])}")

# Crop and dump a small ASCII of gray values around top-left pad
print("\n-- gray patch around (108,96) --")
for y in range(88, 112):
    row = []
    for x in range(95, 130):
        g = int(gray[y, x])
        if g < 80:
            row.append("#")
        elif g < 120:
            row.append("+")
        elif g < 175:
            row.append("s")
        elif g < 200:
            row.append(".")
        else:
            row.append(" ")
    print(f"{y:3} " + "".join(row))

# Try stronger ink threshold + less dilate; also try edge-based split
for thr in (80, 90, 100, 110, 120, 140, 160, 180):
    ink = (gray < thr).astype(np.uint8)
    ink_c = ink[75:175, 90:220]
    print(f"ink<{thr}: {ink_c.sum()} px in crop")

# Canny edges in crop
crop = gray[70:180, 85:230]
edges = cv2.Canny(crop, 40, 120)
Image.fromarray(edges).save("scratch/shaded_edges.png")
Image.fromarray(crop).save("scratch/shaded_gray_crop.png")
print("wrote edges")

# Color-based: shaded pads look darker textured gray vs beige
# Check LAB / HSV
hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
for name, (x, y) in samples.items():
    print(f"{name:14} hsv={tuple(hsv[y,x])} lab={tuple(lab[y,x])}")
