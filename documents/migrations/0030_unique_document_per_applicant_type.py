"""Deduplicate vault Documents per (applicant, document_type), then enforce uniqueness."""

from django.db import migrations, models


def dedupe_documents(apps, schema_editor):
    Document = apps.get_model('documents', 'Document')
    # Keep newest uploaded_at (then id); delete older duplicates.
    seen = set()
    # Order oldest-first so the last write to `seen` is the newest keeper... 
    # Actually iterate newest-first and delete when already seen.
    qs = Document.objects.order_by('applicant_id', 'document_type', '-uploaded_at', '-id')
    for doc in qs.iterator():
        key = (str(doc.applicant_id), doc.document_type)
        if key in seen:
            # Older duplicate — remove file on disk if any, then delete row
            try:
                if doc.file:
                    doc.file.delete(save=False)
            except Exception:
                pass
            doc.delete()
        else:
            seen.add(key)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0029_update_document_type_voter_cert'),
    ]

    operations = [
        migrations.RunPython(dedupe_documents, noop_reverse),
        migrations.AddConstraint(
            model_name='document',
            constraint=models.UniqueConstraint(
                fields=('applicant', 'document_type'),
                name='unique_document_per_applicant_type',
            ),
        ),
    ]
