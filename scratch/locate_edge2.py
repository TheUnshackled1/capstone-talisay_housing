"""Match tiny user crops at near-1.0 scales; inspect coverage in matched region."""
from pathlib import Path

import cv2
import json
import numpy as np
from PIL import Image

ROOT = Path(".")
ASSETS = Path(r"C:\Users\jtcor\.cursor\projects\c-Users-jtcor-Documents-capstone\assets")
full_rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
full = cv2.cvtColor(full_rgb, cv2.COLOR_RGB2GRAY)
full_e = cv2.Canny(full, 50, 120)
H, W = full.shape
lots = json.loads((ROOT / "static/units/lot_plan_polygons.json").read_text())["lots"]
cov = np.zeros((H, W), np.uint8)
for L in lots:
    p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], np.int32)
    cv2.fillConvexPoly(cov, p, 255)

for name in ["image-ea3e0e7d", "image-1cc80aac"]:
    path = next(ASSETS.glob(f"*{name}*"))
    rgb = np.array(Image.open(path).convert("RGB"))
    crop = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    b, g, r = cv2.split(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    blueish = (b.astype(int) > r.astype(int) + 35) & (b.astype(int) > g.astype(int) + 15)
    crop = crop.copy()
    crop[blueish] = int(np.median(crop[~blueish])) if (~blueish).any() else 180
    crop_e = cv2.Canny(crop, 50, 120)
    best = (-1, None, None)
    for scale in np.linspace(0.7, 1.3, 25):
        small = cv2.resize(crop_e, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if small.shape[0] >= H or small.shape[1] >= W:
            continue
        res = cv2.matchTemplate(full_e, small, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxl = cv2.minMaxLoc(res)
        if maxv > best[0]:
            best = (maxv, maxl, scale)
    print(name, best)
    x, y = best[1]
    scale = best[2]
    w, h = int(crop.shape[1] * scale), int(crop.shape[0] * scale)
    print(f"  box=({x},{y},{w}x{h})")
    # coverage map in region
    sub = cov[y : y + h, x : x + w]
    print(f"  covered_frac={float(sub.mean())/255:.2f}")
    # find uncovered bright cells
    gsub = full[y : y + h, x : x + w]
    ink = (gsub < 108).astype(np.uint8)
    for yy in range(4, h - 4, 3):
        for xx in range(4, w - 4, 3):
            if gsub[yy, xx] > 160 and sub[yy, xx] == 0 and ink[yy, xx] == 0:
                print(f"  uncovered ({x+xx},{y+yy}) gray={gsub[yy,xx]}")
    dbg = np.array(Image.open(ROOT / "scratch/lot_map_polygons_debug.png").convert("RGB"))
    vis = dbg[y : y + h, x : x + w].copy()
    cv2.rectangle(dbg, (x, y), (x + w, y + h), (255, 0, 0), 2)
    Image.fromarray(vis).save(ROOT / "scratch" / f"match_{name}.png")
    Image.fromarray(dbg).save(ROOT / "scratch" / f"matchfull_{name}.png")
