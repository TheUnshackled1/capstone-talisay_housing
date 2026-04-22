from django.db import models
from django.conf import settings
import uuid


class Document(models.Model):
    """
    Centralized digital archive for all applicant/beneficiary documents.
    Replaces physical folders as primary working reference.
    """
    DOCUMENT_TYPE_CHOICES = [
        # Group A - Applicant Requirements
        ('barangay_residency', 'Barangay Certificate of Residency'),
        ('barangay_indigency', 'Barangay Certificate of Indigency'),
        ('cedula', 'Cedula (Community Tax Certificate)'),
        ('police_clearance', 'Police Clearance'),
        ('no_property', 'Certificate of No Property'),
        ('photo_2x2', '2x2 Picture'),
        ('house_sketch', 'Sketch of House Location'),
        
        # Group B - Office-Generated
        ('application_form', 'Application Form'),
        ('notarized_docs', 'Notarized Documents'),
        ('engineering_assessment', 'Engineering Assessment'),
        ('signed_application', 'Signed Application (Head-Approved)'),
        
        # Group C - Post-Award
        ('lot_award', 'Lot Award Document'),
        ('electricity_app', 'Electricity Connection Application'),
        ('cdrrmo_cert', 'CDRRMO Certification'),
        ('explanation_letter', 'Explanation Letter'),
        
        # Other
        ('other', 'Other Document'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to applicant profile
    applicant = models.ForeignKey(
        'intake.Applicant',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    # Optionally link to specific requirement submission
    requirement_submission = models.ForeignKey(
        'applications.RequirementSubmission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    
    # File storage
    file = models.FileField(upload_to='documents/%Y/%m/')
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True)
    
    # Upload tracking
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        indexes = [
            models.Index(fields=['applicant', 'document_type']),
            models.Index(fields=['document_type']),
        ]
    
    def __str__(self):
        return f"{self.applicant.full_name} - {self.get_document_type_display()}"
    
    @property
    def file_size_display(self):
        """Human-readable file size."""
        if self.file_size is None:
            return "—"
        if self.file_size == 0:
            return "—"
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
