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

    Hazard / Option A invariant — do not collapse these into one vault slot:
    - ``document_type='incident_report'``: written or scanned incident report in the vault only.
    - On-site verification photographs: stored as ``applications.FieldVerificationPhoto`` on the
      applicant's ``CDRRMOCertification`` (``field_photos``), never as ``Document(incident_report)``.
      Field desk code must not create ``Document`` rows for those images.
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
        ('electricity_app', 'Electricity Connection Application'),
        ('cdrrmo_cert', 'CDRRMO Certification'),
        ('incident_report', 'Incident report'),
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
):
    """
    Create or replace a vault Document for this applicant/type.
    Stores bytes in DocumentBlob and clears FileField so scans do not require disk writes.

    When ``document_type == 'incident_report'``, this must remain the formal incident-report file only —
    not Ronda/field verification photos (those stay ``FieldVerificationPhoto`` records).
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


class SignatoryRouting(models.Model):
    """
    Tracks document routing through signatory chain.
    Hard-moved ownership from applications module.
    """
    STEP_CHOICES = [
        ('received', 'Received - Processing'),
        ('forwarded_oic', 'Forwarded to OIC'),
        ('signed_oic', 'Signed by OIC - Complete'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='routing_steps'
    )
    step = models.CharField(max_length=20, choices=STEP_CHOICES)
    action_at = models.DateTimeField(auto_now_add=True)
    action_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='routing_actions'
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['application', 'action_at']
        verbose_name = "Signatory Routing Step"
        verbose_name_plural = "Signatory Routing Steps"
        db_table = 'applications_signatoryrouting'

    def __str__(self):
        return f"{self.application.application_number} - {self.get_step_display()}"

    @property
    def days_since_action(self):
        from django.utils import timezone
        return (timezone.now() - self.action_at).days

    @property
    def is_delayed(self):
        return self.days_since_action > 3


# Backward-compatible symbol used in some views/admin.
SignatoryRoutingStep = SignatoryRouting

class FieldInspection(models.Model):
    """
    Phase B (3.4): Ronda field inspection submission and staff confirmation.
    """
    STATUS_CHOICES = [
        ('submitted', 'Submitted by Ronda'),
        ('confirmed', 'Confirmed by THA Staff'),
        ('needs_revision', 'Needs Revision'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='field_inspection',
    )
    findings = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='field_inspections_submitted',
        help_text='Ronda user who submitted the field report.',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='field_inspections_confirmed',
        help_text='THA Staff who confirmed the report.',
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    staff_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Field Inspection'
        verbose_name_plural = 'Field Inspections'

    def __str__(self):
        return f'{self.application.application_number} - {self.get_status_display()}'


class FieldInspectionPhoto(models.Model):
    """
    Photos attached to Phase B field inspection submission.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection = models.ForeignKey(
        FieldInspection,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    image = models.ImageField(upload_to='documents/field_inspection/%Y/%m/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Field Inspection Photo'
        verbose_name_plural = 'Field Inspection Photos'

    def __str__(self):
        return f'Photo - {self.inspection.application.application_number}'


class CommitteeInterview(models.Model):
    """
    Phase C (3.5-3.7): committee schedule and recorded result.
    """
    RESULT_CHOICES = [
        ('pending', 'Pending'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('follow_up', 'Needs Follow-up'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='committee_interview',
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    scheduled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='committee_interviews_scheduled',
    )
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='pending')
    result_recorded_at = models.DateTimeField(null=True, blank=True)
    result_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='committee_interviews_recorded',
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-result_recorded_at', '-scheduled_at']
        verbose_name = 'Committee Interview'
        verbose_name_plural = 'Committee Interviews'

    def __str__(self):
        return f'{self.application.application_number} - {self.get_result_display()}'


class EndorsementRoutingStep(models.Model):
    """
    Phase D: seven-step endorsement and signature routing chain.
    """
    STEP_CHOICES = [
        ('barangay_affairs', 'Barangay Affairs Office endorsement'),
        ('community_relations', 'Community Relations Office endorsement'),
        ('cswd_referral', 'CSWD referral, interview, and profiling'),
        ('sp_endorsement', 'SP endorsement'),
        ('gk_orientation', 'GK team orientation and conformity'),
        ('tha_recommending', 'THA recommending approval'),
        ('mayor_final', "Mayor's Office final approval"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='endorsement_routing_steps',
    )
    step = models.CharField(max_length=40, choices=STEP_CHOICES)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='endorsement_steps_recorded',
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['application', 'step']
        verbose_name = 'Endorsement Routing Step'
        verbose_name_plural = 'Endorsement Routing Steps'
        constraints = [
            models.UniqueConstraint(
                fields=['application', 'step'],
                name='unique_application_endorsement_step',
            )
        ]

    def __str__(self):
        return f'{self.application.application_number} - {self.get_step_display()}'


class ElectricityConnection(models.Model):
    """
    Tracks electricity connection status for awarded units.
    Managed by Joie (2nd Member) and Laarni (5th Member).
    Coordination with Negros Power.
    Transferred from applications module for document/service tracking.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending - Not Yet Applied'),
        ('applied', 'Applied to Negros Power'),
        ('inspection_scheduled', 'Inspection Scheduled'),
        ('inspection_completed', 'Inspection Completed'),
        ('connected', 'Electricity Connected'),
        ('issues', 'Issues - Requires Follow-up'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='electricity_connection'
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')

    # Application to Negros Power
    applied_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='electricity_applications'
    )
    negros_power_reference = models.CharField(max_length=50, blank=True)

    # Inspection tracking
    inspection_date = models.DateField(null=True, blank=True)
    inspection_result = models.TextField(blank=True)

    # Connection completion
    connected_at = models.DateTimeField(null=True, blank=True)
    meter_number = models.CharField(max_length=50, blank=True)

    # Issue tracking
    issue_description = models.TextField(blank=True)
    issue_resolved_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Electricity connection (application)"
        verbose_name_plural = "Electricity connections (applications)"

    def __str__(self):
        return f"{self.application.application_number} - {self.get_status_display()}"

    @property
    def days_pending(self):
        """Days since lot was awarded without electricity connection."""
        if self.status == 'connected':
            return 0
        if self.application.status == 'awarded':
            from django.utils import timezone
            award_date = self.application.updated_at
            return (timezone.now() - award_date).days
        return 0

    @property
    def is_overdue(self):
        """Flag if pending > 30 days (per office policy)."""
        return self.days_pending > 30


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


class SMSLog(models.Model):
    """
    Audit trail for Documents (Module 2) SMS notifications.
    Tracks document submission deadlines, verifications, rejections, etc.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_phone = models.CharField(max_length=20)
    message_content = models.TextField()
    trigger_event = models.CharField(
        max_length=50,
        help_text="Event that triggered this SMS (deadline_notice, document_verified, document_rejected, etc.)"
    )

    # Optional links to related records
    applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents_sms_logs'
    )

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    external_id = models.CharField(max_length=100, blank=True, help_text="SMS provider message ID")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = "SMS Log (Documents)"
        verbose_name_plural = "SMS Logs (Documents)"

    def __str__(self):
        return f"SMS to {self.recipient_phone} - {self.trigger_event} ({self.status})"
