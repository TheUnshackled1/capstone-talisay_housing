import re
import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

# Office-controlled IDs: CASE-2026-0001 (calendar year + 4-digit sequence)
CASE_NUMBER_PATTERN = re.compile(r'^CASE-(\d{4})-(\d+)$')


class CaseYearSequence(models.Model):
    """Per-calendar-year counter for sequential case numbers (THA office control)."""
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(
        default=0,
        help_text='Last assigned sequence for this year; next case is last_number + 1.',
    )

    class Meta:
        verbose_name = 'Case number sequence'
        verbose_name_plural = 'Case number sequences'

    def __str__(self):
        return f'{self.year}: {self.last_number} issued'


def _max_sequential_for_year(year: int) -> int:
    """Highest CASE-YYYY-NNNN already stored for the given year."""
    prefix = f'CASE-{year}-'
    max_n = 0
    for case_number in Case.objects.filter(case_number__startswith=prefix).values_list(
        'case_number', flat=True
    ):
        match = CASE_NUMBER_PATTERN.match(case_number)
        if match and int(match.group(1)) == year:
            max_n = max(max_n, int(match.group(2)))
    return max_n


def allocate_case_number() -> str:
    """
    Next office case ID for the current calendar year.
    Thread-safe under concurrent creates (row lock on CaseYearSequence).
    """
    year = timezone.now().year
    with transaction.atomic():
        seq, _created = CaseYearSequence.objects.select_for_update().get_or_create(
            year=year,
            defaults={'last_number': _max_sequential_for_year(year)},
        )
        db_max = _max_sequential_for_year(year)
        if seq.last_number < db_max:
            seq.last_number = db_max
        seq.last_number += 1
        next_num = seq.last_number
        seq.save(update_fields=['last_number'])
    return f'CASE-{year}-{next_num:04d}'


class Case(models.Model):
    """
    Complaint and violation case tracking.
    First formal complaint tracking system for THA.
    Every complaint gets a case record until resolved.
    """
    CASE_TYPE_CHOICES = [
        ('lot_boundary', 'LOT BOUNDARY'),
        ('noise', 'NOISE COMPLAINT'),
        ('drunk_disturbance', 'DRUNK DISTURBANCE'),
        ('community_quarrel', 'COMMUNITY QUARREL'),
        ('illegal_occupant', 'ILLEGAL OCCUPANT CONCERN'),
        ('occupancy_dispute', 'OCCUPANCY DISPUTE'),
        ('sanitation', 'SANITATION COMPLAINT'),
        ('other', 'OTHER COMMUNITY CONCERN'),
    ]

    STATUS_CHOICES = [
        ('pending_review', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('mediation_monitoring', 'Settlement'),
        ('awaiting_response', 'Awaiting Response'),
        ('referred_engineering', 'Awaiting Engineering Findings'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    RECEIVED_AT_CHOICES = [
        ('office', 'THA Office'),
        ('onsite', 'On-site at Relocation Site'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case_number = models.CharField(max_length=20, unique=True, editable=False)
    
    case_type = models.CharField(max_length=20, choices=CASE_TYPE_CHOICES)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default='pending_review')
    
    # Complainant/Reporter
    complainant_name = models.CharField(max_length=255)
    complainant_phone = models.CharField(max_length=20, blank=True)
    
    # Link to beneficiary profile (if complainant is an awardee)
    complainant_applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cases_filed'
    )
    
    # Link to housing unit (if case involves specific unit)
    related_unit = models.ForeignKey(
        'units.HousingUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cases'
    )
    
    # Subject of complaint (if different from complainant)
    subject_name = models.CharField(max_length=255, blank=True)
    subject_applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cases_against'
    )
    
    # Intake details
    received_at_location = models.CharField(
        max_length=20,
        choices=RECEIVED_AT_CHOICES,
        default='office'
    )
    received_at = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cases_received'
    )
    
    # Description
    initial_description = models.CharField(
        max_length=100,
        verbose_name='Incident description',
    )
    
    # Investigation
    investigation_notes = models.TextField(blank=True)
    investigated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cases_investigated'
    )
    investigated_at = models.DateTimeField(null=True, blank=True)
    # Field desk acknowledged case details; unlocks mediation evidence (carousel section 2).
    field_intake_reviewed_at = models.DateTimeField(null=True, blank=True)
    SETTLEMENT_OUTCOME_CHOICES = [
        ('settled', 'Settled'),
        ('not_settled', 'Not settled'),
    ]
    field_settlement_outcome = models.CharField(
        max_length=16,
        choices=SETTLEMENT_OUTCOME_CHOICES,
        blank=True,
    )
    field_settlement_saved_at = models.DateTimeField(null=True, blank=True)

    # Referral tracking
    referred_to = models.CharField(
        max_length=100,
        blank=True,
        help_text="E.g., City Engineering, THA Head"
    )
    referred_at = models.DateTimeField(null=True, blank=True)
    referral_notes = models.TextField(blank=True)
    
    # Decision/Resolution
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cases_decided'
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Closure (Step 7)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closure_outcome = models.CharField(
        max_length=255,
        blank=True,
        help_text='Short outcome summary when case is closed',
    )

    # Monitoring (Step 6)
    follow_up_at = models.DateField(null=True, blank=True)
    monitored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='monitored_cases',
        help_text='Ronda tagged by staff to observe this case on-site.',
    )

    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-received_at']
        verbose_name = "Case"
        verbose_name_plural = "Cases"
    
    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = allocate_case_number()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.case_number} - {self.get_case_type_display()}"
    
    @property
    def days_open(self):
        """Calculate how many days the case has been open."""
        if self.status in ['resolved', 'closed']:
            return 0
        from django.utils import timezone
        return (timezone.now() - self.received_at).days
    
    @property
    def is_stale(self):
        """Flag if case has been open > 14 days without resolution."""
        return self.days_open > 14 and self.status not in ['resolved', 'closed']


