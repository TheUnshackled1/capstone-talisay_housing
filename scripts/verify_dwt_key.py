import re
from pathlib import Path

EXPECTED = (
    "t0198EQYAALQxSa0io9PGcQuw2Yi74vQrWZMOHP9IBF8aWco5Nhw/Hsb/UyH14T6FTJtjcuAJvlz1QxXt+d1dW4XmeZECu7bXnZMHOKW/U6i/EwOc/MhJNO2vmk7b7PO2CRyBeQfkuA4HgBJIazkBi/2O3hkygFuANABprQEtoLqLUHwui7d9Xmv634HWnDzAKf2dZUD6ODHAyY+cISBOybzDbtcUEJQ3JwO4BUgVwO9HdgkInQFuAVIFllOKOQNIRa065Q8iQjgu"
)
OLD_PREFIX = "t0197EQYA"
ROOT = Path(__file__).resolve().parents[1] / "static" / "Dynamic Web TWAIN SDK 19.3.3"
PROD = ROOT / "Resources" / "dynamsoft.webtwain.config.js"

configs = sorted(ROOT.rglob("dynamsoft.webtwain.config.js"))
issues = []
for p in configs:
    text = p.read_text(encoding="utf-8")
    m = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("///") or "ProductKey" not in line:
            continue
        hit = re.search(r"Dynamsoft\.DWT\.ProductKey = '([^']+)'", line)
        if hit:
            m = hit
            break
    if not m:
        issues.append(f"NO KEY: {p.relative_to(ROOT.parent.parent)}")
    elif m.group(1) != EXPECTED:
        issues.append(f"MISMATCH ({len(m.group(1))} chars): {p.relative_to(ROOT.parent.parent)}")
    elif OLD_PREFIX in text:
        issues.append(f"OLD KEY REMAINS: {p.relative_to(ROOT.parent.parent)}")

print(f"Config files checked: {len(configs)}")
print(f"Production file: {PROD}")
if PROD.exists():
    prod_text = PROD.read_text(encoding="utf-8")
    prod_m = None
    for line in prod_text.splitlines():
        if line.strip().startswith("///") or "ProductKey" not in line:
            continue
        hit = re.search(r"Dynamsoft\.DWT\.ProductKey = '([^']+)'", line)
        if hit:
            prod_m = hit
            break
    print(f"Production key matches email: {prod_m.group(1) == EXPECTED if prod_m else False}")
print(f"Old key (t0120...) anywhere in SDK: {any(OLD_PREFIX in p.read_text(encoding='utf-8') for p in configs)}")
if issues:
    print("ISSUES:")
    for i in issues:
        print(" -", i)
else:
    print("ALL OK")
