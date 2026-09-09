"""Hardcoded AABB inset fits for shaded gray pads."""
from pathlib import Path
import json

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

ink = cv2.dilate((gray < 100).astype(np.uint8) * 255, np.ones((2, 2), np.uint8), 1)
pad = ((gray >= 132) & (gray <= 172)).astype(np.uint8) * 255
pad = cv2.bitwise_and(pad, cv2.bitwise_not(ink))
# stronger split
split = cv2.erode(pad, np.ones((3, 3), np.uint8), 1)

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]


def aabb_fit(sx, sy, inset=1.5):
    ix, iy = int(round(sx)), int(round(sy))
    if split[iy, ix] == 0:
        for r in range(1, 14):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and split[yy, xx]:
                        ix, iy = xx, yy
                        break
                else:
                    continue
                break
            else:
                continue
            break
    if split[iy, ix] == 0:
        return None
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = split.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    cell = cv2.dilate(cell, np.ones((3, 3), np.uint8), 1)
    cell = cv2.bitwise_and(cell, pad)
    ys, xs = np.where(cell > 0)
    if len(xs) < 40:
        return None
    x0, x1 = float(xs.min()) + inset, float(xs.max()) - inset
    y0, y1 = float(ys.min()) + inset, float(ys.max()) - inset
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    box = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32)
    return box


img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
boxes = []
for sx, sy in seeds:
    box = aabb_fit(sx, sy)
    if box is None:
        print("fail", sx, sy)
        continue
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    boxes.append((sx, sy, box))
    print(f"({sx:.0f},{sy:.0f}) {box[0][0]:.1f},{box[0][1]:.1f} -> {box[2][0]:.1f},{box[2][1]:.1f}")

out = ROOT / "scratch" / "shaded_aabb_fit.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)

# Also patch JSON directly for these 8
path = ROOT / "static" / "units" / "lot_plan_polygons.json"
data = json.loads(path.read_text())
lots = data["lots"]
# remove existing in region
lots = [L for L in lots if not (95 <= L["cx"] * W <= 210 and 85 <= L["cy"] * H <= 155)]
for sx, sy, box in boxes:
    pts = [[round(float(x) / W, 4), round(float(y) / H, 4)] for x, y in box]
    # order
    arr = np.array(pts)
    ang = np.arctan2(arr[:, 1] - arr[:, 1].mean(), arr[:, 0] - arr[:, 0].mean())
    pts = [pts[int(j)] for j in np.argsort(ang)]
    cx = float(box[:, 0].mean())
    cy = float(box[:, 1].mean())
    area = float((box[2][0] - box[0][0]) * (box[2][1] - box[0][1]) / (W * H))
    lots.append({
        "points": pts,
        "cx": round(cx / W, 4),
        "cy": round(cy / H, 4),
        "area": round(area, 4),
    })
lots.sort(key=lambda L: (L["cy"], L["cx"]))
data["lots"] = lots
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("patched JSON lots=", len(lots))
