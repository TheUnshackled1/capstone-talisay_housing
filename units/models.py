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
        return self.units.filter(status='occupied').count()
    
    @property
    def vacant_units_count(self):
        return self.units.filter(status='vacant').count()


class HousingUnit(models.Model):
    """
    Individual housing unit (block/lot) at a relocation site.
    """
    STATUS_CHOICES = [
        ('vacant', 'Vacant - Available'),
        ('occupied', 'Occupied'),
        ('notice_30', 'Under Notice - 30 Days'),
        ('notice_10', 'Under Notice - 10 Days (Final)'),
        ('repossessed', 'Repossessed'),
        ('maintenance', 'Under Maintenance'),
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
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='vacant')
    
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


class ElectricityConnection(models.Model):
    """
    Tracks Negros Power electricity connection per beneficiary.
    Managed by Joie (2nd Member) and Laarni (5th Member).
    """
    STATUS_CHOICES = [
        ('pending', 'Pending - Not Started'),
        ('docs_submitted', 'Documents Submitted to Negros Power'),
        ('coordinating', 'Coordination in Progress'),
        ('approved', 'Connection Approved'),
        ('completed', 'Connection Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    lot_award = models.OneToOneField(
        LotAward,
        on_delete=models.CASCADE,
        related_name='electricity_connection'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timeline tracking
    initiated_at = models.DateTimeField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='electricity_initiated'
    )
    
    docs_submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Negros Power reference
    negros_power_reference = models.CharField(max_length=50, blank=True)
    
    notes = models.TextField(blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Electricity Connection"
        verbose_name_plural = "Electricity Connections"
    
    def __str__(self):
        return f"Electricity - {self.lot_award.unit}"


class ComplianceNotice(models.Model):
    """
    Compliance notices issued to beneficiaries.
    30-day reminder → 10-day final → Repossession if no response.
    """
    NOTICE_TYPE_CHOICES = [
        ('reminder_30', 'Reminder Notice (30 Days)'),
        ('final_10', 'Final Notice (10 Days)'),
        ('custom', 'Custom Notice Period'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active - Awaiting Response'),
        ('complied', 'Complied - Resolved'),
        ('escalated', 'Escalated - No Response'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    lot_award = models.ForeignKey(
        LotAward,
        on_delete=models.CASCADE,
        related_name='compliance_notices'
    )
    unit = models.ForeignKey(
        HousingUnit,
        on_delete=models.CASCADE,
        related_name='compliance_notices'
    )
    
    notice_type = models.CharField(max_length=20, choices=NOTICE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Reason for notice
    reason = models.TextField(verbose_name="Reason for Notice")
    
    # Timeline
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='notices_issued'
    )
    
    days_granted = models.PositiveIntegerField(
        verbose_name="Days to Comply",
        help_text="Number of days before deadline"
    )
    deadline = models.DateField()
    
    # Response tracking
    response_received_at = models.DateTimeField(null=True, blank=True)
    response_received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responses_received'
    )
    response_notes = models.TextField(blank=True)
    
    # Resolution
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_decision = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notice_decisions'
    )
    
    class Meta:
        ordering = ['-issued_at']
        verbose_name = "Compliance Notice"
        verbose_name_plural = "Compliance Notices"
    
    def __str__(self):
        return f"{self.get_notice_type_display()} - {self.unit}"
    
    @property
    def days_remaining(self):
        """Calculate days until deadline."""
        from django.utils import timezone
        if self.status != 'active':
            return 0
        remaining = (self.deadline - timezone.now().date()).days
        return max(0, remaining)
    
    @property
    def is_approaching_deadline(self):
        """Flag if 5 or fewer days remaining."""
        return self.days_remaining <= 5 and self.status == 'active'
    
    @property
    def is_overdue(self):
        """Flag if deadline has passed."""
        return self.days_remaining == 0 and self.status == 'active'


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


class OccupancyReport(models.Model):
    """
    Weekly occupancy reports submitted by caretaker via mobile form.
    Reviewed and confirmed by field team.
    """
    STATUS_CHOICES = [
        ('submitted', 'Submitted - Pending Review'),
        ('confirmed', 'Confirmed by Field Team'),
        ('discrepancy', 'Discrepancy Found'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    site = models.ForeignKey(
        RelocationSite,
        on_delete=models.CASCADE,
        related_name='occupancy_reports'
    )
    
    # Reporting period
    report_week_start = models.DateField()
    report_week_end = models.DateField()
    
    # Submitted by caretaker
    submitted_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='occupancy_reports_submitted'
    )
    
    # Counts from caretaker
    reported_occupied = models.PositiveIntegerField(default=0)
    reported_vacant = models.PositiveIntegerField(default=0)
    reported_concerns = models.PositiveIntegerField(default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    
    # Field team review
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='occupancy_reports_reviewed'
    )
    
    # Confirmed counts (after field team review)
    confirmed_occupied = models.PositiveIntegerField(null=True, blank=True)
    confirmed_vacant = models.PositiveIntegerField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    discrepancy_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-report_week_start']
        verbose_name = "Occupancy Report"
        verbose_name_plural = "Occupancy Reports"
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'report_week_start'],
                name='unique_weekly_report_per_site'
            )
        ]
    
    def __str__(self):
        return f"{self.site.code} - Week of {self.report_week_start}"


class OccupancyReportDetail(models.Model):
    """
    Per-unit status in weekly occupancy report.
    """
    UNIT_STATUS_CHOICES = [
        ('occupied', 'Occupied'),
        ('unoccupied', 'Unoccupied'),
        ('concern', 'Concern Noted'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    report = models.ForeignKey(
        OccupancyReport,
        on_delete=models.CASCADE,
        related_name='details'
    )
    unit = models.ForeignKey(
        HousingUnit,
        on_delete=models.CASCADE,
        related_name='occupancy_report_details'
    )
    
    reported_status = models.CharField(max_length=20, choices=UNIT_STATUS_CHOICES)
    concern_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['report', 'unit']
        verbose_name = "Occupancy Report Detail"
        verbose_name_plural = "Occupancy Report Details"
        constraints = [
            models.UniqueConstraint(
                fields=['report', 'unit'],
                name='unique_unit_per_report'
            )
        ]
    
    def __str__(self):
        return f"{self.report} - {self.unit}"
