"""Assign block+lot identity to each traced polygon.

Reads lot_plan_polygons.json, clusters the 325 polygons into blocks by
spatial proximity, assigns lot numbers within each block (reading order),
and writes the updated JSON back.

The physical subdivision plan (GK Cabatangan) has clearly separated block
groups. This script uses the polygon centroids and agglomerative spatial
clustering to find those groups automatically.

Usage:
    python scripts/assign_block_lots.py [--html]  # --html writes a visual map
"""

from __future__ import annotations
import json, math, sys
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
JSON_PATH = BASE_DIR / "static" / "units" / "lot_plan_polygons.json"
HTML_PATH = BASE_DIR / "static" / "units" / "lot_plan_index_map.html"

def load():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def cluster_blocks(lots, threshold=0.045):
    """Simple agglomerative clustering of polygon centroids.
    
    Polygons whose centroids are within `threshold` (normalized 0..1 coords)
    are grouped into the same block.
    """
    n = len(lots)
    centroids = [(l["cx"], l["cy"]) for l in lots]
    labels = list(range(n))  # each starts as its own cluster

    def find(x):
        while labels[x] != x:
            labels[x] = labels[labels[x]]
            x = labels[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            labels[ra] = rb

    # Union polygons that are close together
    for i in range(n):
        for j in range(i + 1, n):
            if dist(centroids[i], centroids[j]) < threshold:
                union(i, j)

    # Collect groups
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    # Sort groups by average Y then X (top-to-bottom, left-to-right)
    sorted_groups = sorted(
        groups.values(),
        key=lambda idxs: (
            sum(centroids[i][1] for i in idxs) / len(idxs),
            sum(centroids[i][0] for i in idxs) / len(idxs),
        ),
    )
    return sorted_groups


def assign(data, threshold=0.045):
    lots = data["lots"]
    groups = cluster_blocks(lots, threshold)

    print(f"Found {len(groups)} block clusters from {len(lots)} polygons")
    print()

    block_num = 1
    for group_idxs in groups:
        # Sort lots within block by reading order (top-to-bottom, left-to-right)
        band = 0.015  # vertical band tolerance within a block
        group_idxs_sorted = sorted(
            group_idxs,
            key=lambda i: (round(lots[i]["cy"] / band), lots[i]["cx"]),
        )
        for lot_num_idx, poly_idx in enumerate(group_idxs_sorted, 1):
            lots[poly_idx]["block"] = block_num
            lots[poly_idx]["lot"] = lot_num_idx

        count = len(group_idxs)
        avg_cx = sum(lots[i]["cx"] for i in group_idxs) / count
        avg_cy = sum(lots[i]["cy"] for i in group_idxs) / count
        print(f"  Block {block_num:2d}: {count:3d} lots  (center ~ {avg_cx:.3f}, {avg_cy:.3f})")
        block_num += 1

    return data


def write_html(data):
    """Write an HTML visualization showing polygon indices + block assignments on the plan."""
    lots = data["lots"]
    svg_w, svg_h = 1000, 1000
    polys_svg = []
    for i, lot in enumerate(lots):
        pts = " ".join(f"{p[0]*svg_w:.1f},{p[1]*svg_h:.1f}" for p in lot["points"])
        cx, cy = lot["cx"] * svg_w, lot["cy"] * svg_h
        block = lot.get("block", "?")
        lot_num = lot.get("lot", "?")
        label = f"B{block}-L{lot_num}"
        # Color by block number
        hue = ((block - 1) * 31) % 360 if isinstance(block, int) else 0
        fill = f"hsla({hue}, 60%, 70%, 0.5)"
        polys_svg.append(
            f'<g>'
            f'<polygon points="{pts}" fill="{fill}" stroke="#333" stroke-width="0.8"/>'
            f'<text x="{cx:.0f}" y="{cy:.0f}" font-size="7" text-anchor="middle" '
            f'dominant-baseline="central" fill="#000" font-weight="700" '
            f'paint-order="stroke" stroke="#fff" stroke-width="2">{label}</text>'
            f'</g>'
        )
    html = f"""<!DOCTYPE html>
<html><head><title>Lot Plan - Block Assignment Map</title>
<style>body{{margin:0;background:#f0f0f0;display:flex;justify-content:center;padding:1rem}}
.wrap{{position:relative;max-width:1024px;width:100%}}
img{{width:100%;display:block}}
svg{{position:absolute;inset:0;width:100%;height:100%}}</style></head>
<body><div class="wrap">
<img src="../images/lot_plan.png" alt="plan">
<svg viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="none">
{''.join(polys_svg)}
</svg></div></body></html>"""
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"\nVisual map -> {HTML_PATH}")


def main():
    data = load()
    do_html = "--html" in sys.argv

    # Try different thresholds to get reasonable block count
    # The physical plan appears to have ~25-35 blocks
    threshold = 0.042
    data = assign(data, threshold)

    JSON_PATH.write_text(json.dumps(data), encoding="utf-8")
    print(f"\nUpdated {JSON_PATH}")

    if do_html:
        write_html(data)


if __name__ == "__main__":
    main()
