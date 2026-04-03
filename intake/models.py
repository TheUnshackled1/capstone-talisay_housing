from django.db import models
from django.conf import settings
import uuid


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
    barangay = models.CharField(max_length=100, verbose_name="Barangay")
    
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
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('eligible', 'Eligible'),
        ('disqualified', 'Disqualified'),
        ('in_queue', 'In Priority Queue'),
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
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference_number} - {self.full_name}"

    @property
    def is_income_eligible(self):
        """Check if monthly income is within ₱10,000 threshold."""
        return self.monthly_income <= 10000
