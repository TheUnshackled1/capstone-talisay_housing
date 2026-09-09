from pathlib import Path

p = Path("scratch/gen_lot_polygons.py")
text = p.read_text(encoding="utf-8")
start = text.index("def recover_neighbor_gaps(")
end = text.index("\ndef detect_lots(")
new = Path("scratch/_recover_patch.py").read_text(encoding="utf-8")
p.write_text(text[:start] + new + text[end:], encoding="utf-8")
print("ok")
