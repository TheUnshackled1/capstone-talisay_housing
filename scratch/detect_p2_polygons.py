"""
Definitive Phase 2 lot detector.
Uses very high threshold to find ONLY major structural lines (borders + main roads),
giving exactly the 9 block regions we expect (blocks 13-21).
Then uses fine detection within each block to find individual lots.

Run: python scratch/detect_p2_polygons.py
"""
import json, pathlib, sys
from PIL import Image

ROOT = pathlib.Path(__file__).parent.parent
IMG_PATH = ROOT / "static" / "images" / "lot_plan_roads_p2.png"
OUT_PATH = ROOT / "static" / "units" / "lot_plan_polygons_p2.json"

img = Image.open(IMG_PATH).convert("L")
W, H = img.size
pix = img.load()
print(f"Image: {W}×{H}", file=sys.stderr)

DARK = 120

def row_density(y):
    return sum(1 for x in range(W) if pix[x, y] < DARK) / W

def col_density(x):
    return sum(1 for y in range(H) if pix[x, y] < DARK) / H

def row_density_range(y, x1, x2):
    span = x2 - x1
    return sum(1 for x in range(x1, x2) if pix[x, y] < DARK) / span if span else 0

def col_density_range(x, y1, y2):
    span = y2 - y1
    return sum(1 for y in range(y1, y2) if pix[x, y] < DARK) / span if span else 0

def find_lines(density_fn, n, thresh, min_gap=10):
    vals = [density_fn(i) for i in range(n)]
    lines = []
    in_line = False; start = 0
    for i, v in enumerate(vals):
        if v >= thresh:
            if not in_line: in_line = True; start = i
        else:
            if in_line:
                in_line = False
                mid = (start + i) // 2
                if not lines or mid - lines[-1] >= min_gap:
                    lines.append(mid)
    if in_line:
        mid = (start + n) // 2
        if not lines or mid - lines[-1] >= min_gap:
            lines.append(mid)
    return lines

# --- Level 1: Only MAJOR structural lines ---
# Row threshold 0.35 → ~4 rows (borders + 1 main road)
# Col threshold 0.50 → ~4 cols (borders + 1 main road)
H_MAJOR = find_lines(lambda y: row_density(y), H, thresh=0.35, min_gap=20)
V_MAJOR = find_lines(lambda x: col_density(x), W, thresh=0.50, min_gap=20)
print(f"Major H-lines ({len(H_MAJOR)}): {H_MAJOR}", file=sys.stderr)
print(f"Major V-lines ({len(V_MAJOR)}): {V_MAJOR}", file=sys.stderr)

# --- Build block regions from major lines ---
# Expect ~3 row gaps × ~3 col gaps = 9 block regions
block_regions = []
MIN_BW = 80; MIN_BH = 60
MAX_BW = W; MAX_BH = H

for yi in range(len(H_MAJOR) - 1):
    by1 = H_MAJOR[yi] + 3
    by2 = H_MAJOR[yi + 1] - 3
    if not (MIN_BH <= by2-by1 <= MAX_BH): continue
    for xi in range(len(V_MAJOR) - 1):
        bx1 = V_MAJOR[xi] + 3
        bx2 = V_MAJOR[xi + 1] - 3
        if not (MIN_BW <= bx2-bx1 <= MAX_BW): continue
        # Skip if center is dark (road)
        cx = (bx1+bx2)//2; cy = (by1+by2)//2
        dark_ct = sum(1 for dy in range(-4,5) for dx in range(-4,5)
                      if 0<=cx+dx<W and 0<=cy+dy<H and pix[cx+dx,cy+dy]<DARK)
        if dark_ct > 30: continue
        block_regions.append((bx1, by1, bx2, by2))

print(f"Block regions found: {len(block_regions)}", file=sys.stderr)

# --- Level 2: Fine detection within each block ---
def find_local_lines(density_fn, start, end, thresh=0.10, min_gap=5):
    lines = []
    in_line = False; seg_start = start
    for i in range(start, end+1):
        v = density_fn(i)
        if v >= thresh:
            if not in_line: in_line = True; seg_start = i
        else:
            if in_line:
                in_line = False
                mid = (seg_start + i) // 2
                if not lines or mid - lines[-1] >= min_gap:
                    lines.append(mid)
    if in_line:
        mid = (seg_start + end) // 2
        if not lines or mid - lines[-1] >= min_gap:
            lines.append(mid)
    return lines

