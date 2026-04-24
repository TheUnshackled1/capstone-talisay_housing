from django import forms
from .models import HouseholdMember, Applicant
from django.core.exceptions import ValidationError
import re


def validate_philippine_phone(value):
    """
    Validates Philippine phone number format.
    Accepts: 09XXXXXXXXXX (11 digits, starts with 09)
    """
    if not value:  # Allow empty (optional fields)
        return

    # Clean to digits only
    clean = re.sub(r'\D', '', str(value))

    # Check length and format
    if len(clean) != 11 or not clean.startswith('09'):
        raise ValidationError(
            'Invalid Philippine phone number. Required format: 09XXXXXXXXXX (11 digits)',
            code='invalid_ph_phone'
        )


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
# Channel B: Danger Zone Registration Form
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
    Module 1 office walk-in registration (Channel B desk).
    Hazard-area particulars are optional; when declared, the backend opens a
    CDRRMO verification (claim-only) workflow — CDRRMO does not log into the system.
    """
    barangay = forms.ChoiceField(
        choices=BARANGAY_CHOICES,
        required=True,
        label="Barangay",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Danger zone specific fields (optional - only required if applicant IS in danger zone)
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

    # Eligibility check required field
    years_residing = forms.IntegerField(
        required=True,
        min_value=0,
        label="Years Residing in Talisay",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Number of years',
            'min': 0,
        }),
        help_text="Required for eligibility check"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Philippine phone validator to phone_number field
        if 'phone_number' in self.fields:
            self.fields['phone_number'].validators.append(validate_philippine_phone)

    class Meta:
        model = Applicant
        fields = [
            'last_name',
            'first_name',
            'middle_name',
            'extension_name',
            'sex',
            'age',
            'date_of_birth',
            'place_of_birth',
            'phone_number',
            'spouse_name',
            'spouse_phone',
            'current_address',
            'monthly_income',
            'household_size',
            'years_residing',
            'occupation',
            'employment_status',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Surname',
                'autofocus': True,
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Given name',
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Middle name (optional)',
            }),
            'extension_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Jr., Sr., II, III, etc. (optional)',
            }),
            'sex': forms.RadioSelect(attrs={
                'class': 'form-radio',
            }),
            'age': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Age',
                'min': 0,
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'place_of_birth': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City/Municipality, Province',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '09XXXXXXXXXX',
                'pattern': '09[0-9]{9}',
            }),
            'spouse_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Spouse full name',
            }),
            'spouse_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '09XXXXXXXXXX',
                'pattern': '09[0-9]{9}',
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
            'occupation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Occupation/job title',
            }),
            'employment_status': forms.Select(attrs={
                'class': 'form-select',
            }),
        }
        labels = {
            'full_name': 'Full Name',
            'last_name': 'Last Name (Surname)',
            'first_name': 'First Name (Given Name)',
            'middle_name': 'Middle Name',
            'extension_name': 'Extension Name',
            'sex': 'Sex',
            'age': 'Age',
            'date_of_birth': 'Date of Birth',
            'place_of_birth': 'Place of Birth',
            'phone_number': 'Applicant Contact Number',
            'spouse_name': 'Name of Spouse (if applicable)',
            'spouse_phone': 'Spouse Contact Number',
            'current_address': 'Current Address',
            'monthly_income': 'Monthly Income (₱)',
            'household_size': 'Household Size',
            'years_residing': 'Years Residing in Talisay',
            'occupation': 'Occupation',
            'employment_status': 'Status of Employment',
        }

    def clean_monthly_income(self):
        """Validate income is non-negative."""
        income = self.cleaned_data.get('monthly_income')
        if income and income < 0:
            raise forms.ValidationError('Monthly income cannot be negative.')
        return income

    def clean(self):
        """Custom validation for danger zone fields - only required if is_danger_zone=true."""
        cleaned_data = super().clean()

        # Check if is_danger_zone was in the original POST data
        is_danger_zone = self.data.get('is_danger_zone', 'false')

        # Only validate danger zone fields if applicant is in danger zone
        if is_danger_zone == 'true':
            danger_zone_type = cleaned_data.get('danger_zone_type')
            danger_zone_location = cleaned_data.get('danger_zone_location')

            if not danger_zone_type:
                self.add_error('danger_zone_type', 'This field is required for danger zone applicants.')
            if not danger_zone_location or not danger_zone_location.strip():
                self.add_error('danger_zone_location', 'This field is required for danger zone applicants.')

        return cleaned_data
