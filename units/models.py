from django.db import models
from django.conf import settings
import uuid


class RelocationSite(models.Model):
    """
    THA-managed relocation sites (e.g., GK Cabatangan).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField()
    barangay = models.ForeignKey(
        'intake.Barangay',
        on_delete=models.PROTECT,
        related_name='relocation_sites'
    )
    
    # Capacity
    total_blocks = models.PositiveIntegerField(default=0)
    total_lots = models.PositiveIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Caretaker assignment
    caretaker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_sites'
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Relocation Site"
        verbose_name_plural = "Relocation Sites"
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @property
    def occupied_units_count(self):
        return self.units.filter(status='Occupied').count()

    @property
    def vacant_units_count(self):
        return self.units.filter(status='Vacant — available').count()


class HousingUnit(models.Model):
    """
    Individual housing unit (block/lot) at a relocation site.
    """
    STATUS_CHOICES = [
        ('Vacant — available', 'Vacant — available'),
        ('Occupied', 'Occupied'),
        ('Under notice (30-day)', 'Under notice (30-day)'),
        ('Final notice (10-day)', 'Final notice (10-day)'),
        ('Repossessed', 'Repossessed'),
        ('maintenance', 'Under Maintenance'),
    ]

    NOTICE_TYPE_CHOICES = [
        ('30-day', '30-day notice'),
        ('10-day', '10-day final notice'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    site = models.ForeignKey(
        RelocationSite,
        on_delete=models.CASCADE,
        related_name='units'
    )

    block_number = models.CharField(max_length=10)
    lot_number = models.CharField(max_length=10)

    # Unit details
    area_sqm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Area (sq.m.)"
    )

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Vacant — available')

    # Occupancy tracking (for monitoring dashboard)
    occupant_name = models.CharField(max_length=200, blank=True, null=True)
    occupant_id = models.CharField(max_length=100, blank=True, null=True)

    # Notice tracking
    notice_type = models.CharField(
        max_length=20,
        choices=NOTICE_TYPE_CHOICES,
        blank=True,
        null=True
    )
    notice_date_issued = models.DateTimeField(null=True, blank=True)
    notice_deadline = models.DateField(null=True, blank=True)

    # Escalation flag
    is_escalated = models.BooleanField(default=False)
    escalation_reason = models.TextField(blank=True)

    # Location notes (helpful for field team)
    location_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['site', 'block_number', 'lot_number']
        verbose_name = "Housing Unit"
        verbose_name_plural = "Housing Units"
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'block_number', 'lot_number'],
                name='unique_unit_per_site'
            )
        ]
    
    def __str__(self):
        return f"{self.site.code} Block {self.block_number} Lot {self.lot_number}"

    @property
    def current_occupant(self):
        """Return current active lot award if occupied."""
        active_award = self.lot_awards.filter(status='active').first()
        return active_award.application.applicant if active_award else None

    @property
    def construction_progress_snapshot(self):
        """
        Fast path for templates: views may attach ``_construction_progress``.
        Falls back to a query if missing.
        """
        attached = getattr(self, '_construction_progress', None)
        if attached is not None:
            return attached
        try:
            active_award = self.lot_awards.select_related('construction_progress').filter(status='active').first()
            return getattr(active_award, 'construction_progress', None) if active_award else None
        except Exception:
            return None


class WeeklyReport(models.Model):
    """
    Weekly occupancy report for a housing unit.
    Submitted by caretaker, contains comfort status and any concerns.
    """
    REPORT_STATUS_CHOICES = [
        ('Occupied', 'Occupied'),
        ('Vacant', 'Vacant'),
        ('Concern', 'Concern - Needs Follow-up'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    unit = models.OneToOneField(
        HousingUnit,
        on_delete=models.CASCADE,
        related_name='weekly_report'
    )

    reported_status = models.CharField(max_length=50, choices=REPORT_STATUS_CHOICES)
    concern_notes = models.TextField(blank=True)

    last_updated = models.DateTimeField(auto_now=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='weekly_reports_submitted'
    )

    class Meta:
        ordering = ['-last_updated']
        verbose_name = "Weekly Report"
        verbose_name_plural = "Weekly Reports"

    def __str__(self):
        return f"Weekly Report - {self.unit}"


class LotAward(models.Model):
    """
    Lot assignment record linking application to housing unit.
    Tracks the full lifecycle from award to potential repossession.
    """
    STATUS_CHOICES = [
        ('active', 'Active - Occupying'),
        ('transferred', 'Properly Transferred'),
        ('repossessed', 'Repossessed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    application = models.ForeignKey(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='lot_awards'
    )
    unit = models.ForeignKey(
        HousingUnit,
        on_delete=models.CASCADE,
        related_name='lot_awards'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Award details
    awarded_at = models.DateTimeField()
    awarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lot_awards_granted'
    )
    
    # Draw lots info (if applicable)
    via_draw_lots = models.BooleanField(
        default=True,
        help_text="False if re-awarded repossessed unit"
    )
    draw_lots_date = models.DateField(null=True, blank=True)
    
    # End tracking
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.TextField(blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-awarded_at']
        verbose_name = "Lot Award"
        verbose_name_plural = "Lot Awards"
    
    def __str__(self):
        return f"{self.unit} → {self.application.applicant.full_name}"


class ConstructionProgress(models.Model):
    """
    Tracks beneficiary house construction progress after a lot is awarded.
    Snapshot model (current stage/percent). Timeline lives in ConstructionProgressUpdate.
    """
    STAGE_CHOICES = [
        ('not_started', 'Not started'),
        ('site_clearing', 'Site clearing'),
        ('foundation', 'Foundation'),
        ('wall_framing', 'Wall framing'),
        ('roofing', 'Roofing'),
        ('finishing', 'Finishing'),
        ('completed', 'Completed / Occupied'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    lot_award = models.OneToOneField(
        LotAward,
        on_delete=models.CASCADE,
        related_name='construction_progress',
    )

    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default='not_started')
    percent_complete = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    expected_completion_date = models.DateField(null=True, blank=True)
    last_inspected_at = models.DateTimeField(null=True, blank=True)

    is_delayed = models.BooleanField(default=False)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='construction_progress_updates',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Construction progress"
        verbose_name_plural = "Construction progress"

    def __str__(self):
        return f"Construction: {self.lot_award.unit} ({self.get_stage_display()} {self.percent_complete}%)"


class ConstructionProgressUpdate(models.Model):
    """
    Append-only timeline updates for construction progress.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    progress = models.ForeignKey(
        ConstructionProgress,
        on_delete=models.CASCADE,
        related_name='updates',
    )

    stage = models.CharField(max_length=30, choices=ConstructionProgress.STAGE_CHOICES)
    percent_complete = models.PositiveIntegerField()
    visit_date = models.DateField()
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='construction_progress_timeline_entries',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-visit_date', '-created_at']
        verbose_name = "Construction progress update"
        verbose_name_plural = "Construction progress updates"

    def __str__(self):
        return f"{self.progress.lot_award.unit} - {self.get_stage_display()} ({self.percent_complete}%)"