MIN_LOT_W = 12; MIN_LOT_H = 10
MAX_LOT_W = 200; MAX_LOT_H = 180

all_block_lots = []
for (bx1, by1, bx2, by2) in block_regions:
    h_local = find_local_lines(
        lambda y, x1=bx1, x2=bx2: row_density_range(y, x1, x2),
        by1, by2, thresh=0.12, min_gap=5
    )
    v_local = find_local_lines(
        lambda x, y1=by1, y2=by2: col_density_range(x, y1, y2),
        bx1, bx2, thresh=0.12, min_gap=5
    )

    # Always add block edges
    if not h_local or h_local[0] > by1+5: h_local = [by1] + h_local
    if not h_local or h_local[-1] < by2-5: h_local = h_local + [by2]
    if not v_local or v_local[0] > bx1+5: v_local = [bx1] + v_local
    if not v_local or v_local[-1] < bx2-5: v_local = v_local + [bx2]

    lots = []
    for yi in range(len(h_local)-1):
        ly1 = h_local[yi]+1; ly2 = h_local[yi+1]-1
        if not (MIN_LOT_H <= ly2-ly1 <= MAX_LOT_H): continue
        for xi in range(len(v_local)-1):
            lx1 = v_local[xi]+1; lx2 = v_local[xi+1]-1
            if not (MIN_LOT_W <= lx2-lx1 <= MAX_LOT_W): continue
            lcx=(lx1+lx2)//2; lcy=(ly1+ly2)//2
            dark_ct = sum(1 for dy in range(-2,3) for dx in range(-2,3)
                          if 0<=lcx+dx<W and 0<=lcy+dy<H and pix[lcx+dx,lcy+dy]<DARK)
            if dark_ct > 10: continue
            lots.append((lx1, ly1, lx2, ly2))

    if lots:
        all_block_lots.append(((bx1,by1,bx2,by2), lots))

print(f"\nBlocks with detected lots: {len(all_block_lots)}", file=sys.stderr)

# --- Assign block numbers (spatial order) ---
MID_X = W * 0.49; MID_Y = H * 0.49

def blk_center(b):
    bb = b[0]
    return ((bb[1]+bb[3])/2, (bb[0]+bb[2])/2)

tl = sorted([b for b in all_block_lots if (b[0][0]+b[0][2])/2<MID_X and (b[0][1]+b[0][3])/2<MID_Y], key=blk_center)
tr = sorted([b for b in all_block_lots if (b[0][0]+b[0][2])/2>=MID_X and (b[0][1]+b[0][3])/2<MID_Y], key=blk_center)
bl = sorted([b for b in all_block_lots if (b[0][0]+b[0][2])/2<MID_X and (b[0][1]+b[0][3])/2>=MID_Y], key=blk_center)
br = sorted([b for b in all_block_lots if (b[0][0]+b[0][2])/2>=MID_X and (b[0][1]+b[0][3])/2>=MID_Y], key=blk_center)
ordered = tl + tr + bl + br
print(f"Quadrant split: TL={len(tl)} TR={len(tr)} BL={len(bl)} BR={len(br)}", file=sys.stderr)

MARGIN = 1
lots_out = []
for blk_off, ((bx1,by1,bx2,by2), lots) in enumerate(ordered):
    block_num = 13 + blk_off
    sorted_lots = sorted(lots, key=lambda c: (round((c[1]+c[3])/2/12)*12, c[0]))
    print(f"  Block {block_num} ({bx1},{by1})-({bx2},{by2}): {len(sorted_lots)} lots", file=sys.stderr)
    for lot_num, (x1,y1,x2,y2) in enumerate(sorted_lots, start=1):
        nx1=round((x1+MARGIN)/W,4); ny1=round((y1+MARGIN)/H,4)
        nx2=round((x2-MARGIN)/W,4); ny2=round((y2-MARGIN)/H,4)
        cx=round((nx1+nx2)/2,4); cy=round((ny1+ny2)/2,4)
        lots_out.append({
            "points":[[nx1,ny1],[nx2,ny1],[nx2,ny2],[nx1,ny2]],
            "cx":cx,"cy":cy,"area":round((nx2-nx1)*(ny2-ny1),6),
            "block":block_num,"lot":lot_num,
        })

output = {"image":{"w":W,"h":H},"lots":lots_out}
OUT_PATH.write_text(json.dumps(output, indent=2))
print(f"\nTotal: {len(lots_out)} lots → {OUT_PATH}", file=sys.stderr)
