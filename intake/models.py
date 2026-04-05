from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


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
    isf_record = models.ForeignKey(
        'ISFRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_logs'
    )
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-sent_at']
        verbose_name = "SMS Log"
        verbose_name_plural = "SMS Logs"
    
    def __str__(self):
        return f"SMS to {self.recipient_phone} - {self.trigger_event} ({self.status})"


class Blacklist(models.Model):
    """
    Permanent record of blacklisted individuals.
    Auto-checked during every Module 1 eligibility check.
    """
    REASON_CHOICES = [
        ('repossession', 'Housing Unit Repossessed'),
        ('fraud', 'Fraudulent Information'),
        ('violation', 'Violation of Housing Rules'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Identity
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Reason
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes = models.TextField(blank=True)
    
    # Link to applicant if exists
    applicant = models.ForeignKey(
        'Applicant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blacklist_entries'
    )
    
    # Staff tracking
    blacklisted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='blacklist_entries_created'
    )
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-blacklisted_at']
        verbose_name = "Blacklist Entry"
        verbose_name_plural = "Blacklist"
    
    def __str__(self):
        return f"Blacklisted: {self.full_name} ({self.get_reason_display()})"


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


class LandownerSubmission(models.Model):
    """
    Landowner submission containing one or more ISF records.
    Channel A: Landowner submits ISF list via public web form.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('processed', 'Processed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(max_length=20, unique=True, editable=False)
    
    # Landowner information
    landowner_name = models.CharField(max_length=255, verbose_name="Landowner Full Name")
    landowner_phone = models.CharField(max_length=20, blank=True, verbose_name="Contact Number")
    landowner_email = models.EmailField(blank=True, verbose_name="Email Address")
    property_address = models.TextField(verbose_name="Property Address")
    barangay = models.CharField(max_length=100, blank=True, verbose_name="Barangay")
    
    # Metadata
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_submissions'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, verbose_name="Staff Notes")
    
    # Track if submitted by staff (walk-in landowner) vs online portal
    submitted_by_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_submissions',
        verbose_name="Submitted by Staff"
    )

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Landowner Submission"
        verbose_name_plural = "Landowner Submissions"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Generate reference: LS-YYYYMMDD-XXXX
            from django.utils import timezone
            import random
            date_str = timezone.now().strftime('%Y%m%d')
            random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(4)])
            self.reference_number = f"LS-{date_str}-{random_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference_number} - {self.landowner_name}"

    @property
    def isf_count(self):
        return self.isf_records.count()


class ISFRecord(models.Model):
    """
    Individual ISF (Informal Settler Family) record within a landowner submission.
    This is the initial record - it gets converted to an Applicant profile after review.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('eligible', 'Eligible - Converted to Applicant'),
        ('disqualified', 'Disqualified'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(max_length=20, unique=True, editable=False)
    submission = models.ForeignKey(
        LandownerSubmission,
        on_delete=models.CASCADE,
        related_name='isf_records'
    )
    
    # ISF Information
    full_name = models.CharField(max_length=255, verbose_name="Full Name")
    household_members = models.PositiveIntegerField(verbose_name="Number of Household Members")
    monthly_income = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Monthly Income (₱)"
    )
    years_residing = models.PositiveIntegerField(verbose_name="Years Residing on Property")
    barangay = models.CharField(max_length=100, blank=True, verbose_name="Barangay")
    
    # Contact (optional, for SMS notifications)
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Contact Number")
    
    # Eligibility tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    disqualification_reason = models.TextField(blank=True)
    eligibility_checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checked_isf_records'
    )
    eligibility_checked_at = models.DateTimeField(null=True, blank=True)
    
    # Link to created Applicant (when converted)
    converted_to_applicant = models.BooleanField(default=False)
    applicant_created_at = models.DateTimeField(null=True, blank=True)
    
    # SMS tracking
    registration_sms_sent = models.BooleanField(default=False)
    eligibility_sms_sent = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "ISF Record"
        verbose_name_plural = "ISF Records"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Generate reference: ISF-YYYYMMDD-XXXX
            from django.utils import timezone
            import random
            date_str = timezone.now().strftime('%Y%m%d')
            random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(4)])
            self.reference_number = f"ISF-{date_str}-{random_suffix}"
        
        # Send registration SMS after first save
        is_new = self._state.adding
        super().save(*args, **kwargs)
        
        if is_new and not self.registration_sms_sent and self.phone_number:
            self.send_registration_sms()
    
    def __str__(self):
        return f"{self.reference_number} - {self.full_name}"

    @property
    def is_income_eligible(self):
        """Check if monthly income is within ₱10,000 threshold."""
        return self.monthly_income <= 10000
    
    def send_registration_sms(self):
        """Send SMS notification that ISF was registered via landowner."""
        from .utils import send_sms
        message = f"Your name has been submitted for housing assistance by your landowner. Reference: {self.reference_number}. Keep this for follow-up."
        if send_sms(self.phone_number, message, 'registration', isf_record=self):
            self.registration_sms_sent = True
            self.save(update_fields=['registration_sms_sent'])
    
    def send_eligibility_sms(self, eligible=True):
        """Send SMS notification of eligibility result."""
        from .utils import send_sms
        if eligible:
            message = f"You passed eligibility. Please visit the Talisay Housing Authority office to submit your 7 requirements. Reference: {self.reference_number}"
        else:
            message = f"Your housing application could not be processed. Reason: {self.disqualification_reason or 'See office for details'}. Reference: {self.reference_number}"
        
        if send_sms(self.phone_number, message, 'eligibility_result', isf_record=self):
            self.eligibility_sms_sent = True
            self.save(update_fields=['eligibility_sms_sent'])


