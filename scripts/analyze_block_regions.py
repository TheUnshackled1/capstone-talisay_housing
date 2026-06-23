"""Analyze traced polygons per block region for slot calibration."""
import json
from pathlib import Path

REGIONS = [
    {"block": "1", "x": 0.130, "y": 0.040, "w": 0.130, "h": 0.900},
    {"block": "2", "x": 0.260, "y": 0.040, "w": 0.080, "h": 0.900},
    {"block": "3", "x": 0.335, "y": 0.030, "w": 0.115, "h": 0.320},
    {"block": "4", "x": 0.335, "y": 0.310, "w": 0.115, "h": 0.200},
    {"block": "5", "x": 0.450, "y": 0.030, "w": 0.105, "h": 0.320},
    {"block": "6", "x": 0.450, "y": 0.310, "w": 0.105, "h": 0.220},
    {"block": "7", "x": 0.560, "y": 0.030, "w": 0.120, "h": 0.320},
    {"block": "8", "x": 0.560, "y": 0.310, "w": 0.120, "h": 0.220},
    {"block": "9", "x": 0.680, "y": 0.030, "w": 0.120, "h": 0.320},
    {"block": "10", "x": 0.680, "y": 0.310, "w": 0.120, "h": 0.220},
    {"block": "11", "x": 0.800, "y": 0.040, "w": 0.095, "h": 0.900},
]

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "static/units/lot_plan_polygons.json").read_text())
lots = data["lots"]


def in_region(p, r):
    return r["x"] <= p["cx"] < r["x"] + r["w"] and r["y"] <= p["cy"] < r["y"] + r["h"]


def cluster_rows(cands, band=0.04):
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


for r in REGIONS:
    cands = [p for p in lots if in_region(p, r)]
    rows = cluster_rows(cands)
    print(f"\n=== Block {r['block']} ({len(cands)} polys, {len(rows)} rows) ===")
    lot_num = 1
    for ri, rw in enumerate(rows):
        for ci, p in enumerate(rw["items"]):
            print(
                f"  slot{lot_num}: cx={p['cx']:.3f} cy={p['cy']:.3f} area={p['area']:.5f}"
            )
            lot_num += 1
