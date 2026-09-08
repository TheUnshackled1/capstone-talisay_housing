"""
Generates lot_plan_polygons_p2.json with rectangular approximations
derived from the cluster bounding boxes in lot_plan_clusters_p2.json.
Run: python scratch/gen_p2_polygons.py > static/units/lot_plan_polygons_p2.json
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).parent.parent

# Block layout: bounding box + how many lots per row
# Matches lot_plan_clusters_p2.json but adds row breakdown
BLOCKS = {
    13: {"x": 0.05, "y": 0.05, "w": 0.40, "h": 0.20, "rows": [5, 4]},
    14: {"x": 0.05, "y": 0.27, "w": 0.40, "h": 0.18, "rows": [5, 4]},
    15: {"x": 0.52, "y": 0.05, "w": 0.44, "h": 0.20, "rows": [5, 4]},
    16: {"x": 0.52, "y": 0.27, "w": 0.44, "h": 0.18, "rows": [5, 4]},
    17: {"x": 0.05, "y": 0.52, "w": 0.18, "h": 0.20, "rows": [3, 3, 3]},
    18: {"x": 0.25, "y": 0.52, "w": 0.20, "h": 0.20, "rows": [3, 3, 3]},
    19: {"x": 0.05, "y": 0.74, "w": 0.40, "h": 0.20, "rows": [5, 4]},
    20: {"x": 0.52, "y": 0.52, "w": 0.44, "h": 0.20, "rows": [5, 4]},
    21: {"x": 0.52, "y": 0.74, "w": 0.44, "h": 0.20, "rows": [5, 4]},
}

GAP = 0.003  # small visual gap between lot rectangles

def r4(v):
    return round(v, 4)

lots = []
for block, c in sorted(BLOCKS.items()):
    bx, by, bw, bh = c["x"], c["y"], c["w"], c["h"]
    rows = c["rows"]
    n_rows = len(rows)
    row_h = bh / n_rows
    lot_num = 1
    for ri, n_cols in enumerate(rows):
        ry = by + ri * row_h
        lot_w = bw / n_cols
        for ci in range(n_cols):
            rx = bx + ci * lot_w
            x1 = r4(rx + GAP)
            y1 = r4(ry + GAP)
            x2 = r4(rx + lot_w - GAP)
            y2 = r4(ry + row_h - GAP)
            cx = r4((x1 + x2) / 2)
            cy = r4((y1 + y2) / 2)
            area = r4((x2 - x1) * (y2 - y1))
            lots.append({
                "points": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
                "cx": cx,
                "cy": cy,
                "area": area,
                "block": block,
                "lot": lot_num,
            })
            lot_num += 1

output = {"image": {"w": 1024, "h": 1024}, "lots": lots}
out_path = ROOT / "static" / "units" / "lot_plan_polygons_p2.json"
out_path.write_text(json.dumps(output, indent=2))
print(f"Written {len(lots)} lot polygons to {out_path}", file=sys.stderr)
