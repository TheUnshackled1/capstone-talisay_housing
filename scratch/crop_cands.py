from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw

W, H = 906, 543
rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
Image.fromarray(rgb).crop((580, 200, 740, 320)).resize((480, 360), Image.NEAREST).save("scratch/cand_a.png")
Image.fromarray(rgb).crop((620, 180, 780, 340)).resize((480, 480), Image.NEAREST).save("scratch/cand_b.png")
Image.fromarray(rgb).crop((200, 80, 400, 250)).resize((480, 400), Image.NEAREST).save("scratch/cand_c.png")
Image.fromarray(rgb).crop((350, 90, 550, 260)).resize((480, 400), Image.NEAREST).save("scratch/cand_d.png")

data = json.loads(Path("static/units/lot_plan_polygons.json").read_text(encoding="utf-8"))
vis = Image.fromarray(rgb.copy())
dr = ImageDraw.Draw(vis, "RGBA")
for L in data["lots"]:
    cx, cy = L["cx"] * W, L["cy"] * H
    if 580 <= cx <= 740 and 200 <= cy <= 320:
        pts = [(int(p[0] * W), int(p[1] * H)) for p in L["points"]]
        dr.polygon(pts, outline=(0, 220, 255, 255), fill=(40, 180, 255, 80))
        print("poly", round(cx), round(cy), "n", len(L["points"]))
vis.crop((580, 200, 740, 320)).resize((480, 360), Image.NEAREST).save("scratch/cand_a_overlay.png")
print("done")
