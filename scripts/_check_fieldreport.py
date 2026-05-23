import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talisay_housing.settings')
django.setup()
from django.db import connection
c = connection.cursor()
for table in ['cases_fieldreport', 'cases_fieldsettledincidentlog', 'cases_casefieldupdate', 'cases_case']:
    c.execute("""
        SELECT column_name, is_nullable, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, [table])
    print('===', table, '===')
    for row in c.fetchall():
        print(row)
