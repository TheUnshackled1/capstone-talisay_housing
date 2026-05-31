from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
import uuid
from units.monitoring_policy import (
    FINAL_INSPECTION_INSPECTION_LABEL,
    INITIAL_INSPECTION_INSPECTION_LABEL,
    TASK_TYPE_EXTENSION_FINAL,
    TASK_TYPE_EXTENSION_MIDPOINT,
    TASK_TYPE_EXTENSION_MONTH_3,
    TASK_TYPE_FINAL_INSPECTION,
    TASK_TYPE_FINAL_NOTICE,
    TASK_TYPE_INITIAL_INSPECTION,
)

_DIGITS_ONLY = RegexValidator(r'^\d+$', message='Must be digits only (0-9).')


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
        return self.units.filter(status=HousingUnit.STATUS_VACANT_AVAILABLE).count()


class HousingUnit(models.Model):
    """
    Individual housing unit (block/lot) at a relocation site.
    """
    STATUS_VACANT_AVAILABLE = 'Vacant — available'
    # Legacy typo (ASCII hyphen) from early lot-award code — still match for safety.
    STATUS_VACANT_AVAILABLE_LEGACY = 'Vacant - available'

    STATUS_CHOICES = [
        (STATUS_VACANT_AVAILABLE, 'Vacant — available'),
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

    block_number = models.CharField(max_length=10, validators=[_DIGITS_ONLY])
    lot_number = models.CharField(max_length=10, validators=[_DIGITS_ONLY])

    # Unit details
    area_sqm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Area (sq.m.)"
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_VACANT_AVAILABLE,
    )

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

    @classmethod
    def is_vacant_available_status(cls, value) -> bool:
        """True when status is Module 4 vacant (em dash or legacy hyphen spelling)."""
        if not value:
            return False
        text = (value or '').strip()
        if text in (cls.STATUS_VACANT_AVAILABLE, cls.STATUS_VACANT_AVAILABLE_LEGACY):
            return True
        normalized = text
        for ch in ('\u2014', '\u2013', '\u2212'):
            normalized = normalized.replace(ch, '-')
        return normalized == cls.STATUS_VACANT_AVAILABLE_LEGACY

    @classmethod
    def vacant_available_status_filter(cls):
        from django.db.models import Q

        return Q(status=cls.STATUS_VACANT_AVAILABLE) | Q(
            status=cls.STATUS_VACANT_AVAILABLE_LEGACY
        )

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


# =============================================================================
# MODULE 4 MONITORING WORKFLOW MODELS
# =============================================================================

