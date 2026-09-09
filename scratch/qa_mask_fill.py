"""Visual QA: grown mask fill vs gray pads (no contour approx)."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from scratch.patch_shaded_contours import SEEDS, grow_to_ink

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
vis = rgb.copy()
for sx, sy in SEEDS:
    cell = grow_to_ink(sx, sy)
    if cell is None:
        continue
    # Colorize mask over RGB
    ys, xs = np.where(cell > 0)
    vis[ys, xs] = (vis[ys, xs] * 0.45 + np.array([40, 140, 255]) * 0.55).astype(np.uint8)
    # Draw exact contour (no approx)
    cnts, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if cnts:
        cv2.drawContours(vis, cnts, -1, (0, 60, 220), 1)

Image.fromarray(vis).crop((85, 70, 230, 180)).save("scratch/shaded_mask_fill_qa.png")
print("wrote shaded_mask_fill_qa.png")