class Blacklist(models.Model):
    """
    Permanently disqualified beneficiaries.
    Checked automatically during eligibility check in Module 1.
    """
    REASON_CHOICES = [
        ('repossession', 'Unit Repossessed - Non-Compliance'),
        ('fraud', 'Fraudulent Information'),
        ('illegal_transfer', 'Illegal Unit Transfer'),
        ('other', 'Other Violation'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    applicant = models.OneToOneField(
        'intake.Applicant',
        on_delete=models.CASCADE,
        related_name='blacklist_record'
    )
    
    # Related records
    original_lot_award = models.ForeignKey(
        LotAward,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blacklist_records'
    )
    original_unit = models.ForeignKey(
        HousingUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blacklist_records'
    )
    
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    reason_details = models.TextField(verbose_name="Detailed Reason")
    
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    blacklisted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='blacklist_actions'
    )
    
    # Supporting documentation
    supporting_notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Blacklist Entry"
        verbose_name_plural = "Blacklist Entries"
    
    def __str__(self):
        return f"BLACKLISTED: {self.applicant.full_name}"


class CaseRecord(models.Model):
    """
    Case management records for housing-related complaints and disputes.
    Module 5: Case Management
    """
    STATUS_CHOICES = [
        ('Open', 'Open - Under Investigation'),
        ('Referred', 'Referred - Escalated'),
        ('Resolved', 'Resolved - Closed'),
    ]

    COMPLAINT_TYPE_CHOICES = [
        ('Boundary Dispute', 'Boundary Dispute'),
        ('Structural Issue', 'Structural Issue'),
        ('Interpersonal Conflict', 'Interpersonal Conflict'),
        ('Other', 'Other'),
    ]

    REFERRED_TO_CHOICES = [
        ('City Engineering Office', 'City Engineering Office'),
        ('Field Officer', 'Field Officer (Sir Russo)'),
        ('Attorney', 'Attorney'),
        ('Head (Arthur)', 'Head (Sir Arthur)'),
        ('None', '— None —'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Case identification
    case_number = models.CharField(max_length=50, unique=True, editable=False)
    site = models.ForeignKey(
        RelocationSite,
        on_delete=models.CASCADE,
        related_name='cases',
        null=True,
        blank=True
    )

    # Complainant info
    complainant_name = models.CharField(max_length=200)
    complainant_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Beneficiary Profile Reference"
    )

    # Complaint details
    complaint_type = models.CharField(max_length=50, choices=COMPLAINT_TYPE_CHOICES)
    description = models.TextField()
    date_received = models.DateField()

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')

    # Handler assignment
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cases_handled'
    )

    # Referral info (if escalated)
    referred_to = models.CharField(
        max_length=100,
        choices=REFERRED_TO_CHOICES,
        blank=True,
        null=True
    )
    referral_date = models.DateField(null=True, blank=True)

    # Resolution info
    outcome = models.TextField(blank=True)
    resolved_date = models.DateField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cases_created'
    )

    class Meta:
        ordering = ['-date_received']
        verbose_name = "Case Record"
        verbose_name_plural = "Case Records"

    def __str__(self):
        return f"{self.case_number} - {self.complainant_name}"

    def save(self, *args, **kwargs):
        # Auto-generate case number if not set
        if not self.case_number:
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            count = CaseRecord.objects.count() + 1
            self.case_number = f"CASE-{timestamp}-{count:04d}"
        super().save(*args, **kwargs)


class CaseUpdate(models.Model):
    """
    Tracks updates/notes added to a case during investigation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    case = models.ForeignKey(
        CaseRecord,
        on_delete=models.CASCADE,
        related_name='updates'
    )

    notes = models.TextField()

    # Who made this update
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='case_updates'
    )

    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Case Update"
        verbose_name_plural = "Case Updates"

    def __str__(self):
        return f"Update to {self.case.case_number}"


class SMSLog(models.Model):
    """
    Audit trail for Units (Housing/Occupancy) SMS notifications.
    Tracks occupancy updates, compliance notices, key turnover, etc.
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
        help_text="Event that triggered this SMS (key_turnover, occupancy_notice, compliance_notice, etc.)"
    )

    # Optional links to related records
    applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='units_sms_logs'
    )

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    external_id = models.CharField(max_length=100, blank=True, help_text="SMS provider message ID")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = "SMS Log (Units)"
        verbose_name_plural = "SMS Logs (Units)"

    def __str__(self):
        return f"SMS to {self.recipient_phone} - {self.trigger_event} ({self.status})"
