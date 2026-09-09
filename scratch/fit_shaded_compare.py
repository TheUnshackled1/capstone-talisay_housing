"""Fit shaded-cluster lots to ink walls and write QA crop."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gen", ROOT / "scratch" / "gen_lot_polygons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

W, H = 906, 543
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
lots = json.loads((ROOT / "static/units/lot_plan_polygons.json").read_text())["lots"]

# Current shaded cluster centers
seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]

print("ink-wall fits:")
for sx, sy in seeds:
    hit = gen.lot_from_seed(gray, sx, sy, 24.0)
    if not hit:
        print(f"  FAIL ({sx},{sy})")
        continue
    lot, box = hit
    xs = box[:, 0]; ys = box[:, 1]
    print(
        f"  ({sx:.0f},{sy:.0f}) -> cx={lot['cx']*W:.1f} cy={lot['cy']*H:.1f} "
        f"w={xs.max()-xs.min():.1f} h={ys.max()-ys.min():.1f} area={lot['area']}"
    )

# Visualize current vs ink-wall
img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
for L in lots:
    cx, cy = L["cx"] * W, L["cy"] * H
    if 95 <= cx <= 210 and 85 <= cy <= 155:
        pts = [(p[0] * W, p[1] * H) for p in L["points"]]
        dr.line(pts + [pts[0]], fill=(0, 120, 255), width=2)

for sx, sy in seeds:
    hit = gen.lot_from_seed(gray, sx, sy, 24.0)
    if not hit:
        continue
    _, box = hit
    pts = [(float(x), float(y)) for x, y in box]
    dr.line(pts + [pts[0]], fill=(0, 220, 80), width=2)
    dr.ellipse((sx - 2, sy - 2, sx + 2, sy + 2), fill=(255, 0, 0))

out = ROOT / "scratch" / "shaded_fit_compare.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
