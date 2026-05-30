from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
import uuid


class DocumentQuerySet(models.QuerySet):
    def with_file_payload(self):
        return self.filter(
            models.Q(blob_record__isnull=False)
            | (models.Q(file__isnull=False) & ~models.Q(file=''))
        )


DocumentManager = models.Manager.from_queryset(DocumentQuerySet)


class Document(models.Model):
    """
    Centralized digital archive for all applicant/beneficiary documents.
    Replaces physical folders as primary working reference.
    """
    DOCUMENT_TYPE_CHOICES = [
        # Group A - Applicant Requirements
        ('barangay_residency', 'Barangay Certificate of Residency'),
        ('barangay_indigency', 'Barangay Certificate of Indigency'),
        ('cedula', 'Cedula (Community Tax Certificate)'),
        ('police_clearance', 'Police Clearance'),
        ('no_property', 'Certificate of No Property'),
        ('photo_2x2', '2x2 Picture'),
        ('house_sketch', 'Sketch of House Location'),
        (
            'voter_certification',
            'Voter Certification (COMELEC / Barangay voter record)',
        ),
        (
            'isf_situational_docs',
            'ISF situational documentation (Applicant Situation Options A/B/C)',
        ),

        # Group B - Office-Generated
        ('application_form', 'Application Form'),
        ('notarized_docs', 'Notarized Documents'),
        ('engineering_assessment', 'Engineering Assessment'),
        ('signed_application', 'Physically signed application (scan)'),
        
        # Group C - Post-Award
        ('lot_award', 'Lot Award Document'),
        ('cdrrmo_cert', 'CDRRMO Certification'),
        ('explanation_letter', 'Explanation Letter'),

        # Other
        ('other', 'Other Document'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to applicant profile
    applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    # Optionally link to specific requirement submission
    requirement_submission = models.ForeignKey(
        'documents.RequirementSubmission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    
    # File storage (nullable when payload lives in DocumentBlob — e.g. intake scans)
    file = models.FileField(upload_to='documents/%Y/%m/', null=True, blank=True)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True)
    
    # Upload tracking
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents'
    )
    
    notes = models.TextField(blank=True)

    CAPTURE_UPLOAD = 'upload'
    CAPTURE_SCAN = 'scan'
    CAPTURE_METHOD_CHOICES = [
        ('', 'Not recorded'),
        (CAPTURE_UPLOAD, 'Uploaded'),
        (CAPTURE_SCAN, 'Scanned'),
    ]
    capture_method = models.CharField(
        max_length=10,
        choices=CAPTURE_METHOD_CHOICES,
        blank=True,
        default='',
        help_text='How this file entered the vault (staff Upload vs TWAIN Scan).',
    )

    objects = DocumentManager()

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        indexes = [
            models.Index(fields=['applicant', 'document_type']),
            models.Index(fields=['document_type']),
        ]
    
    def __str__(self):
        return f"{self.applicant.full_name} - {self.get_document_type_display()}"
    
    @property
    def file_size_display(self):
        """Human-readable file size."""
        if self.file_size is None:
            return "—"
        if self.file_size == 0:
            return "—"
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"

    def absolute_download_url(self, request):
        """Staff-facing absolute URL: blob endpoint or MEDIA file URL."""
        from django.urls import reverse

        user = getattr(request, 'user', None)
        position = getattr(user, 'position', None) if user else None
        if position:
            try:
                self.blob_record
            except ObjectDoesNotExist:
                pass
            else:
                path = reverse(
                    'documents:blob_download',
                    kwargs={'position': position, 'doc_id': self.pk},
                )
                return request.build_absolute_uri(path)
        if self.file:
            return request.build_absolute_uri(self.file.url)
        return ''

    def filed_via_display(self):
        return document_filed_via_display(self.capture_method)


def document_filed_via_display(capture_method):
    """UI label for checklist rows (Uploaded vs Scanned)."""
    method = (capture_method or '').strip().lower()
    if method == Document.CAPTURE_UPLOAD:
        return 'Uploaded'
    if method == Document.CAPTURE_SCAN:
        return 'Scanned'
    return ''


class DocumentBlob(models.Model):
    """Binary vault payload linked 1:1 to Document (used by intake scanner uploads)."""

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='blob_record',
    )
    data = models.BinaryField()

    class Meta:
        verbose_name = 'Document blob'
        verbose_name_plural = 'Document blobs'

    def __str__(self):
        return f'Blob for {self.document_id}'


