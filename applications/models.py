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
        ('received', 'Received by Third Member'),
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


class FacilitatedService(models.Model):
    """
    Tracks notarial services and engineering assessment.
    Coordinated by office at no cost to applicant.
    """
    SERVICE_TYPE_CHOICES = [
        ('notarial', 'Notarial Services'),
        ('engineering', 'Engineering Assessment'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='facilitated_services'
    )
    
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    initiated_at = models.DateTimeField(auto_now_add=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_services'
    )
    
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_services'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['application', 'service_type']
        verbose_name = "Facilitated Service"
        verbose_name_plural = "Facilitated Services"
        constraints = [
            models.UniqueConstraint(
                fields=['application', 'service_type'],
                name='unique_application_service'
            )
        ]
    
    def __str__(self):
        return f"{self.application.application_number} - {self.get_service_type_display()}"


class ElectricityConnection(models.Model):
    """
    Tracks electricity connection status for awarded units.
    Managed by Joie (2nd Member) and Laarni (5th Member).
    Coordination with Negros Power.
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
        Application,
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
        verbose_name = "Electricity Connection"
        verbose_name_plural = "Electricity Connections"
    
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
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        Application,
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