class CaseAction(models.Model):
    """Step 5 — recorded staff action (warning, mediation, referral, etc.)."""
    ACTION_CHOICES = [
        ('refer_engineering', 'Refer to City Engineering'),
        ('issue_warning', 'Issue warning'),
        ('schedule_mediation', 'Schedule mediation'),
        ('monitor_complaint', 'Monitor complaint'),
        ('record_incident', 'Record incident'),
        ('record_resolution', 'Record resolution'),
        ('review_occupancy', 'Review occupancy'),
        ('request_clarification', 'Request clarification'),
        ('monitor_case', 'Monitor case'),
        ('issue_reminder', 'Issue reminder'),
        ('monitor_compliance', 'Monitor compliance'),
        ('schedule_inspection', 'Schedule lot survey'),
        ('verbal_warning', 'Verbal warning issued'),
        ('written_warning', 'Written warning issued'),
        ('mediation_held', 'Mediation conducted'),
        ('notice_issued', 'Notice issued'),
        ('follow_up', 'Follow-up logged'),
        ('other', 'Other action recorded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='actions')
    action_type = models.CharField(max_length=32, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='case_actions_created',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Case action'
        verbose_name_plural = 'Case actions'

    def __str__(self):
        return f'{self.get_action_type_display()} on {self.case.case_number}'


class CaseEvidence(models.Model):
    """Photos or documents uploaded during case review (Step 4)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='evidence',
    )
    file = models.FileField(upload_to='cases/evidence/%Y/%m/')
    caption = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='case_evidence_uploaded',
    )

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Case evidence'
        verbose_name_plural = 'Case evidence'

    def __str__(self):
        return f'Evidence for {self.case.case_number}'


class FieldSettledIncidentLog(models.Model):
    """On-site memory log — not a formal case."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    related_unit = models.ForeignKey(
        'units.HousingUnit',
        on_delete=models.CASCADE,
        related_name='settled_incident_logs',
    )
    complainant_name = models.CharField(max_length=255, blank=True)
    complainant_phone = models.CharField(max_length=20, blank=True)
    complainant_applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settled_incident_logs_as_complainant',
    )
    subject_applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settled_incident_logs',
    )
    subject_name = models.CharField(max_length=255, blank=True)
    case_type = models.CharField(max_length=20, choices=Case.CASE_TYPE_CHOICES)
    description = models.CharField(max_length=150)
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settled_incident_logs',
    )
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']
        verbose_name = 'Settled incident log'
        verbose_name_plural = 'Settled incident logs'

    def __str__(self):
        return f'Settled log {self.id}'

