import django, os, sys
sys.path.insert(0, '.')
os.environ['DJANGO_SETTINGS_MODULE'] = 'talisay_housing.settings'
django.setup()
from units.models import HousingUnit, RelocationSite

for s in RelocationSite.objects.all():
    blocks = list(HousingUnit.objects.filter(site=s).values_list('block_number', flat=True).distinct().order_by('block_number'))
    total = HousingUnit.objects.filter(site=s).count()
    phase = getattr(s, 'map_phase', 'N/A')
    print("Site:", s.name, "| map_phase:", phase, "| id:", str(s.id)[:8])
    print("  Blocks:", blocks)
    print("  Total units:", total)
    print()
