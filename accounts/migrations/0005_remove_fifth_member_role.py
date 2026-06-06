from django.db import migrations, models


def delete_fifth_member_users(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(position="fifth_member").delete()
    User.objects.filter(username="laarni.hellera").delete()
    User.objects.filter(email="laarni.hellera@talisayhousing.gov.ph").delete()


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_merge_caretaker_into_ronda"),
    ]

    operations = [
        migrations.RunPython(delete_fifth_member_users, reverse_noop),
        migrations.AlterField(
            model_name="user",
            name="position",
            field=models.CharField(
                blank=True,
                choices=[
                    ("second_member", "Second Member"),
                    ("fourth_member", "Fourth Member"),
                    ("ronda", "Ronda (Field Personnel)"),
                    ("field", "Field Personnel"),
                ],
                help_text="Staff position in THA organizational structure",
                max_length=50,
            ),
        ),
    ]
