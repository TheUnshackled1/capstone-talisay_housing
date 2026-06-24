"""Assign block 1 / lots 2–10 metadata on the left-strip plan polygons.

Nearest traced polygon to each slot center is relabeled; lot 10 uses an
extrapolated slot when no anchor exists in lot_plan_slots.json.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
POLY_PATH = BASE_DIR / "static" / "units" / "lot_plan_polygons.json"
SLOTS_PATH = BASE_DIR / "static" / "units" / "lot_plan_slots.json"
MAX_DIST = 0.035


def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def rect(cx: float, cy: float, hw: float = 0.016, hh: float = 0.012) -> list[list[float]]:
    return [
        [cx - hw, cy - hh],
        [cx + hw, cy - hh],
        [cx + hw, cy + hh],
        [cx - hw, cy + hh],
    ]


def main() -> None:
    data = json.loads(POLY_PATH.read_text(encoding="utf-8"))
    slots = json.loads(SLOTS_PATH.read_text(encoding="utf-8"))["blocks"]["1"]
    lots = data["lots"]

    positions: dict[int, tuple[float, float]] = {}
    for lot_num in range(2, 10):
        slot = slots[str(lot_num)]
        positions[lot_num] = (slot["cx"], slot["cy"])

    cy8 = slots["8"]["cy"]
    cy9 = slots["9"]["cy"]
    cx9 = slots["9"]["cx"]
    positions[10] = (cx9, min(0.92, cy9 + (cy9 - cy8)))

    used_idx: set[int] = set()
    for lot_num, target in sorted(positions.items()):
        existing = next(
            (i for i, p in enumerate(lots) if p.get("block") == 1 and p.get("lot") == lot_num),
            None,
        )
        if existing is not None:
            print(f"B1 L{lot_num}: already set (index {existing})")
            used_idx.add(existing)
            continue

        best_i = None
        best_d = MAX_DIST
        for i, p in enumerate(lots):
            if i in used_idx:
                continue
            if p.get("block") == 1 and p.get("lot") == 1:
                continue
            d = dist((p["cx"], p["cy"]), target)
            if d < best_d:
                best_d = d
                best_i = i

        if best_i is not None:
            lots[best_i]["block"] = 1
            lots[best_i]["lot"] = lot_num
            used_idx.add(best_i)
            print(f"B1 L{lot_num}: relabeled polygon {best_i} (d={best_d:.4f})")
            continue

        cx, cy = target
        hw, hh = 0.016, 0.012
        lots.append(
            {
                "points": rect(cx, cy, hw, hh),
                "cx": cx,
                "cy": cy,
                "area": 4 * hw * hh,
                "block": 1,
                "lot": lot_num,
            }
        )
        print(f"B1 L{lot_num}: added synthetic polygon at ({cx:.4f}, {cy:.4f})")

    POLY_PATH.write_text(json.dumps(data), encoding="utf-8")
    print(f"Updated {POLY_PATH}")


if __name__ == "__main__":
    main()
