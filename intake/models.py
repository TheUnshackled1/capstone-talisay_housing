from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
import uuid


# Phone validators for Philippine numbers
validate_philippine_phone = RegexValidator(
    regex=r'^09\d{9}$',
    message='Phone number must be in format 09XXXXXXXXXX (11 digits)',
    code='invalid_phone'
)


class SMSLog(models.Model):
    """
    Audit trail for all SMS notifications sent by the system.
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
        help_text="Event that triggered this SMS (registration, eligibility_passed, etc.)"
    )
    
    # Optional links to related records
    applicant = models.ForeignKey(
        'Applicant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_logs'
    )

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    external_id = models.CharField(max_length=100, blank=True, help_text="Twilio message SID")
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-sent_at']
        verbose_name = "SMS Log"
        verbose_name_plural = "SMS Logs"
    
    def __str__(self):
        return f"SMS to {self.recipient_phone} - {self.trigger_event} ({self.status})"


class Barangay(models.Model):
    """
    Reference table for the 27 barangays of Talisay City.
    Used for applicant origin tracking and ISF demand analytics.
    """
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Barangay"
        verbose_name_plural = "Barangays"
    
    def __str__(self):
        return self.name





class Applicant(models.Model):
    """
    Master beneficiary profile - the central entity for all modules.

    Applicants: Channel B (Danger Zone Walk-in)
    """
    CHANNEL_CHOICES = [
        ('danger_zone', 'Channel B - Danger Zone Walk-in'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending eligibility check'),
        ('pending_cdrrmo', 'Pending CDRRMO verification (hazard claim)'),
        ('eligible', 'Eligible - In Queue'),
        ('disqualified', 'Disqualified'),
        ('requirements', 'Submitting Requirements'),
        ('application', 'Application In Progress'),
        ('standby', 'Fully Approved - Standby'),
        ('awarded', 'Lot Awarded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(max_length=20, unique=True, editable=False)

    # Personal Information - Name Fields (A. APPLICATION IDENTITY)
    last_name = models.CharField(max_length=100, verbose_name="Last Name (Surname)", default="")
    first_name = models.CharField(max_length=100, verbose_name="First Name (Given Name)", default="")
    middle_name = models.CharField(max_length=100, blank=True, default="", verbose_name="Middle Name")
    extension_name = models.CharField(max_length=50, blank=True, default="", verbose_name="Extension Name", help_text="Jr., Sr., II, III, IV, etc.")

    # Keep full_name for backward compatibility
    full_name = models.CharField(max_length=255, verbose_name="Full Name", editable=False)

    sex = models.CharField(
        max_length=1,
        choices=[('M', 'Male'), ('F', 'Female')],
        blank=True,
        verbose_name="Sex"
    )
    age = models.PositiveIntegerField(null=True, blank=True, verbose_name="Age")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Date of Birth")
    place_of_birth = models.CharField(max_length=255, blank=True, verbose_name="Place of Birth")
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Applicant Contact Number",
        validators=[validate_philippine_phone],
        help_text="Format: 09XXXXXXXXXX (11 digits)"
    )

    # Spouse Information
    spouse_name = models.CharField(max_length=255, blank=True, verbose_name="Name of Spouse")
    spouse_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Spouse Contact Number",
        validators=[validate_philippine_phone],
        help_text="Format: 09XXXXXXXXXX (11 digits)"
    )

    # Address/Origin
    barangay = models.ForeignKey(
        Barangay,
        on_delete=models.PROTECT,
        related_name='applicants',
        verbose_name="Barangay of Origin"
    )
    current_address = models.TextField(verbose_name="Current Address/Location")
    years_residing = models.PositiveIntegerField(
        default=0,
        verbose_name="Years Residing in Talisay"
    )
    
    # Household & Income
    monthly_income = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Monthly Household Income (₱)",
        validators=[MinValueValidator(0)]
    )
    household_size = models.PositiveIntegerField(
        default=1,
        verbose_name="Declared Household Size",
        help_text="Number of household members as declared during registration"
    )
    occupation = models.CharField(max_length=255, blank=True, verbose_name="Occupation")
    employment_status = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Status of Employment",
        choices=[
            ('employed', 'Employed'),
            ('self_employed', 'Self-Employed'),
            ('unemployed', 'Unemployed'),
            ('retired', 'Retired'),
            ('other', 'Other'),
        ]
    )
    
    # Channel and Status
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Channel B: Danger Zone specific fields
    danger_zone_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Type of Danger Zone",
        help_text="flood_prone, landslide, storm_surge, river_bank, cliff_edge, coastal, other"
    )
    danger_zone_location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Specific Danger Zone Location"
    )

    # Eligibility tracking
    has_property_in_talisay = models.BooleanField(
        default=False,
        verbose_name="Owns Property in Talisay City"
    )
    disqualification_reason = models.TextField(blank=True)
    
    # Processing metadata
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='registered_applicants'
    )
    eligibility_checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eligibility_checked_applicants'
    )
    module2_handoff_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when staff forwarded this intake record to Module 2."
    )
    module2_handoff_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='module2_handed_off_applicants'
    )
    
    # Document Checklist (7 required documents)
    doc_brgy_residency = models.BooleanField(default=False, verbose_name="Brgy. Certificate of Residency")
    doc_brgy_indigency = models.BooleanField(default=False, verbose_name="Brgy. Certificate of Indigency")
    doc_cedula = models.BooleanField(default=False, verbose_name="Cedula")
    doc_police_clearance = models.BooleanField(default=False, verbose_name="Police Clearance")
    doc_no_property = models.BooleanField(default=False, verbose_name="Certificate of No Property")
    doc_2x2_picture = models.BooleanField(default=False, verbose_name="2x2 Picture")
    doc_sketch_location = models.BooleanField(default=False, verbose_name="Sketch of House Location")

    # Document submission deadline tracking
    document_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Document Submission Deadline",
        help_text="Deadline by which all 7 documents must be submitted"
    )
    documents_submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Documents Completed Date",
        help_text="When all 7 documents were completed"
    )

    # SMS tracking
    registration_sms_sent = models.BooleanField(default=False, verbose_name="Registration SMS Sent")
    eligibility_sms_sent = models.BooleanField(default=False, verbose_name="Eligibility SMS Sent")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    eligibility_checked_at = models.DateTimeField(null=True, blank=True)

    # Module 2.8 - Evaluation approval/review marker (separate from Module 3 routing)
    EVALUATION_APPROVAL_CHOICES = [
        ('', 'Not Recorded'),
        ('approved', 'Approved'),
        ('for_review', 'For Review'),
    ]
    evaluation_approval_status = models.CharField(
        max_length=20,
        choices=EVALUATION_APPROVAL_CHOICES,
        blank=True,
        default='',
        help_text='Module 2 step 2.8 approval/review marker only.',
    )
    evaluation_approval_notes = models.TextField(blank=True, default='')
    evaluation_approval_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluation_approved_applicants',
    )
    evaluation_approval_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = "Applicant"
        verbose_name_plural = "Applicants"
    
    def save(self, *args, **kwargs):
        # Generate reference number if new
        if not self.reference_number:
            from django.utils import timezone
            import random
            date_str = timezone.now().strftime('%Y%m%d')
            random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(4)])
            self.reference_number = f"APP-{date_str}-{random_suffix}"

        # Auto-generate full_name from components (first, middle, last + extension)
        name_parts = [self.first_name, self.middle_name, self.last_name]
        base_name = ' '.join([part for part in name_parts if part]).strip()
        if self.extension_name:
            self.full_name = f"{base_name}, {self.extension_name}".strip()
        else:
            self.full_name = base_name

        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.reference_number} - {self.full_name}"
    
    @property
    def is_income_eligible(self):
        """Monthly household income within Module 1 ceiling (see `MODULE1_MONTHLY_INCOME_CEILING_PESO` in intake/views.py)."""
        return self.monthly_income <= 10000  # keep in sync with intake.views.MODULE1_MONTHLY_INCOME_CEILING_PESO
    
    @property
    def household_member_count(self):
        """Return total household members - use declared size if no members registered yet."""
        actual_count = self.household_members.count() + 1
        # Return declared size if larger (members not yet added individually)
        return max(actual_count, self.household_size or 1)
    
    def send_registration_sms(self):
        """Legacy helper: sends the Module 1 handoff SMS message."""
        from .utils import send_sms
        from . import sms_workflow
        if not self.phone_number:
            return False
        message = sms_workflow.message_proceed_to_evaluation(self)
        if send_sms(self.phone_number, message, sms_workflow.PROCEED_TO_EVALUATION, applicant=self):
            self.registration_sms_sent = True
            self.save(update_fields=['registration_sms_sent'])
            return True
        return False
    
    def send_eligibility_sms(self, eligible=True):
        """Send SMS notification of eligibility result."""
        from .utils import send_sms
        if not self.phone_number:
            return False
        if eligible:
            message = f"Congratulations! You passed eligibility. Please visit the Talisay Housing Authority office to submit your 7 requirements. Reference: {self.reference_number}"
        else:
            message = f"Your housing application could not be processed. Reason: {self.disqualification_reason or 'See office for details'}. Reference: {self.reference_number}"
        
        if send_sms(self.phone_number, message, 'eligibility_result', applicant=self):
            self.eligibility_sms_sent = True
            self.save(update_fields=['eligibility_sms_sent'])
            return True
        return False


class HouseholdMember(models.Model):
    """
    Family members of an applicant.
    Only these registered members are permitted to reside in the awarded unit.
    """
    RELATIONSHIP_CHOICES = [
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('sibling', 'Sibling'),
        ('grandchild', 'Grandchild'),
        ('other', 'Other Relative'),
    ]

    CIVIL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('widowed', 'Widowed'),
        ('divorced', 'Divorced'),
        ('separated', 'Separated'),
        ('common_law', 'Common-law'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        Applicant,
        on_delete=models.CASCADE,
        related_name='household_members'
    )

    # B. HOUSEHOLD MEMBERS - Personal Information
    full_name = models.CharField(max_length=100, verbose_name="Full Name")
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, verbose_name="Relationship to Applicant")
    age = models.PositiveIntegerField(default=0, verbose_name="Age", validators=[MaxValueValidator(120)])
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Date of Birth")
    sex = models.CharField(
        max_length=1,
        choices=[('M', 'Male'), ('F', 'Female')],
        blank=True,
        verbose_name="Sex"
    )
    civil_status = models.CharField(
        max_length=20,
        choices=CIVIL_STATUS_CHOICES,
        blank=True,
        default='single',
        verbose_name="Civil Status"
    )
    contact_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
        validators=[validate_philippine_phone],
        verbose_name="Contact Number",
        help_text="Optional household member mobile number (09XXXXXXXXXX).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['applicant', 'created_at']
        verbose_name = "Household Member"
        verbose_name_plural = "Household Members"

    def __str__(self):
        return f"{self.full_name} ({self.get_relationship_display()}) - {self.applicant.full_name}"


class Archive(models.Model):
    """
    Formal record of applicants archived when proceeded to Module 2.
    Captures snapshot of applicant state at handoff time for audit trail and reporting.
    """
    CHANNEL_CHOICES = [
        ('channel_a', 'Channel A — Walk-in'),
        ('channel_b_no_hazard', 'Channel B — No hazard'),
        ('channel_b_hazard', 'Channel B — Hazard'),
        ('channel_c', 'Channel C — Landowner'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Archive event reference
    applicant = models.ForeignKey(
        Applicant,
        on_delete=models.CASCADE,
        related_name='archives'
    )

    # Archive timing and staff
    archived_at = models.DateTimeField(auto_now_add=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='archived_applicants'
    )

    # Snapshot of applicant state at archive time
    reference_number_snapshot = models.CharField(max_length=50, db_index=True)
    full_name_snapshot = models.CharField(max_length=255)
    # Individual name components (for display in reports/modals)
    last_name_snapshot = models.CharField(max_length=100, blank=True)
    first_name_snapshot = models.CharField(max_length=100, blank=True)
    middle_name_snapshot = models.CharField(max_length=100, blank=True)
    extension_name_snapshot = models.CharField(max_length=50, blank=True)
    date_of_birth_snapshot = models.DateField(null=True, blank=True)

    # Channel and queue information
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, db_index=True)
    queue_type = models.CharField(
        max_length=20,
        choices=[('priority', 'Priority Queue'), ('walk_in', 'Walk-in Queue')],
        blank=True,
        help_text="Queue type assigned upon Module 2 entry"
    )

    # Location snapshot
    barangay_name_snapshot = models.CharField(max_length=100, blank=True)

    # SMS notification tracking
    sms_sent = models.BooleanField(default=False)
    sms_sent_at = models.DateTimeField(null=True, blank=True)

    # CDRRMO information if applicable
    cdrrmo_certified = models.BooleanField(
        default=False,
        help_text="Whether CDRRMO certificate was present at archive time"
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-archived_at']
        verbose_name = "Intake Archive"
        verbose_name_plural = "Intake Archives"
        indexes = [
            models.Index(fields=['archived_at']),
            models.Index(fields=['reference_number_snapshot']),
            models.Index(fields=['channel']),
        ]

    def __str__(self):
        return f"Archive: {self.reference_number_snapshot} - {self.full_name_snapshot}"

