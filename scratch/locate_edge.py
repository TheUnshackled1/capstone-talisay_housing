"""Better locate user screenshots via edge matching."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(".")
ASSETS = Path(r"C:\Users\jtcor\.cursor\projects\c-Users-jtcor-Documents-capstone\assets")
full_rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
full = cv2.cvtColor(full_rgb, cv2.COLOR_RGB2GRAY)
full_e = cv2.Canny(full, 60, 140)

targets = [
    "image-ea3e0e7d-67d6-42a2-8fc4-de7bf920bb4c.png",
    "image-1cc80aac-04cd-4ae9-8183-84d79f924c2e.png",
]
for name in targets:
    path = next(ASSETS.glob(f"*{name}"))
    crop = cv2.cvtColor(np.array(Image.open(path).convert("RGB")), cv2.COLOR_RGB2GRAY)
    # suppress saturated blue UI by replacing very-blue pixels
    rgb = np.array(Image.open(path).convert("RGB"))
    b, g, r = cv2.split(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    blueish = (b.astype(int) > r.astype(int) + 40) & (b.astype(int) > g.astype(int) + 20)
    crop = crop.copy()
    crop[blueish] = 180
    crop_e = cv2.Canny(crop, 60, 140)
    best = (-1, None, None)
    for scale in np.linspace(0.15, 0.55, 17):
        small = cv2.resize(crop_e, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if small.shape[0] >= full_e.shape[0] or small.shape[1] >= full_e.shape[1]:
            continue
        if small.shape[0] < 40 or small.shape[1] < 40:
            continue
        res = cv2.matchTemplate(full_e, small, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxl = cv2.minMaxLoc(res)
        if maxv > best[0]:
            best = (maxv, maxl, scale)
    print(name, "best", best)
    if best[1] is not None:
        x, y = best[1]
        scale = best[2]
        w = int(crop.shape[1] * scale)
        h = int(crop.shape[0] * scale)
        vis = full_rgb.copy()
        cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 0, 0), 2)
        out = ROOT / "scratch" / f"locate_{name[:12]}.png"
        Image.fromarray(vis).save(out)
        # also save crop of that region from debug
        dbg = np.array(Image.open(ROOT / "scratch/lot_map_polygons_debug.png").convert("RGB"))
        Image.fromarray(dbg[y : y + h, x : x + w]).save(ROOT / "scratch" / f"locate_dbg_{name[:12]}.png")
        print("  region", x, y, w, h, "wrote", out)
