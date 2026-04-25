"""
Seed script for Module 2 requirements.
Run with: python seed_requirements.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talisay_housing.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from documents.models import Requirement

def seed_requirements():
    """Create the 7 Group A requirements if they don't exist."""
    
    # Check if requirements already exist
    existing = Requirement.objects.count()
    print(f'Existing requirements: {existing}')
    
    if existing == 0:
        requirements = [
            ('R01', 'Brgy. Certificate of Residency', 'A', 1, True),
            ('R02', 'Brgy. Certificate of Indigency', 'A', 2, True),
            ('R03', 'Cedula', 'A', 3, True),
            ('R04', 'Police Clearance', 'A', 4, True),
            ('R05', 'Certificate of No Property', 'A', 5, True),
            ('R06', '2x2 Picture', 'A', 6, True),
            ('R07', 'Sketch of House Location', 'A', 7, True),
        ]
        
        for code, name, group, order, required in requirements:
            Requirement.objects.create(
                code=code,
                name=name,
                group=group,
                order=order,
                is_required_for_form=required
            )
            print(f'✅ Created: {code} - {name}')
        
        print(f'\n✅ Total requirements created: {Requirement.objects.count()}')
    else:
        print('Requirements already exist:')
        for r in Requirement.objects.all().order_by('code'):
            print(f'  {r.code}: {r.name}')

if __name__ == '__main__':
    seed_requirements()
