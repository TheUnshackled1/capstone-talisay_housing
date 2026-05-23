from django.db import migrations


def fix_case_foreign_keys(apps, schema_editor):
    """Align PostgreSQL FK delete rules with Django on_delete."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    alters = [
        (
            'cases_fieldreport',
            'cases_fieldreport_case_id_e77bdf75_fk_cases_case_id',
            'cases_case',
            'case_id',
            'SET NULL',
        ),
        (
            'cases_caseaction',
            'cases_caseaction_case_id_bfce89f9_fk_cases_case_id',
            'cases_case',
            'case_id',
            'CASCADE',
        ),
        (
            'cases_caseevidence',
            'cases_caseevidence_case_id_c09369a3_fk_cases_case_id',
            'cases_case',
            'case_id',
            'CASCADE',
        ),
        (
            'cases_casefieldupdate',
            'cases_casefieldupdate_case_id_8df72879_fk_cases_case_id',
            'cases_case',
            'case_id',
            'CASCADE',
        ),
    ]

    with schema_editor.connection.cursor() as cursor:
        for table, constraint, ref_table, column, on_delete in alters:
            cursor.execute(
                f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}'
            )
            cursor.execute(
                f'''
                ALTER TABLE {table}
                ADD CONSTRAINT {constraint}
                FOREIGN KEY ({column}) REFERENCES {ref_table}(id)
                ON DELETE {on_delete} DEFERRABLE INITIALLY DEFERRED
                '''
            )


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0013_module5_field_reports'),
    ]

    operations = [
        migrations.RunPython(fix_case_foreign_keys, migrations.RunPython.noop),
    ]
