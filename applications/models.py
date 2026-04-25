from django.db import models
from django.conf import settings
import uuid


class Application(models.Model):
    """
    Housing application form data.
    Generated only after all 7 Group A requirements are verified.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft - Form Generated'),
        ('completed', 'Completed - Signed by Applicant'),
        ('routing', 'Under Signatory Routing'),
        ('oic_signed', 'Signed by OIC'),
        ('head_signed', 'Signed by Head - Fully Approved'),
        ('standby', 'Fully Approved - On Standby'),
        ('awarded', 'Lot Awarded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_number = models.CharField(max_length=20, unique=True, editable=False)
    applicant = models.OneToOneField(
        'intake.Applicant',
        on_delete=models.CASCADE,
        related_name='application'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Form generation
    form_generated_at = models.DateTimeField(auto_now_add=True)
    form_generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_applications'
    )
    
    # Applicant signature
    applicant_signed_at = models.DateTimeField(null=True, blank=True)
    
    # Facilitated services flags
    notarial_completed = models.BooleanField(default=False)
    notarial_completed_at = models.DateTimeField(null=True, blank=True)
    engineering_completed = models.BooleanField(default=False)
    engineering_completed_at = models.DateTimeField(null=True, blank=True)
    
    # Final approval tracking
    fully_approved_at = models.DateTimeField(null=True, blank=True)
    
    # Standby queue position (after full approval)
    standby_position = models.PositiveIntegerField(null=True, blank=True)
    standby_entered_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Application"
        verbose_name_plural = "Applications"
    
    def save(self, *args, **kwargs):
        if not self.application_number:
            from django.utils import timezone
            import random
            date_str = timezone.now().strftime('%Y%m%d')
            random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(4)])
            self.application_number = f"HA-{date_str}-{random_suffix}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.application_number} - {self.applicant.full_name}"
    
    @property
    def all_requirements_verified(self):
        """Check if all Group A requirements are verified."""
        from documents.models import Requirement
        required_count = Requirement.objects.filter(
            is_required_for_form=True, is_active=True
        ).count()
        verified_count = self.applicant.requirement_submissions.filter(
            status='verified',
            requirement__is_required_for_form=True
        ).count()
        return verified_count >= required_count


class SMSLog(models.Model):
    """
    Audit trail for Module 2 (Applications) SMS notifications.
    Tracks eligibility decisions, queue assignments, document deadlines, etc.
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
        help_text="Event that triggered this SMS (eligibility_eligible, queue_assigned, deadline_notice, etc.)"
    )

    # Optional links to related records
    applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applications_sms_logs'
    )

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    external_id = models.CharField(max_length=100, blank=True, help_text="SMS provider message ID")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = "SMS Log (Module 2)"
        verbose_name_plural = "SMS Logs (Module 2)"

    def __str__(self):
        return f"SMS to {self.recipient_phone} - {self.trigger_event} ({self.status})"



# =============================================================================
# MODULE 2 OWNERSHIP WRAPPERS (NO DB MOVE RISK)
# =============================================================================

class CDRRMOCertificationProxy(models.Model):
    """
    Applications-app view of CDRRMO certification records.
    Uses the same underlying applications table via unmanaged mapping.
    """
    id = models.UUIDField(primary_key=True, editable=False)
    applicant = models.OneToOneField(
        'intake.Applicant',
        on_delete=models.DO_NOTHING,
        db_column='applicant_id',
        related_name='+',
    )
    status = models.CharField(max_length=20)
    disposition_source = models.CharField(max_length=20)
    declared_location = models.TextField()
    requested_at = models.DateTimeField()
    certified_at = models.DateTimeField(null=True, blank=True)
    certification_notes = models.TextField(blank=True)
    office_intake_notes = models.TextField(blank=True)

    class Meta:
        managed = False
        db_table = 'applications_cdrrmocertification'
        verbose_name = 'CDRRMO Certification (Module 2 view)'
        verbose_name_plural = 'CDRRMO Certifications (Module 2 view)'


