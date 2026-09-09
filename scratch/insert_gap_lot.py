"""Insert oriented lot in the gap between #451 and #458."""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

W, H = 906, 543
path = Path("static/units/lot_plan_polygons.json")
data = json.loads(path.read_text(encoding="utf-8"))
lots = data["lots"]


def r4(v):
    return round(float(v), 4)


def oriented_lot(cx, cy, ref_lot, scale=1.0):
    pts_lp = np.array(ref_lot["points"], dtype=float) * np.array([W, H])
    edges = np.array([b - a for a, b in zip(pts_lp, np.roll(pts_lp, -1, axis=0))])
    lengths = np.linalg.norm(edges, axis=1)
    ux = edges[int(np.argmax(lengths))]
    ux = ux / (np.linalg.norm(ux) + 1e-9)
    uy = np.array([-ux[1], ux[0]])
    side = np.sqrt(ref_lot["area"] * W * H) * scale
    half_w, half_h = side * 0.48, side * 0.42
    corners = np.array(
        [
            [cx, cy] - ux * half_w - uy * half_h,
            [cx, cy] + ux * half_w - uy * half_h,
            [cx, cy] + ux * half_w + uy * half_h,
            [cx, cy] - ux * half_w + uy * half_h,
        ]
    )
    c = corners.mean(axis=0)
    corners = c + (corners - c) * 0.90
    angs = np.arctan2(corners[:, 1] - c[1], corners[:, 0] - c[0])
    corners = corners[np.argsort(angs)]
    pts = [[r4(p[0] / W), r4(p[1] / H)] for p in corners]
    return {
        "points": pts,
        "cx": r4(cx / W),
        "cy": r4(cy / H),
        "area": r4((half_w * 2 * half_h * 2) / (W * H)),
    }


# ref = lot near 174,415
ref = next(L for L in lots if abs(L["cx"] * W - 174) < 3 and abs(L["cy"] * H - 415) < 3)
new = oriented_lot(163.4, 407.4, ref, scale=1.05)

# drop weak overlapping tiny seed at 186,416 if it overlaps badly? keep it
# remove any existing lot too close to new center
kept = []
for L in lots:
    d = ((L["cx"] * W - 163.4) ** 2 + (L["cy"] * H - 407.4) ** 2) ** 0.5
    if d < 8:
        print("dropping near", L["cx"] * W, L["cy"] * H)
        continue
    kept.append(L)
kept.append(new)
kept.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = kept
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("lots", len(kept), "added", new)

rgb = np.array(Image.open("static/images/lot_plan_roads.png").convert("RGB"))
vis = rgb.copy()
for i, L in enumerate(kept):
    cx, cy = L["cx"] * W, L["cy"] * H
    if 130 <= cx <= 230 and 330 <= cy <= 450:
        p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], np.int32)
        cv2.polylines(vis, [p], True, (0, 200, 255), 1)
        cv2.putText(vis, str(i), (int(cx) - 10, int(cy) + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (255, 0, 0), 1)
Image.fromarray(vis[330:450, 130:230]).save("scratch/crop_user_fixed.png")
print("QA ok")
