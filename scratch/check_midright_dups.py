"""Check for duplicate/overlapping polygons in mid-right region."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
data = json.loads(Path("static/units/lot_plan_polygons.json").read_text(encoding="utf-8"))
rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))

X0, X1, Y0, Y1 = 560, 760, 185, 340
region = []
for i, L in enumerate(data["lots"]):
    pts = np.array(L["points"], dtype=np.float32) * [W, H]
    minx, miny = pts.min(axis=0)
    maxx, maxy = pts.max(axis=0)
    # any intersection with region
    if maxx < X0 or minx > X1 or maxy < Y0 or miny > Y1:
        continue
    region.append((i, L, pts))

print("intersecting", len(region))
# pairwise IoU of AABBs
for a in range(len(region)):
    ia, La, pa = region[a]
    for b in range(a + 1, len(region)):
        ib, Lb, pb = region[b]
        # polygon overlap via masks in small crop
        x0 = int(min(pa[:, 0].min(), pb[:, 0].min())) - 1
        y0 = int(min(pa[:, 1].min(), pb[:, 1].min())) - 1
        x1 = int(max(pa[:, 0].max(), pb[:, 0].max())) + 2
        y1 = int(max(pa[:, 1].max(), pb[:, 1].max())) + 2
        if x1 <= x0 or y1 <= y0:
            continue
        ma = np.zeros((y1 - y0, x1 - x0), np.uint8)
        mb = np.zeros_like(ma)
        cv2.fillPoly(ma, [(pa - [x0, y0]).astype(np.int32)], 1)
        cv2.fillPoly(mb, [(pb - [x0, y0]).astype(np.int32)], 1)
        inter = int((ma & mb).sum())
        if inter < 30:
            continue
        ua = int(ma.sum())
        ub = int(mb.sum())
        iou = inter / max(1, ua + ub - inter)
        if iou >= 0.25:
            print(
                f"OVERLAP iou={iou:.2f} inter={inter} "
                f"A[{ia}] ({La['cx']*W:.0f},{La['cy']*H:.0f}) n={len(La['points'])} "
                f"B[{ib}] ({Lb['cx']*W:.0f},{Lb['cy']*H:.0f}) n={len(Lb['points'])}"
            )

# Draw only right-column lots (cx > 680)
vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for i, L, pts in region:
    if L["cx"] * W < 680:
        continue
    poly = [(int(x), int(y)) for x, y in pts]
    dr.polygon(poly, fill=(40, 150, 255, 100), outline=(0, 80, 255, 255))
    print("right", i, round(L["cx"] * W), round(L["cy"] * H), "n", len(L["points"]), "area", L["area"])
vis.crop((680, 190, 760, 340)).resize((320, 600), Image.NEAREST).save("scratch/midright_col_qa.png")
print("wrote midright_col_qa.png")
