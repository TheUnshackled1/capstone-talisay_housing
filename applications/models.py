from django.db import models
from django.conf import settings
import uuid


class Requirement(models.Model):
    """
    Reference table for the 7 required documents.
    Pre-populated with the standard THA requirements.
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
    is_required_for_form = models.BooleanField(
        default=True,
        help_text="If True, this must be complete before application form is generated"
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['group', 'order']
        verbose_name = "Requirement"
        verbose_name_plural = "Requirements"
    
    def __str__(self):
        return f"{self.code}: {self.name}"


class RequirementSubmission(models.Model):
    """
    Tracks which requirements each applicant has submitted.
    Part of the 7-requirements gate before application form generation.
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
    
    # Verification tracking
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
        constraints = [
            models.UniqueConstraint(
                fields=['applicant', 'requirement'],
                name='unique_applicant_requirement'
            )
        ]
    
    def __str__(self):
        return f"{self.applicant.full_name} - {self.requirement.name} ({self.get_status_display()})"


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
        required_count = Requirement.objects.filter(
            is_required_for_form=True, is_active=True
        ).count()
        verified_count = self.applicant.requirement_submissions.filter(
            status='verified',
            requirement__is_required_for_form=True
        ).count()
        return verified_count >= required_count


class SignatoryRouting(models.Model):
    """
    Tracks document routing through signatory chain.
    Jay processes → OIC signs → Head signs (final approval).
    Flags delays > 3 days at any step.
    """
    STEP_CHOICES = [
        ('received', 'Received - Processing'),
        ('forwarded_oic', 'Forwarded to OIC'),
        ('signed_oic', 'Signed by OIC'),
        ('forwarded_head', 'Forwarded to Head'),
        ('signed_head', 'Signed by Head - Complete'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='routing_steps'
    )
    
    step = models.CharField(max_length=20, choices=STEP_CHOICES)
    
    # Timestamps
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
    
    def __str__(self):
        return f"{self.application.application_number} - {self.get_step_display()}"
    
    @property
    def days_since_action(self):
        """Calculate days since this routing step."""
        from django.utils import timezone
        return (timezone.now() - self.action_at).days
    
    @property
    def is_delayed(self):
        """Flag if > 3 days without next step (per office policy)."""
        return self.days_since_action > 3


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
    Uses the same underlying intake table via unmanaged mapping.
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
        db_table = 'intake_cdrrmocertification'
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

