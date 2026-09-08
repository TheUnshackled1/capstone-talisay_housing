"""
DEPRECATED — oversized uniform block grids (do not use for production overlays).

Use instead:
    python scratch/gen_p2_polygons_v3.py

That detector matches drawn lot sizes and writes lot_plan_polygons_p2.json
without poisoned block/lot labels (map binding uses plan_polygon_index).
"""
raise SystemExit(
    "gen_p2_polygons_v2.py is retired (boxes were ~4x too large). "
    "Run: python scratch/gen_p2_polygons_v3.py"
)
