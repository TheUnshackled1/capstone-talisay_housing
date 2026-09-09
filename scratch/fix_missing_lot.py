"""Patch the force-seeded lot at (186,416) to match neighbor orientation/size."""
import json
from pathlib import Path

import cv2
import numpy as np

W, H = 906, 543
path = Path("static/units/lot_plan_polygons.json")
data = json.loads(path.read_text(encoding="utf-8"))
lots = data["lots"]

# Find neighbors near target
target = (186.0 / W, 416.0 / H)
nbrs = []
for i, L in enumerate(lots):
    d = ((L["cx"] - target[0]) ** 2 + (L["cy"] - target[1]) ** 2) ** 0.5
    if 0.005 < d < 0.04:
        nbrs.append((d, i, L))
nbrs.sort()
print("neighbors:", [(i, L["cx"] * W, L["cy"] * H, L["area"]) for _, i, L in nbrs[:6]])

# Use two nearest real lots (458-ish and 466-ish) for orientation
left = min(nbrs, key=lambda t: t[2]["cx"])[2]
right = max(nbrs[:4], key=lambda t: t[2]["cx"])[2]
# Average edge vectors from left lot quad
pts_l = np.array(left["points"], dtype=float)
# order already angular; take longest side as width direction
edges = []
for a, b in zip(pts_l, np.roll(pts_l, -1, axis=0)):
    edges.append(b - a)
edges = np.array(edges)
lengths = np.linalg.norm(edges, axis=1)
long_i = int(np.argmax(lengths))
short_i = int(np.argmin(lengths))
ux = edges[long_i] / (lengths[long_i] + 1e-9)
uy = edges[short_i] / (lengths[short_i] + 1e-9)
# size from neighbors (normalized -> pixels)
side = 0.5 * (np.sqrt(left["area"] * W * H) + np.sqrt(right["area"] * W * H))
hw = (side * 0.48) / W  # half-width in norm x? use pixel then convert
# Build quad in pixel space then normalize
cx, cy = 186.0, 416.0
# Use pixel unit vectors from neighbor in pixel space
pts_lp = pts_l * np.array([W, H])
edges_p = []
for a, b in zip(pts_lp, np.roll(pts_lp, -1, axis=0)):
    edges_p.append(b - a)
edges_p = np.array(edges_p)
len_p = np.linalg.norm(edges_p, axis=1)
ux = edges_p[int(np.argmax(len_p))]
uy = edges_p[int(np.argmin(len_p))]
ux = ux / (np.linalg.norm(ux) + 1e-9)
uy = uy / (np.linalg.norm(uy) + 1e-9)
# Ensure uy is roughly perpendicular
uy = np.array([-ux[1], ux[0]])
half_w = side * 0.45
half_h = side * 0.40
corners = np.array(
    [
        [cx, cy] - ux * half_w - uy * half_h,
        [cx, cy] + ux * half_w - uy * half_h,
        [cx, cy] + ux * half_w + uy * half_h,
        [cx, cy] - ux * half_w + uy * half_h,
    ]
)
# shrink
c = corners.mean(axis=0)
corners = c + (corners - c) * 0.90

def r4(v):
    return round(float(v), 4)

# angular order
angs = np.arctan2(corners[:, 1] - c[1], corners[:, 0] - c[0])
corners = corners[np.argsort(angs)]
pts = [[r4(p[0] / W), r4(p[1] / H)] for p in corners]

# Replace lot 461 or insert
replaced = False
for i, L in enumerate(lots):
    if abs(L["cx"] * W - 186) < 2 and abs(L["cy"] * H - 416) < 3:
        lots[i] = {
            "points": pts,
            "cx": r4(cx / W),
            "cy": r4(cy / H),
            "area": r4((half_w * 2 * half_h * 2) / (W * H)),
        }
        print("replaced", i, lots[i])
        replaced = True
        break
if not replaced:
    lots.append(
        {
            "points": pts,
            "cx": r4(cx / W),
            "cy": r4(cy / H),
            "area": r4((half_w * 2 * half_h * 2) / (W * H)),
        }
    )
    print("appended")

lots.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = lots
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("wrote", len(lots), "lots")

# QA crop
rgb = np.array(__import__("PIL").Image.open("static/images/lot_plan_roads.png").convert("RGB"))
vis = rgb.copy()
for L in lots:
    cx2, cy2 = L["cx"] * W, L["cy"] * H
    if 130 <= cx2 <= 230 and 330 <= cy2 <= 450:
        p = np.array([[pp[0] * W, pp[1] * H] for pp in L["points"]], np.int32)
        cv2.polylines(vis, [p], True, (0, 200, 255), 1)
__import__("PIL").Image.fromarray(vis[330:450, 130:230]).save("scratch/crop_user_fixed.png")
print("QA scratch/crop_user_fixed.png")
