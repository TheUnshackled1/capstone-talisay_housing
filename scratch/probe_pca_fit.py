"""PCA-oriented pad fit — matches gray drawing orientation."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
rgb = np.array(Image.open(ROOT / "static/images/lot_plan_roads.png").convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
H, W = gray.shape

ink = cv2.dilate((gray < 100).astype(np.uint8) * 255, np.ones((2, 2), np.uint8), 1)
pad = ((gray >= 130) & (gray <= 175)).astype(np.uint8) * 255
pad = cv2.bitwise_and(pad, cv2.bitwise_not(ink))
pad = cv2.morphologyEx(pad, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), 1)
pad_split = cv2.erode(pad, np.ones((2, 2), np.uint8), 1)

seeds = [
    (108.0, 96.0), (138.0, 101.0), (167.0, 106.0), (196.0, 111.0),
    (104.0, 116.0), (133.0, 126.0), (161.0, 134.0), (194.0, 145.0),
]


def get_cell(sx, sy):
    ix, iy = int(round(sx)), int(round(sy))
    src = pad_split
    if src[iy, ix] == 0:
        for r in range(1, 14):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    xx, yy = ix + dx, iy + dy
                    if 0 <= xx < W and 0 <= yy < H and src[yy, xx]:
                        ix, iy = xx, yy
                        break
                else:
                    continue
                break
            else:
                continue
            break
    if src[iy, ix] == 0:
        return None
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flood = src.copy()
    cv2.floodFill(flood, mask, (ix, iy), 200)
    cell = (flood == 200).astype(np.uint8) * 255
    cell = cv2.dilate(cell, np.ones((3, 3), np.uint8), 1)
    cell = cv2.bitwise_and(cell, pad)
    ys, xs = np.where(cell > 0)
    if len(xs) < 40:
        return None
    return np.column_stack([xs.astype(np.float32), ys.astype(np.float32)])


def pca_box(pts, shrink=0.95):
    mean = pts.mean(axis=0)
    X = pts - mean
    # covariance
    cov = np.cov(X.T)
    evals, evecs = np.linalg.eigh(cov)
    # largest eigenvalue = long axis
    order = np.argsort(evals)[::-1]
    evecs = evecs[:, order]
    ux, uy = evecs[:, 0], evecs[:, 1]
    # project
    proj = X @ evecs
    mins = proj.min(axis=0)
    maxs = proj.max(axis=0)
    # corners in PCA space
    corners_local = np.array([
        [mins[0], mins[1]],
        [maxs[0], mins[1]],
        [maxs[0], maxs[1]],
        [mins[0], maxs[1]],
    ], dtype=np.float32)
    corners = corners_local @ evecs.T + mean
    c = corners.mean(axis=0)
    corners = c + (corners - c) * shrink
    return corners.astype(np.float32), mean, float(np.degrees(np.arctan2(ux[1], ux[0])))


img = Image.fromarray(rgb)
dr = ImageDraw.Draw(img)
results = []
for sx, sy in seeds:
    pts = get_cell(sx, sy)
    if pts is None:
        print("fail", sx, sy)
        continue
    box, mean, ang = pca_box(pts, shrink=0.96)
    poly = [(float(x), float(y)) for x, y in box]
    dr.line(poly + [poly[0]], fill=(0, 220, 80), width=2)
    results.append((sx, sy, box, mean, ang))
    print(f"({sx:.0f},{sy:.0f}) -> ({mean[0]:.1f},{mean[1]:.1f}) ang={ang:.1f} n={len(pts)}")

out = ROOT / "scratch" / "shaded_pca_fit.png"
img.crop((90, 70, 230, 180)).save(out)
print("wrote", out)
# dump boxes for hardcoding if good
for sx, sy, box, mean, ang in results:
    print("BOX", sx, sy, box.tolist())
