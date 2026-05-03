"""
Application form lifecycle helpers (Module 2).

Physically printed/signed forms are ingested via vault document type ``signed_application``.
When a real scan/file payload exists while ``Application.status`` is ``draft``, we advance to
``completed`` and stamp ``applicant_signed_at`` (first transition only for the timestamp).
"""

from django.apps import apps
from django.db import transaction
from django.utils import timezone


def applicant_has_signed_application_payload(applicant) -> bool:
    """True when vault holds ``signed_application`` with bytes or uploaded file (not placeholder)."""
    Document = apps.get_model('documents', 'Document')
    DocumentBlob = apps.get_model('documents', 'DocumentBlob')

    doc = Document.objects.filter(applicant=applicant, document_type='signed_application').first()
    if not doc:
        return False
    if doc.file and getattr(doc.file, 'name', None):
        return True
    return DocumentBlob.objects.filter(document_id=doc.pk).exists()


def apply_signed_application_scan_if_ready(applicant_id) -> dict:
    """
    If applicant has an Application in ``draft`` and a signed-form vault payload exists,
    set status to ``completed`` and ``applicant_signed_at`` when missing.

    Returns ``{'updated': bool}``.
    """
    Applicant = apps.get_model('intake', 'Applicant')
    Application = apps.get_model('applications', 'Application')

    applicant = Applicant.objects.filter(id=applicant_id).first()
    if applicant is None:
        return {'updated': False}

    application = getattr(applicant, 'application', None)
    if application is None or application.status != 'draft':
        return {'updated': False}

    if not applicant_has_signed_application_payload(applicant):
        return {'updated': False}

    updated = False
    with transaction.atomic():
        app = (
            Application.objects.select_for_update()
            .filter(pk=application.pk, status='draft')
            .first()
        )
        if app is None:
            return {'updated': False}
        if not applicant_has_signed_application_payload(applicant):
            return {'updated': False}
        app.status = 'completed'
        if app.applicant_signed_at is None:
            app.applicant_signed_at = timezone.now()
        app.save()
        updated = True

    return {'updated': updated}
