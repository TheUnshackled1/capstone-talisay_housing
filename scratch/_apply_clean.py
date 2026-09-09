from pathlib import Path

p = Path("scratch/gen_lot_polygons.py")
text = p.read_text(encoding="utf-8")
start = text.index("def recover_neighbor_gaps(")
end = text.index("\ndef write_debug(")
new = Path("scratch/_clean_detect.py").read_text(encoding="utf-8")
# strip the comment header line
if new.startswith("#"):
    new = new.split("\n", 1)[1]
p.write_text(text[:start] + new + text[end:], encoding="utf-8")
print("patched ok, len", len(p.read_text(encoding="utf-8")))
