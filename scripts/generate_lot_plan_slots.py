"""Generate per-block lot anchor slots and primary physical clusters.

Each inventory block maps to ONE physical enclosure on the plan (no lots in
road-separated pockets or neighboring boxes).  Outputs:

  static/units/lot_plan_slots.json
  static/units/lot_plan_clusters.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLY_PATH = ROOT / "static/units/lot_plan_polygons.json"
SLOTS_PATH = ROOT / "static/units/lot_plan_slots.json"
CLUSTERS_PATH = ROOT / "static/units/lot_plan_clusters.json"

# One primary physical box per block (non-overlapping).
PRIMARY_CLUSTERS = {
    "1": {"x": 0.155, "y": 0.045, "w": 0.093, "h": 0.880},
    "2": {"x": 0.248, "y": 0.045, "w": 0.072, "h": 0.880},
    "3": {"x": 0.340, "y": 0.035, "w": 0.095, "h": 0.280},
    "4": {"x": 0.345, "y": 0.310, "w": 0.115, "h": 0.135},
    "5": {"x": 0.440, "y": 0.035, "w": 0.110, "h": 0.280},
    "6": {"x": 0.455, "y": 0.335, "w": 0.090, "h": 0.135},
    "7": {"x": 0.550, "y": 0.035, "w": 0.120, "h": 0.280},
    "8": {"x": 0.555, "y": 0.335, "w": 0.115, "h": 0.135},
    "9": {"x": 0.670, "y": 0.050, "w": 0.145, "h": 0.280},
    "10": {"x": 0.695, "y": 0.355, "w": 0.115, "h": 0.045},
    "11": {"x": 0.830, "y": 0.055, "w": 0.060, "h": 0.200},
    "12": {"x": 0.838, "y": 0.255, "w": 0.035, "h": 0.620},
}

BLOCK_LAYOUTS = {
    "1": "strip_2col",
    "2": "strip_2col",
    "3": "strip_2col",
    "4": [[1, 2, 3, 4], [5, 6, 8, 7], [9]],
    "5": [[1, 2, 3, 4], [5, 6, 7, 8], [9]],
    "6": [[1, 2], [3, 4]],
    "7": [[1, 2, 3, 4], [5, 6, 7, 8], [9]],
    "8": [[1, 2, 3], [4, 5]],
    "9": [[1, 2, 3, 4], [5, 6, 7, 8], [9]],
    "10": [[1, 2, 3]],
    "11": [[1, 2]],
    "12": [[1], [2], [3], [4], [5], [6], [7], [8], [9]],
}

# Hand-calibrated slots inside primary cluster only.
MANUAL_SLOTS = {
    "4": {
        1: {"cx": 0.370, "cy": 0.347},
        2: {"cx": 0.395, "cy": 0.359},
        3: {"cx": 0.421, "cy": 0.361},
        4: {"cx": 0.447, "cy": 0.363},
        5: {"cx": 0.369, "cy": 0.388},
        6: {"cx": 0.394, "cy": 0.423},
        8: {"cx": 0.419, "cy": 0.423},
        7: {"cx": 0.443, "cy": 0.423},
        9: {"cx": 0.369, "cy": 0.433},
    },
    "6": {
        1: {"cx": 0.497, "cy": 0.366, "bounds": {"maxCx": 0.545}},
        2: {"cx": 0.531, "cy": 0.366, "bounds": {"maxCx": 0.545}},
        3: {"cx": 0.494, "cy": 0.426, "bounds": {"maxCx": 0.545}},
        4: {"cx": 0.528, "cy": 0.427, "bounds": {"maxCx": 0.545}},
        5: {"cx": 0.497, "cy": 0.366, "bounds": {"maxCx": 0.545}},
        6: {"cx": 0.531, "cy": 0.366, "bounds": {"maxCx": 0.545}},
        7: {"cx": 0.494, "cy": 0.426, "bounds": {"maxCx": 0.545}},
        8: {"cx": 0.528, "cy": 0.427, "bounds": {"maxCx": 0.545}},
        9: {"cx": 0.497, "cy": 0.366, "bounds": {"maxCx": 0.545}},
    },
    "8": {
        1: {"cx": 0.564, "cy": 0.368, "bounds": {"minCx": 0.555}},
        2: {"cx": 0.596, "cy": 0.370, "bounds": {"minCx": 0.555}},
        3: {"cx": 0.650, "cy": 0.403, "bounds": {"minCx": 0.555}},
        4: {"cx": 0.561, "cy": 0.429, "bounds": {"minCx": 0.555}},
        5: {"cx": 0.594, "cy": 0.430, "bounds": {"minCx": 0.555}},
        6: {"cx": 0.564, "cy": 0.368, "bounds": {"minCx": 0.555}},
        7: {"cx": 0.596, "cy": 0.370, "bounds": {"minCx": 0.555}},
        8: {"cx": 0.650, "cy": 0.403, "bounds": {"minCx": 0.555}},
        9: {"cx": 0.561, "cy": 0.429, "bounds": {"minCx": 0.555}},
    },
    "10": {
        1: {"cx": 0.711, "cy": 0.376},
        2: {"cx": 0.740, "cy": 0.377},
        3: {"cx": 0.769, "cy": 0.379},
    },
    "12": {
        1: {"cx": 0.8458, "cy": 0.2618},
        2: {"cx": 0.8457, "cy": 0.2952},
        3: {"cx": 0.8588, "cy": 0.3839},
        4: {"cx": 0.8471, "cy": 0.5088},
        5: {"cx": 0.8466, "cy": 0.5594},
        6: {"cx": 0.8471, "cy": 0.6354},
        7: {"cx": 0.8473, "cy": 0.6861},
        8: {"cx": 0.8476, "cy": 0.7368},
        9: {"cx": 0.8589, "cy": 0.8252},
    },
}

STRIP_2COL_SPLIT = {
    "1": 0.205,
    "2": 0.290,
    "3": 0.388,
}


def in_region(p, r):
    return r["x"] <= p["cx"] < r["x"] + r["w"] and r["y"] <= p["cy"] < r["y"] + r["h"]


def cluster_rows_fine(cands, band=0.028):
    sorted_c = sorted(cands, key=lambda x: (x["cy"], x["cx"]))
    rows = []
    for p in sorted_c:
        row = next((rw for rw in rows if abs(rw["avgCy"] - p["cy"]) <= band), None)
        if not row:
            row = {"items": [], "avgCy": p["cy"]}
            rows.append(row)
        row["items"].append(p)
        row["avgCy"] = sum(x["cy"] for x in row["items"]) / len(row["items"])
    rows.sort(key=lambda x: x["avgCy"])
    for rw in rows:
        rw["items"].sort(key=lambda x: x["cx"])
    return rows


def merge_rows_to_target(rows, target):
    rows = [{**r, "items": list(r["items"])} for r in rows]
    while len(rows) > target:
        best_i = 0
        best_gap = float("inf")
        for i in range(len(rows) - 1):
            gap = rows[i + 1]["avgCy"] - rows[i]["avgCy"]
            if gap < best_gap:
                best_gap = gap
                best_i = i
        merged = {
            "items": rows[best_i]["items"] + rows[best_i + 1]["items"],
            "avgCy": 0,
        }
        merged["avgCy"] = sum(p["cy"] for p in merged["items"]) / len(merged["items"])
        merged["items"].sort(key=lambda p: p["cx"])
        rows = rows[:best_i] + [merged] + rows[best_i + 2 :]
    return rows


def pick_n_spread(col, n):
    col = sorted(col, key=lambda p: p["cy"])
    if len(col) <= n:
        return col
    step = (len(col) - 1) / (n - 1)
    idxs = [round(i * step) for i in range(n)]
    return [col[i] for i in idxs]


def pick_row_cells(row_items, want):
    if len(row_items) <= want:
        return row_items
    sorted_row = sorted(row_items, key=lambda p: p["cx"])
    if want == 1:
        return [sorted_row[len(sorted_row) // 2]]
    step = (len(sorted_row) - 1) / (want - 1)
    idxs = [round(i * step) for i in range(want)]
    return [sorted_row[i] for i in idxs]


def strip_2col_slots(cands, block, n=9):
    if not cands:
        return {}
    mid_x = STRIP_2COL_SPLIT.get(block, sorted(p["cx"] for p in cands)[len(cands) // 2])
    left = pick_n_spread([p for p in cands if p["cx"] < mid_x], 5)
    right = pick_n_spread([p for p in cands if p["cx"] >= mid_x], 4)
    slots = {}
    for lot, p in zip([1, 3, 5, 7, 9], left):
        slots[lot] = {"cx": round(p["cx"], 4), "cy": round(p["cy"], 4)}
    for lot, p in zip([2, 4, 6, 8], right):
        slots[lot] = {"cx": round(p["cx"], 4), "cy": round(p["cy"], 4)}
    return slots


def grid_layout_slots(cands, layout):
    rows = merge_rows_to_target(cluster_rows_fine(cands), len(layout))
    slots = {}
    for row_idx, lot_nums in enumerate(layout):
        if row_idx >= len(rows):
            break
        row_items = rows[row_idx]["items"]
        if len(row_items) > len(lot_nums):
            row_items = pick_row_cells(row_items, len(lot_nums))
        for col_idx, lot in enumerate(lot_nums):
            if col_idx < len(row_items):
                p = row_items[col_idx]
                slots[lot] = {"cx": round(p["cx"], 4), "cy": round(p["cy"], 4)}
    return slots


def main():
    lots = json.loads(POLY_PATH.read_text())["lots"]
    slots_out = {"blocks": {}}
    clusters_out = {"blocks": {}}

    for block, primary in PRIMARY_CLUSTERS.items():
        layout = BLOCK_LAYOUTS[block]
        clusters_out["blocks"][block] = {
            "primary": primary,
            "layout": layout if isinstance(layout, list) else "strip_2col",
        }

        if block in MANUAL_SLOTS:
            slots_out["blocks"][block] = {
                str(k): v for k, v in sorted(MANUAL_SLOTS[block].items())
            }
            print(f"OK block {block}: manual {len(MANUAL_SLOTS[block])} slots")
            continue

        cands = [p for p in lots if in_region(p, primary)]
        if layout == "strip_2col":
            slots = strip_2col_slots(cands, block, 9)
            expected = 9
        else:
            slots = grid_layout_slots(cands, layout)
            expected = sum(len(r) for r in layout)

        status = "OK" if len(slots) >= expected else "WARN"
        print(f"{status} block {block}: {len(slots)}/{expected} slots ({len(cands)} polys)")
        slots_out["blocks"][block] = {str(k): v for k, v in sorted(slots.items())}

    SLOTS_PATH.write_text(json.dumps(slots_out, indent=2) + "\n")
    CLUSTERS_PATH.write_text(json.dumps(clusters_out, indent=2) + "\n")
    print("Wrote", SLOTS_PATH)
    print("Wrote", CLUSTERS_PATH)


if __name__ == "__main__":
    main()
