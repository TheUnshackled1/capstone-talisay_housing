from django import forms
from .models import LandownerSubmission, ISFRecord, HouseholdMember, Applicant


# Talisay City barangays (official 27 barangays)
# Add/remove barangays here - changes will automatically reflect in all forms
BARANGAY_CHOICES = [
    ('', 'Select Barangay'),
    ('Bubog', 'Bubog'),
    ('Cabatangan', 'Cabatangan'),
    ('Concepcion', 'Concepcion'),
    ('Dos Hermanas', 'Dos Hermanas'),
    ('Efigenio Lizares', 'Efigenio Lizares'),
    ('Katilingban', 'Katilingban'),
    ('Matab-ang', 'Matab-ang'),
    ('San Fernando', 'San Fernando'),
    ('Zone 1 (Pob.)', 'Zone 1 (Pob.)'),
    ('Zone 2 (Pob.)', 'Zone 2 (Pob.)'),
    ('Zone 3 (Pob.)', 'Zone 3 (Pob.)'),
    ('Zone 4 (Pob.)', 'Zone 4 (Pob.)'),
    ('Zone 4-A (Pob.)', 'Zone 4-A (Pob.)'),
    ('Zone 5 (Pob.)', 'Zone 5 (Pob.)'),
    ('Zone 6 (Pob.)', 'Zone 6 (Pob.)'),
    ('Zone 7 (Pob.)', 'Zone 7 (Pob.)'),
    ('Zone 8 (Pob.)', 'Zone 8 (Pob.)'),
    ('Zone 9 (Pob.)', 'Zone 9 (Pob.)'),
    ('Zone 10 (Pob.)', 'Zone 10 (Pob.)'),
    ('Zone 11 (Pob.)', 'Zone 11 (Pob.)'),
    ('Zone 12 (Pob.)', 'Zone 12 (Pob.)'),
    ('Zone 12-A (Pob.)', 'Zone 12-A (Pob.)'),
    ('Zone 14 (Pob.)', 'Zone 14 (Pob.)'),
    ('Zone 14-A (Pob.)', 'Zone 14-A (Pob.)'),
    ('Zone 14-B (Pob.)', 'Zone 14-B (Pob.)'),
    ('Zone 15 (Pob.)', 'Zone 15 (Pob.)'),
    ('Zone 16 (Pob.)', 'Zone 16 (Pob.)'),
]


class LandownerSubmissionForm(forms.ModelForm):
    """
    Landowner submission form (enhanced).
    Public form - no authentication required.
    Collects: landowner name, phone, email, property address, barangay
    """
    barangay = forms.ChoiceField(
        choices=BARANGAY_CHOICES,
        required=False,
        label="Barangay",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = LandownerSubmission
        fields = [
            'landowner_name',
            'landowner_phone',
            'landowner_email',
            'property_address',
        ]
        widgets = {
            'landowner_name': forms.TextInput(attrs={
                'placeholder': 'Enter your full name',
                'autofocus': True,
                'class': 'form-control',
            }),
            'landowner_phone': forms.TextInput(attrs={
                'placeholder': '09XX-XXX-XXXX',
                'class': 'form-control',
            }),
            'landowner_email': forms.EmailInput(attrs={
                'placeholder': 'email@example.com',
                'class': 'form-control',
            }),
            'property_address': forms.Textarea(attrs={
                'placeholder': 'Complete address of the property where informal settlers are residing',
                'rows': 2,
                'class': 'form-control',
            }),
        }
        labels = {
            'landowner_name': 'Full Name',
            'landowner_phone': 'Contact Number',
            'landowner_email': 'Email Address',
            'property_address': 'Property Address',
        }


class ISFRecordForm(forms.ModelForm):
    """
    Minimal ISF form (spec-compliant).
    Used dynamically in the landowner form.
    Only 4 fields: name, household count, income, years residing
    """
    class Meta:
        model = ISFRecord
        fields = [
            'full_name',
            'household_members',
            'monthly_income',
            'years_residing',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'placeholder': 'Full name of informal settler',
                'class': 'form-control',
            }),
            'household_members': forms.NumberInput(attrs={
                'placeholder': 'Number of people in household',
                'min': 1,
                'max': 20,
                'class': 'form-control',
            }),
            'monthly_income': forms.NumberInput(attrs={
                'placeholder': 'Monthly household income',
                'min': 0,
                'step': '0.01',
                'class': 'form-control',
            }),
            'years_residing': forms.NumberInput(attrs={
                'placeholder': 'Years living on this property',
                'min': 0,
                'max': 100,
                'class': 'form-control',
            }),
        }
        labels = {
            'full_name': 'Full Name',
            'household_members': 'Number of Household Members',
            'monthly_income': 'Monthly Income (₱)',
            'years_residing': 'Years Residing on Property',
        }


class ISFEligibilityForm(forms.ModelForm):
    """
    Staff form for checking ISF eligibility.
    Used by Jocel to review and mark applicants.
    """
    class Meta:
        model = ISFRecord
        fields = ['status', 'disqualification_reason']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'disqualification_reason': forms.Textarea(attrs={
                'placeholder': 'If disqualified, enter reason here...',
                'rows': 3,
            }),
        }


