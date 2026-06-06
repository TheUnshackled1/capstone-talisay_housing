import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "talisay_housing.settings")
django.setup()

from django.db import connection

with connection.cursor() as c:
    c.execute(
        "UPDATE django_migrations SET name=%s WHERE app=%s AND name=%s",
        ["0006_remove_retired_staff_position", "accounts", "0006_remove_oic_position"],
    )
    c.execute(
        "UPDATE django_migrations SET name=%s WHERE app=%s AND name=%s",
        ["0007_delete_legacy_staff_users", "accounts", "0007_delete_oic_user_accounts"],
    )
    c.execute(
        "SELECT name FROM django_migrations WHERE app=%s ORDER BY id DESC LIMIT 5",
        ["accounts"],
    )
    print("Latest accounts migrations:", [row[0] for row in c.fetchall()])