class OccupancyMonitoringCycle(models.Model):
    """
    Tracks the overall occupancy monitoring lifecycle for a lot award.
    Manages transitions through: Original 30-day → Extension (1-3 months) → Final Notice (30 days)

    Each stage represents a distinct monitoring period with its own deadline.
    """
    STAGE_CHOICES = [
        ('original_30_day', 'Original 30-Day Monitoring'),
        ('extension_month_1', 'Extension Month 1'),
        ('extension_month_2', 'Extension Month 2'),
        ('extension_month_3', 'Extension Month 3'),
        ('final_notice_30_day', 'Final Notice — 30 Days'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    lot_award = models.ForeignKey(
        LotAward,
        on_delete=models.CASCADE,
        related_name='monitoring_cycles'
    )

    cycle_stage = models.CharField(
        max_length=30,
        choices=STAGE_CHOICES,
        default='original_30_day',
        help_text="Current monitoring stage in the lifecycle"
    )

    stage_start_date = models.DateField(
        help_text="When this stage begins"
    )
    stage_end_date = models.DateField(
        help_text="When this stage ends (deadline)"
    )

    days_allowed = models.PositiveIntegerField(
        default=30,
        help_text="Number of days allowed for this stage (30 for original, varies for extension)"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="True if this is the current active cycle"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Occupancy Monitoring Cycle"
        verbose_name_plural = "Occupancy Monitoring Cycles"

    def __str__(self):
        return f"{self.lot_award.unit} - {self.get_cycle_stage_display()}"

    @property
    def days_remaining(self):
        """Calculate days until deadline."""
        from datetime import date
        days = (self.stage_end_date - date.today()).days
        return max(0, days)

    @property
    def is_overdue(self):
        """Check if deadline has passed."""
        from datetime import date
        return date.today() > self.stage_end_date


class MonitoringTask(models.Model):
    """
    Scheduled inspection task assigned to caretaker/ronda.
    Created automatically when lot is awarded or extension is approved.

    Task types include: Day 90 Inspection, Day 120 Inspection, extension visits, Final Inspection.
    """
    TASK_TYPE_CHOICES = [
        (TASK_TYPE_INITIAL_INSPECTION, INITIAL_INSPECTION_INSPECTION_LABEL),
        (TASK_TYPE_FINAL_INSPECTION, FINAL_INSPECTION_INSPECTION_LABEL),
        (TASK_TYPE_EXTENSION_MIDPOINT, 'Extension Month 1 — Inspection'),
        (TASK_TYPE_EXTENSION_FINAL, 'Extension Month 2 — Inspection'),
        (TASK_TYPE_EXTENSION_MONTH_3, 'Extension Month 3 — Inspection'),
        (TASK_TYPE_FINAL_NOTICE, 'Final Inspection (Post-Notice)'),
    ]

    TASK_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    unit = models.ForeignKey(
        HousingUnit,
        on_delete=models.CASCADE,
        related_name='monitoring_tasks'
    )

    lot_award = models.ForeignKey(
        LotAward,
        on_delete=models.CASCADE,
        related_name='monitoring_tasks'
    )

    task_type = models.CharField(
        max_length=30,
        choices=TASK_TYPE_CHOICES,
        help_text="Type of monitoring task"
    )

    scheduled_date = models.DateField(
        help_text="When task was scheduled (creation date)"
    )

    due_date = models.DateField(
        help_text="Deadline for completing task"
    )

    days_from_award = models.PositiveIntegerField(
        help_text=(
            "Monitoring day after the 30-day possession grace period when the visit is due "
            "(90 for the first visit; 210 for the final visit, i.e. 120 calendar days after the 90 Day due date)."
        ),
    )

    status = models.CharField(
        max_length=20,
        choices=TASK_STATUS_CHOICES,
        default='pending'
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_monitoring_tasks',
        help_text="Caretaker or Ronda assigned to this task"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When task was completed"
    )

    notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When staff notified the monitoring dashboard about this task"
    )

    notified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notified_monitoring_tasks',
        help_text="Staff user who notified the monitoring dashboard"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', 'task_type']
        verbose_name = "Monitoring Task"
        verbose_name_plural = "Monitoring Tasks"
        indexes = [
            models.Index(fields=['assigned_to', 'status', 'due_date']),
            models.Index(fields=['lot_award', 'status']),
        ]

    def __str__(self):
        return f"{self.unit} - {self.get_task_type_display()} (Due: {self.due_date})"

    @property
    def is_overdue(self):
        """Check if task is past due and not completed."""
        from datetime import date
        return self.status != 'completed' and date.today() > self.due_date

    @property
    def days_until_due(self):
        """Calculate days until due date."""
        from datetime import date
        days = (self.due_date - date.today()).days
        return max(0, days) if self.status != 'completed' else 0


class MonitoringReport(models.Model):
    """
    Occupancy and construction report submitted by caretaker/ronda.
    Captures field observations including occupancy status, construction progress, and photo evidence.

    Used by monitoring evaluation engine to determine compliance and trigger escalations.
    """
    OCCUPANCY_STATUS_CHOICES = [
        ('properly_occupied', 'Properly Occupied'),
        ('temporarily_vacant', 'Temporarily Vacant'),
        ('unoccupied_abandoned', 'Unoccupied / Abandoned'),
    ]

    CONSTRUCTION_STATUS_CHOICES = [
        ('no_structure', 'No Structure'),
        ('ongoing_construction', 'Ongoing Construction'),
        ('site_clearing', 'Site Clearing'),
        ('foundation', 'Foundation'),
        ('wall_framing', 'Wall Framing'),
        ('roofing', 'Roofing'),
        ('finishing', 'Finishing'),
        ('completed_occupied', 'Completed / Occupied'),
    ]

    PROGRESS_ASSESSMENT_CHOICES = [
        ('normal_progress', 'Normal Progress'),
        ('no_progress', 'No Progress'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    task = models.ForeignKey(
        MonitoringTask,
        on_delete=models.CASCADE,
        related_name='reports',
        help_text="Monitoring task this report fulfills"
    )

    lot_award = models.ForeignKey(
        LotAward,
        on_delete=models.CASCADE,
        related_name='monitoring_reports'
    )

    unit = models.ForeignKey(
        HousingUnit,
        on_delete=models.CASCADE,
        related_name='monitoring_reports'
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='monitoring_reports_submitted',
        help_text="Caretaker/Ronda who submitted report"
    )

    # Occupancy information
    occupancy_status = models.CharField(
        max_length=30,
        choices=OCCUPANCY_STATUS_CHOICES,
        help_text="Current occupancy condition"
    )

    people_observed = models.CharField(
        max_length=100,
        blank=True,
        help_text="Number of people observed (e.g., '4', 'family of 3', 'none')"
    )

    occupancy_notes = models.TextField(
        blank=True,
        help_text="Observations about occupancy condition"
    )

    # Construction progress information
    construction_status = models.CharField(
        max_length=30,
        choices=CONSTRUCTION_STATUS_CHOICES,
        help_text="Current construction stage"
    )

    percent_complete = models.PositiveIntegerField(
        default=0,
        help_text="Estimated construction progress (0-100%)"
    )

    progress_notes = models.TextField(
        blank=True,
        help_text="Details about construction progress"
    )

    photo_evidence = models.FileField(
        upload_to='monitoring_evidence/%Y/%m/',
        blank=True,
        help_text="Field photo evidence captured during inspection"
    )

    # General remarks
    general_remarks = models.TextField(
        blank=True,
        help_text="Overall assessment and remarks from caretaker"
    )

    progress_assessment = models.CharField(
        max_length=30,
        choices=PROGRESS_ASSESSMENT_CHOICES,
        blank=True,
        help_text="Staff review decision after checking caretaker monitoring report"
    )

    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='monitoring_reports_assessed',
        help_text="Staff user who reviewed the monitoring report"
    )

    assessed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When staff reviewed the monitoring report"
    )

    # Completion status
    is_complete = models.BooleanField(
        default=True,
        help_text="True if all required fields are filled"
    )

    submitted_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Monitoring Report"
        verbose_name_plural = "Monitoring Reports"
        indexes = [
            models.Index(fields=['lot_award', '-submitted_at']),
            models.Index(fields=['occupancy_status', 'construction_status']),
        ]

    def __str__(self):
        return f"{self.unit} - {self.get_construction_status_display()} ({self.submitted_at.date()})"


class MonitoringReportPhoto(models.Model):
    """Additional photo evidence attached to a caretaker monitoring report."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    report = models.ForeignKey(
        MonitoringReport,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    image = models.FileField(
        upload_to='monitoring_evidence/%Y/%m/',
        help_text="Field photo evidence captured during inspection"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at', 'id']
        verbose_name = "Monitoring Report Photo"
        verbose_name_plural = "Monitoring Report Photos"

    def __str__(self):
        return f"Photo evidence for {self.report_id}"


class ExplanationReview(models.Model):
    """
    Track beneficiary explanations for construction delays or non-compliance.

    Triggered when monitoring evaluation engine detects no progress past deadline.
    Staff reviews caretaker reports + beneficiary explanation, then approves or denies extension.
    """
    REVIEW_STATUS_CHOICES = [
        ('pending_review', 'Pending Review'),
        ('approved', 'Approved — Extension Granted'),
        ('denied', 'Denied — Proceed to Final Notice'),
        ('needs_clarification', 'Needs Clarification — Request More Info'),
    ]

    TRIGGER_KIND_CHOICES = [
        ('staff_no_progress', 'Staff marked monitoring as No Progress'),
        ('auto_rule', 'Automated monitoring evaluation rule'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    lot_award = models.ForeignKey(
        LotAward,
        on_delete=models.CASCADE,
        related_name='explanation_reviews'
    )

    unit = models.ForeignKey(
        HousingUnit,
        on_delete=models.CASCADE,
        related_name='explanation_reviews'
    )

    triggered_by_report = models.ForeignKey(
        MonitoringReport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_explanations',
        help_text="MonitoringReport that triggered this explanation review"
    )

    trigger_kind = models.CharField(
        max_length=30,
        choices=TRIGGER_KIND_CHOICES,
        default='staff_no_progress',
        help_text="Whether this case was opened by staff assessment or automated rules",
    )

    # Staff-set deadline for the beneficiary to submit a written explanation at the office
    letter_deadline_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date/time by which the beneficiary must submit an explanation letter on file",
    )

    letter_document = models.FileField(
        upload_to='explanation_letters/%Y/%m/',
        blank=True,
        help_text="Scanned or uploaded explanation letter (staff)",
    )

    letter_received_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When staff recorded receipt of the explanation letter",
    )

    deadline_eve_sms_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the day-before deadline reminder SMS was sent",
    )

    deadline_due_sms_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the past-deadline / non-compliance notice SMS was sent",
    )

    # Beneficiary explanation (from SMS or system notification)
    beneficiary_explanation = models.TextField(
        blank=True,
        help_text="Explanation provided by beneficiary for delay"
    )

    explanation_submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When beneficiary submitted explanation"
    )

    # Staff review
    review_status = models.CharField(
        max_length=30,
        choices=REVIEW_STATUS_CHOICES,
        default='pending_review'
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='explanations_reviewed',
        help_text="THA Staff member who reviewed"
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When staff reviewed explanation"
    )

    staff_decision_notes = models.TextField(
        blank=True,
        help_text="Staff notes on decision"
    )

    # Extension decision (if approved)
    extension_approved = models.BooleanField(
        default=False,
        help_text="True if extension was approved"
    )

    extension_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        choices=[(1, '1 Month'), (2, '2 Months'), (3, '3 Months')],
        help_text="Duration of extension (if approved)"
    )

    extension_reason = models.TextField(
        blank=True,
        help_text="Staff notes on why extension was approved/denied"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Explanation Review"
        verbose_name_plural = "Explanation Reviews"
        indexes = [
            models.Index(fields=['review_status', '-created_at']),
            models.Index(fields=['lot_award', 'review_status']),
        ]

    def __str__(self):
        return f"{self.lot_award.unit} - {self.get_review_status_display()}"


class ExtensionRecord(models.Model):
    """
    Record of an extension approval containing dates and details.

    Created when ExplanationReview is approved.
    Triggers creation of Month 1, 2, 3 monitoring tasks and new MonitoringCycle.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    lot_award = models.ForeignKey(
        LotAward,
        on_delete=models.CASCADE,
        related_name='extensions'
    )

    explanation_review = models.ForeignKey(
        ExplanationReview,
        on_delete=models.CASCADE,
        related_name='extension_record',
        help_text="Explanation review that approved this extension"
    )

    extension_duration_months = models.PositiveIntegerField(
        choices=[(1, '1 Month'), (2, '2 Months'), (3, '3 Months')],
        help_text="Duration of extension in months"
    )

    extension_start_date = models.DateField(
        help_text="When extension period begins"
    )

    extension_end_date = models.DateField(
        help_text="When extension period ends (deadline)"
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_extensions',
        help_text="Staff member who approved extension"
    )

    approved_at = models.DateTimeField(auto_now_add=True)

    approval_notes = models.TextField(
        blank=True,
        help_text="Additional notes from staff on extension approval"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-approved_at']
        verbose_name = "Extension Record"
        verbose_name_plural = "Extension Records"

    def __str__(self):
        return f"{self.lot_award.unit} - {self.extension_duration_months}-Month Extension"

    @property
    def days_remaining(self):
        """Calculate days until extension deadline."""
        from datetime import date
        days = (self.extension_end_date - date.today()).days
        return max(0, days)

    @property
    def is_expired(self):
        """Check if extension period has ended."""
        from datetime import date
        return date.today() > self.extension_end_date
