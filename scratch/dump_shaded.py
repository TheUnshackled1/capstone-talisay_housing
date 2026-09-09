import json
from pathlib import Path

W, H = 906, 543
data = json.loads(Path("static/units/lot_plan_polygons.json").read_text(encoding="utf-8"))
lots = data["lots"]
print("total", len(lots))
shaded = []
for L in lots:
    cx, cy = L["cx"] * W, L["cy"] * H
    if 95 <= cx <= 215 and 80 <= cy <= 160:
        shaded.append(L)
        print(f"{cx:.1f},{cy:.1f} n={len(L['points'])} area={L['area']}")
print("shaded count", len(shaded))
# dump one polygon in px
L = shaded[-1]
pts = [(p[0] * W, p[1] * H) for p in L["points"]]
print("BR pts", pts)
