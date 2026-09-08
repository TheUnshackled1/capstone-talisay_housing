"""
Manually calibrated Phase 2 polygon generator.
Uses detected structural lines to define exact block bounding boxes,
then divides each block into uniform lot rectangles (5+4 or 3+3+3 arrangement).

Run: python scratch/gen_p2_polygons_v2.py
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).parent.parent
OUT_PATH = ROOT / "static" / "units" / "lot_plan_polygons_p2.json"

W, H = 1008, 1024  # image dimensions

# Detected major line positions (from image analysis):
# H major: 80 (top border), 283 (TL/BL-top internal), 502 (mid road), 720 (BL-bottom internal), 972 (bottom border)
# V major: 53 (left border), 304 (BL-internal vertical split), 492 (mid road), 960 (right border)

# Block definitions: (x1, y1, x2, y2, row_layout)
# row_layout: list of lot counts per row, top to bottom
GAP = 2  # pixels between lots for visual separation

BLOCKS = {
    # Top-left quadrant: blocks 22, 23
    22: {"x1": 57,  "y1": 82,  "x2": 489, "y2": 281, "rows": [5, 4]},
    23: {"x1": 57,  "y1": 287, "x2": 489, "y2": 499, "rows": [5, 4]},
    # Top-right quadrant: blocks 24, 25
    24: {"x1": 496, "y1": 82,  "x2": 957, "y2": 281, "rows": [5, 4]},
    25: {"x1": 496, "y1": 287, "x2": 957, "y2": 499, "rows": [5, 4]},
    # Bottom-left quadrant upper-left small block: 26
    26: {"x1": 57,  "y1": 505, "x2": 302, "y2": 718, "rows": [3, 3, 3]},
    # Bottom-left quadrant upper-right small block: 27
    27: {"x1": 307, "y1": 505, "x2": 489, "y2": 718, "rows": [3, 3, 3]},
    # Bottom-left quadrant full-width lower block: 28
    28: {"x1": 57,  "y1": 724, "x2": 489, "y2": 968, "rows": [5, 4]},
    # Bottom-right quadrant: blocks 29, 30
    29: {"x1": 496, "y1": 505, "x2": 957, "y2": 718, "rows": [5, 4]},
    30: {"x1": 496, "y1": 724, "x2": 957, "y2": 968, "rows": [5, 4]},
}

def r4(v): return round(v, 4)

lots_out = []
for block_num in sorted(BLOCKS):
    b = BLOCKS[block_num]
    bx1, by1, bx2, by2 = b["x1"], b["y1"], b["x2"], b["y2"]
    rows = b["rows"]
    bw = bx2 - bx1
    bh = by2 - by1
    n_rows = len(rows)
    row_h = bh / n_rows
    lot_num = 1
    for ri, n_cols in enumerate(rows):
        ry = by1 + ri * row_h
        lot_w = bw / n_cols
        for ci in range(n_cols):
            rx = bx1 + ci * lot_w
            x1 = rx + GAP
            y1 = ry + GAP
            x2 = rx + lot_w - GAP
            y2 = ry + row_h - GAP
            nx1 = r4(x1 / W); ny1 = r4(y1 / H)
            nx2 = r4(x2 / W); ny2 = r4(y2 / H)
            cx  = r4((nx1+nx2)/2)
            cy  = r4((ny1+ny2)/2)
            lots_out.append({
                "points": [[nx1,ny1],[nx2,ny1],[nx2,ny2],[nx1,ny2]],
                "cx": cx, "cy": cy,
                "area": r4((nx2-nx1)*(ny2-ny1)),
                "block": block_num, "lot": lot_num,
            })
            lot_num += 1
    print(f"Block {block_num}: {lot_num-1} lots, bbox=({bx1},{by1})-({bx2},{by2})", file=sys.stderr)

output = {"image": {"w": W, "h": H}, "lots": lots_out}
OUT_PATH.write_text(json.dumps(output, indent=2))
print(f"\nTotal: {len(lots_out)} lots → {OUT_PATH}", file=sys.stderr)