class ISFReviewForm(forms.ModelForm):
    """
    Enhanced form for Jocel to add missing information during review.
    Adds: phone number, barangay extraction, property ownership check.
    """
    barangay = forms.ChoiceField(
        choices=BARANGAY_CHOICES,
        required=True,
        label="Barangay",
        help_text="Extract from property address",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    has_property_in_talisay = forms.ChoiceField(
        choices=[
            ('', '-- Select --'),
            ('no', 'No Property Ownership ✓'),
            ('yes', 'Owns Property (Disqualified)'),
        ],
        required=True,
        label="Property Ownership Verification",
        help_text="Verified against Assessor's Office records",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = ISFRecord
        fields = [
            'phone_number',
            'status',
            'disqualification_reason',
        ]
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'placeholder': '09XX XXX XXXX',
                'class': 'form-control',
            }),
            'status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'disqualification_reason': forms.Textarea(attrs={
                'placeholder': 'Required if marking as disqualified',
                'rows': 3,
                'class': 'form-control',
            }),
        }
        labels = {
            'phone_number': 'Contact Number (for SMS)',
            'status': 'Eligibility Status',
            'disqualification_reason': 'Disqualification Reason',
        }


class HouseholdMemberForm(forms.ModelForm):
    """
    Form for adding detailed household member information.
    Jocel adds actual names during eligibility review.
    """
    class Meta:
        model = HouseholdMember
        fields = [
            'full_name',
            'relationship',
            'date_of_birth',
            'sex',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'placeholder': 'Full name',
                'class': 'form-control',
            }),
            'relationship': forms.Select(attrs={
                'class': 'form-select',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'sex': forms.Select(attrs={
                'class': 'form-select',
            }),
        }
        labels = {
            'full_name': 'Full Name',
            'relationship': 'Relationship to Applicant',
            'date_of_birth': 'Date of Birth',
            'sex': 'Sex',
        }


# ============================================================
# Channel B/C Walk-in Registration Forms
# ============================================================

DANGER_ZONE_TYPES = [
    ('', '-- Select Danger Zone Type --'),
    ('riverside', 'Riverside / Riverbank'),
    ('flood_prone', 'Flood-Prone Area'),
    ('landslide', 'Landslide-Prone Area'),
    ('coastal', 'Coastal / Near Shoreline'),
    ('railroad', 'Near Railroad Tracks'),
    ('road_right_of_way', 'Road Right of Way'),
    ('other', 'Other Danger Zone'),
]


class WalkInApplicantForm(forms.ModelForm):
    """
    Registration form for Channel B (Danger Zone) and Channel C (Walk-in) applicants.
    Used at the THA office during walk-in registration.
    """
    barangay = forms.ChoiceField(
        choices=BARANGAY_CHOICES,
        required=True,
        label="Barangay",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    channel = forms.ChoiceField(
        choices=[
            ('walk_in', 'Channel C — Regular Walk-in'),
            ('danger_zone', 'Channel B — Danger Zone (Priority)'),
        ],
        required=True,
        label="Application Channel",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'channel-select'})
    )
    
    # Danger zone specific fields (shown only for Channel B)
    danger_zone_type = forms.ChoiceField(
        choices=DANGER_ZONE_TYPES,
        required=False,
        label="Danger Zone Type",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    danger_zone_location = forms.CharField(
        required=False,
        label="Danger Zone Location Details",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Describe the specific danger zone location...'
        })
    )
    
    class Meta:
        model = Applicant
        fields = [
            'full_name',
            'phone_number',
            'current_address',
            'monthly_income',
            'household_size',
            'years_residing',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name (Last Name, First Name Middle Name)',
                'autofocus': True,
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '09XX XXX XXXX',
            }),
            'current_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Current residential address',
            }),
            'monthly_income': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Monthly household income',
                'min': 0,
                'step': '0.01',
            }),
            'household_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of household members',
                'min': 1,
            }),
            'years_residing': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Years at current location',
                'min': 0,
            }),
        }
        labels = {
            'full_name': 'Full Name',
            'phone_number': 'Contact Number (for SMS)',
            'current_address': 'Current Address',
            'monthly_income': 'Monthly Income (₱)',
            'years_residing': 'Years Residing at Location',
        }
    
    def clean_monthly_income(self):
        """Validate income is non-negative."""
        income = self.cleaned_data.get('monthly_income')
        if income and income < 0:
            raise forms.ValidationError('Monthly income cannot be negative.')
        return income
    
    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()
        channel = cleaned_data.get('channel')
        danger_zone_type = cleaned_data.get('danger_zone_type')
        danger_zone_location = cleaned_data.get('danger_zone_location')
        
        # If Channel B (danger zone), require danger zone details
        if channel == 'danger_zone':
            if not danger_zone_type:
                self.add_error('danger_zone_type', 'Please specify the danger zone type.')
            if not danger_zone_location:
                self.add_error('danger_zone_location', 'Please describe the danger zone location.')
        
        return cleaned_data
