import json
import os

path = os.path.join(os.path.dirname(__file__), '../static/units/lot_plan_polygons.json')
with open(path, 'r') as f:
    data = json.load(f)

strip = []
others = []
for l in data['lots']:
    if 0.15 < l['cx'] < 0.25:
        strip.append(l)
    else:
        others.append(l)

strip = sorted(strip, key=lambda x: x['cy'])

# Reassign block and lot sequentially from top to bottom
for i, l in enumerate(strip):
    l['block'] = 1
    l['lot'] = i + 1

data['lots'] = others + strip

with open(path, 'w') as f:
    json.dump(data, f)

print(f"Patched {len(strip)} polygons to be Block 1 sequentially.")