class Applicant(models.Model):
    """
    Master beneficiary profile - the central entity for all modules.
    
    Applicants come from three channels:
    - Channel A: Landowner submission (linked via isf_record)
    - Channel B: Walk-in claiming danger zone
    - Channel C: Regular walk-in
    """
    CHANNEL_CHOICES = [
        ('landowner', 'Channel A - Landowner Submission'),
        ('danger_zone', 'Channel B - Danger Zone Walk-in'),
        ('walk_in', 'Channel C - Regular Walk-in'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Eligibility Check'),
        ('pending_cdrrmo', 'Pending CDRRMO Certification'),
        ('eligible', 'Eligible - In Queue'),
        ('disqualified', 'Disqualified'),
        ('requirements', 'Submitting Requirements'),
        ('application', 'Application In Progress'),
        ('standby', 'Fully Approved - Standby'),
        ('awarded', 'Lot Awarded'),
        ('blacklisted', 'Blacklisted'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(max_length=20, unique=True, editable=False)
    
    # Personal Information
    full_name = models.CharField(max_length=255, verbose_name="Full Name")
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Contact Number")
    
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
        verbose_name="Years at Current Location"
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
    
    # Link to Channel A source (if applicable)
    isf_record = models.OneToOneField(
        ISFRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applicant_profile',
        help_text="Links to original ISF record if from landowner submission"
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
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    eligibility_checked_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = "Applicant"
        verbose_name_plural = "Applicants"
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            from django.utils import timezone
            import random
            date_str = timezone.now().strftime('%Y%m%d')
            random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(4)])
            self.reference_number = f"APP-{date_str}-{random_suffix}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.reference_number} - {self.full_name}"
    
    @property
    def is_income_eligible(self):
        """Check if monthly income is within ₱10,000 threshold."""
        return self.monthly_income <= 10000
    
    @property
    def household_member_count(self):
        """Return total household members - use declared size if no members registered yet."""
        actual_count = self.household_members.count() + 1
        # Return declared size if larger (members not yet added individually)
        return max(actual_count, self.household_size or 1)


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
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        Applicant,
        on_delete=models.CASCADE,
        related_name='household_members'
    )
    
    full_name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    sex = models.CharField(
        max_length=1,
        choices=[('M', 'Male'), ('F', 'Female')],
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['applicant', 'created_at']
        verbose_name = "Household Member"
        verbose_name_plural = "Household Members"
    
    def __str__(self):
        return f"{self.full_name} ({self.get_relationship_display()}) - {self.applicant.full_name}"


class CDRRMOCertification(models.Model):
    """
    Tracks CDRRMO danger zone certification for Channel B applicants.
    CDRRMO physically visits the location and certifies (or not).
    """
    STATUS_CHOICES = [
        ('pending', 'Pending CDRRMO Visit'),
        ('certified', 'Certified - Danger Zone'),
        ('not_certified', 'Not Certified'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.OneToOneField(
        Applicant,
        on_delete=models.CASCADE,
        related_name='cdrrmo_certification'
    )
    
    declared_location = models.TextField(
        verbose_name="Declared Danger Zone Location",
        help_text="Riverbank, riverside, flood-prone area, etc."
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
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
    certification_notes = models.TextField(blank=True)
    
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


class QueueEntry(models.Model):
    """
    Manages priority and walk-in FIFO queues.
    Each applicant has one active queue entry at a time.
    """
    QUEUE_TYPE_CHOICES = [
        ('priority', 'Priority Queue'),
        ('walk_in', 'Walk-in FIFO Queue'),
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
        Applicant,
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
