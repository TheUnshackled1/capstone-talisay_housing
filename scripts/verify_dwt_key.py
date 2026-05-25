import re
from pathlib import Path

EXPECTED = (
    "t0199EQYAAJqA0Qpyh1fBTpxe91qDhPmCwxqNYCvm7Az82ylEe1wKNa4Y3kDZOdZI+rbTv9RIHpDn7FdhWxQrMVCzHZ5yE060z52TDZxa36lS34kGTr5yivTr0O+nbdZ1ywLOwLACelyHA0AK7LGcgNFus3eGCGAJ0AKgpRhQArK7CMlnmrzl95rTZweac7KBU+s70wKp40QDJ185Q4E4L+YbdjvtBYL05kQAS4BmAfwfskuByBlgCdAsMJ6qmBEgXYiQNPIDgn038g=="
)
OLD_PREFIX = "t0120ZAEAAG3"
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