@transaction.atomic
def upsert_document_vault_upload(
    *,
    applicant,
    document_type,
    uploaded_file,
    title,
    uploaded_by,
    capture_method='',
):
    """
    Create or replace a vault Document for this applicant/type.
    Stores bytes in DocumentBlob and clears FileField so scans do not require disk writes.
    """
    raw = uploaded_file.read()
    if not raw:
        raise ValueError('Empty upload')

    existing = Document.objects.filter(
        applicant=applicant,
        document_type=document_type,
    ).first()
    if existing and existing.file:
        existing.file.delete(save=False)

    method = (capture_method or '').strip().lower()
    if method not in (Document.CAPTURE_UPLOAD, Document.CAPTURE_SCAN):
        method = ''

    doc, created = Document.objects.update_or_create(
        applicant=applicant,
        document_type=document_type,
        defaults={
            'title': title,
            'file_name': uploaded_file.name,
            'file_size': len(raw),
            'mime_type': getattr(uploaded_file, 'content_type', '') or '',
            'uploaded_by': uploaded_by,
            'file': None,
            'capture_method': method,
        },
    )

    DocumentBlob.objects.update_or_create(
        document=doc,
        defaults={'data': raw},
    )

    if document_type == 'signed_application':
        from applications.form_pipeline import apply_signed_application_scan_if_ready

        apply_signed_application_scan_if_ready(applicant.id)

    return doc, created


class Requirement(models.Model):
    """
    Reference table for required documents.
    Hard-moved ownership from applications module.
    """
    DOCUMENT_GROUP_CHOICES = [
        ('A', 'Group A - Applicant Requirements'),
        ('B', 'Group B - Office-Generated'),
        ('C', 'Group C - Post-Award'),
    ]

    code = models.CharField(max_length=10, unique=True, primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    group = models.CharField(max_length=1, choices=DOCUMENT_GROUP_CHOICES, default='A')
    order = models.PositiveSmallIntegerField(default=0)
    vault_document_type = models.CharField(
        max_length=30,
        blank=True,
        default='',
        choices=Document.DOCUMENT_TYPE_CHOICES,
        help_text='Links this row to vault uploads: a scan exists when Applicant has a Document with this type.',
    )
    is_required_for_form = models.BooleanField(
        default=True,
        help_text="If True, this must be complete before application form is generated"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['group', 'order']
        verbose_name = "Requirement"
        verbose_name_plural = "Requirements"
        db_table = 'applications_requirement'

    def __str__(self):
        return f"{self.code}: {self.name}"


class RequirementSubmission(models.Model):
    """
    Tracks submitted/verified state per applicant requirement.
    Hard-moved ownership from applications module.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected - Resubmit Required'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.CASCADE,
        related_name='requirement_submissions'
    )
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.PROTECT,
        related_name='submissions'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_requirements'
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['applicant', 'requirement__order']
        verbose_name = "Requirement Submission"
        verbose_name_plural = "Requirement Submissions"
        db_table = 'applications_requirementsubmission'
        constraints = [
            models.UniqueConstraint(
                fields=['applicant', 'requirement'],
                name='unique_applicant_requirement'
            )
        ]

    def __str__(self):
        return f"{self.applicant.full_name} - {self.requirement.name} ({self.get_status_display()})"


class LotAwarding(models.Model):
    """
    Records lot awarding details.
    Managed by Jocel (4th Member).
    Transferred from applications module for document/archival management.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='lot_awarding'
    )

    # Lot details
    lot_number = models.CharField(max_length=50)
    block_number = models.CharField(max_length=50, blank=True)
    site_name = models.CharField(max_length=100, blank=True, help_text="e.g., GK Cabatangan")

    # Awarding ceremony
    awarded_at = models.DateTimeField(auto_now_add=True)
    awarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lots_awarded'
    )

    # Contract signing
    contract_signed = models.BooleanField(default=False)
    contract_signed_at = models.DateTimeField(null=True, blank=True)

    # Key turnover
    keys_turned_over = models.BooleanField(default=False)
    keys_turned_over_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-awarded_at']
        verbose_name = "Lot Awarding"
        verbose_name_plural = "Lot Awardings"

    def __str__(self):
        return f"{self.application.application_number} - Lot {self.lot_number}"