class QueueEntry(models.Model):
    """
    Manages Module 2 queue assignment for eligible applicants.
    Each applicant has one active queue entry at a time.
    """
    QUEUE_TYPE_CHOICES = [
        ('priority', 'Priority Queue - Danger Zone'),
        ('walk_in', 'Walk-in Queue - FIFO'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active - Waiting'),
        ('notified', 'Notified for Requirements'),
        ('processing', 'Processing Application'),
        ('completed', 'Completed - Moved to Application'),
        ('removed', 'Removed from Queue'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.CASCADE,
        related_name='queue_entries'
    )

    queue_type = models.CharField(max_length=20, choices=QUEUE_TYPE_CHOICES)
    position = models.PositiveIntegerField(
        verbose_name="Queue Position",
        help_text="Position number in the queue (FIFO order)"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Timestamps
    entered_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Staff tracking
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='queue_entries_added'
    )

    class Meta:
        ordering = ['queue_type', 'position']
        verbose_name = "Queue Entry"
        verbose_name_plural = "Queue Entries"
        constraints = [
            models.UniqueConstraint(
                fields=['queue_type', 'position'],
                condition=models.Q(status='active'),
                name='unique_active_queue_position'
            )
        ]

    def __str__(self):
        return f"{self.get_queue_type_display()} #{self.position} - {self.applicant.full_name}"


class CDRRMOCertification(models.Model):
    """
    Tracks CDRRMO danger zone certification for Channel B applicants.
    CDRRMO physically visits the location and certifies (or not).
    Moved to applications app for Module 2+ operations.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending CDRRMO verification (claim on file)'),
        ('certified', 'Certified - Danger Zone'),
        ('not_certified', 'Not Certified'),
    ]

    DISPOSITION_SOURCE_CHOICES = [
        ('pending', 'No disposition recorded'),
        ('office_intake', 'Official CDRRMO paperwork filed at THA intake'),
        ('field_unit', 'Field unit / Ronda on-site verification'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.OneToOneField(
        'intake.Applicant',
        on_delete=models.CASCADE,
        related_name='cdrrmo_certification'
    )

    declared_location = models.TextField(
        verbose_name="Declared Danger Zone Location",
        help_text="Riverbank, riverside, flood-prone area, etc."
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    disposition_source = models.CharField(
        max_length=20,
        choices=DISPOSITION_SOURCE_CHOICES,
        default='pending',
        help_text='Intake-filed CDRRMO documents vs. field/Ronda on-site verification (different workflows).',
    )

    # Coordination tracking
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cdrrmo_requests'
    )

    # Result tracking
    certified_at = models.DateTimeField(null=True, blank=True)
    result_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cdrrmo_results_recorded'
    )
    certification_notes = models.TextField(
        blank=True,
        help_text='Remarks from field / Ronda on-site verification (not intake receiving log).',
    )
    office_intake_notes = models.TextField(
        blank=True,
        help_text='Receiving log when official CDRRMO certification is filed at THA intake.',
    )

    class Meta:
        verbose_name = "CDRRMO Certification"
        verbose_name_plural = "CDRRMO Certifications"

    def __str__(self):
        return f"CDRRMO Cert - {self.applicant.full_name} ({self.get_status_display()})"

    @property
    def days_pending(self):
        """Calculate days since certification was requested."""
        if self.status == 'pending':
            from django.utils import timezone
            return (timezone.now() - self.requested_at).days
        return 0

    @property
    def is_overdue(self):
        """Flag if pending > 14 days (per office policy)."""
        return self.days_pending > 14


class FieldVerificationPhoto(models.Model):
    """
    On-site photos taken by field/ronda staff as evidence for danger-zone verification.
    Stored when submitting field verification (Module 1, Channel B).
    Moved to applications app for Module 2+ operations.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    certification = models.ForeignKey(
        CDRRMOCertification,
        on_delete=models.CASCADE,
        related_name='field_photos',
    )
    image = models.ImageField(upload_to='field_verification/%Y/%m/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='field_verification_photos',
    )

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Field verification photo'
        verbose_name_plural = 'Field verification photos'

    def __str__(self):
        return f'Photo for {self.certification.applicant.reference_number}'

