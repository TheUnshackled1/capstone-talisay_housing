from django import forms
from .models import HouseholdMember, Applicant, CIVIL_STATUS_CHOICES
from django.core.exceptions import ValidationError
import re


def _is_weak_hazard_location_input(raw_location):
    """Match `intake.views._is_weak_hazard_location` for registration validation."""
    location = " ".join((raw_location or "").split()).strip().lower()
    if len(location) < 12:
        return True
    weak_values = {
        "n/a", "na", "none", "unknown", "same", "same as address",
        "same address", "barangay", "sitio", "landmark",
    }
    return location in weak_values


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
                'maxlength': 30,
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

DISPLACEMENT_REGISTRATION_CHOICES = [
    ('danger_zone', 'Danger Zone / Hazard Area (Option A)'),
    ('ejected', 'Ejected from previous residence (Option B)'),
    ('relocated', 'Relocated due to project / infrastructure (Option C)'),
    ('not_abc', 'None of A, B, or C (Option D)'),
]

# Aligned with Module 2 hazard options (stored on Applicant.danger_zone_type).
DANGER_ZONE_TYPES = [
    ('', '— Select hazard type —'),
    ('flood_prone', 'Flood-prone area'),
    ('landslide', 'Landslide-prone area'),
    ('storm_surge', 'Storm surge zone'),
    ('river_bank', 'River / creek bank'),
    ('cliff_edge', 'Cliff edge'),
    ('coastal', 'Coastal erosion'),
    ('other', 'Other hazard'),
]

EJECTION_REGISTRATION_CHOICES = list(Applicant.EJECTION_TYPE_CHOICES)


class WalkInApplicantForm(forms.ModelForm):
    """
    Module 1 office walk-in registration (Channel B desk).

    Applicant Situation (Options A–D) determines displacement particulars collected here:
    hazard (CDRRMO pathway), ejection, or government-project relocation. Details persist on the Applicant record for Modules 2–3 (verification workflows downstream).
    """
    barangay = forms.ChoiceField(
        choices=BARANGAY_CHOICES,
        required=True,
        label="Barangay",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    has_property_in_talisay = forms.ChoiceField(
        choices=[
            ('', '— Select —'),
            ('yes', 'Yes'),
            ('no', 'No'),
        ],
        required=True,
        label="Has Property Ownership in Talisay City",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    displacement_reason = forms.ChoiceField(
        choices=DISPLACEMENT_REGISTRATION_CHOICES,
        required=True,
        label="Applicant Situation (Options A–D)",
        widget=forms.RadioSelect(attrs={'class': 'form-radio'}),
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
        max_length=30,
        label="Hazard Location Description",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sitio, purok, river, creek, or nearby landmark',
            'maxlength': 30,
        })
    )

    ejection_type = forms.ChoiceField(
        choices=EJECTION_REGISTRATION_CHOICES,
        required=False,
        label="Ejection Classification",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    ejection_date = forms.DateField(
        required=False,
        label="Date of Notice or Ejection",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    project_name = forms.CharField(
        required=False,
        max_length=30,
        label="Project Designation",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Road-widening, drainage, infrastructure, or other government project',
            'maxlength': 30,
        }),
    )

    # Eligibility check required field
    years_residing = forms.IntegerField(
        required=True,
        min_value=5,
        max_value=99,
        label="Years Residing in Talisay",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 10',
            'min': 5,
            'max': 99,
            'maxlength': 2,
            'inputmode': 'numeric',
        }),
        help_text="Whole years in Talisay City (2 digits, 5–99).",
    )
    is_registered_voter_talisay = forms.TypedChoiceField(
        choices=[
            ('', '— Select —'),
            ('yes', 'Yes'),
            ('no', 'No'),
        ],
        coerce=lambda value: str(value).lower() == 'yes',
        empty_value='',
        required=True,
        label="Registered Voter in Talisay City",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    civil_status = forms.ChoiceField(
        choices=[('', '— Select —')] + list(CIVIL_STATUS_CHOICES),
        required=True,
        label="Civil Status",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'phone_number' in self.fields:
            self.fields['phone_number'].validators.append(validate_philippine_phone)
        if 'age' in self.fields:
            self.fields['age'].required = False
        if 'date_of_birth' in self.fields:
            self.fields['date_of_birth'].required = False

    class Meta:
        model = Applicant
        fields = [
            'last_name',
            'first_name',
            'middle_name',
            'extension_name',
            'sex',
            'civil_status',
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
            'is_registered_voter_talisay',
            'occupation',
            'employment_status',
            'has_property_in_talisay',
            'displacement_reason',
            'danger_zone_type',
            'danger_zone_location',
            'ejection_type',
            'ejection_date',
            'project_name',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Surname',
                'autofocus': True,
                'maxlength': 10,
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Given name',
                'maxlength': 15,
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Middle name (optional)',
                'maxlength': 10,
            }),
            'extension_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Jr., Sr., II, III, etc. (optional)',
                'maxlength': 5,
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
                'maxlength': 30,
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '09XXXXXXXXXX',
                'pattern': '09[0-9]{9}',
            }),
            'spouse_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Spouse full name',
                'maxlength': 30,
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
                'maxlength': 25,
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
            'civil_status': 'Civil Status',
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

    def clean_years_residing(self):
        years = self.cleaned_data.get('years_residing')
        if years is None:
            return years
        if years > 99:
            raise ValidationError('Years of residence must be at most 2 digits (99).')
        if years < 5:
            raise ValidationError(
                'Applicants with 4 years or below residency in Talisay City are not accepted. Minimum is 5 years.'
            )
        return years

    def clean(self):
        """Require hazard / ejection / project particulars by Applicant Situation (A–D)."""
        cleaned_data = super().clean()
        dr = (cleaned_data.get('displacement_reason') or '').strip()

        danger_zone_type = (cleaned_data.get('danger_zone_type') or '').strip()
        danger_zone_location = (cleaned_data.get('danger_zone_location') or '').strip()
        ejection_type = (cleaned_data.get('ejection_type') or '').strip()
        project_name = (cleaned_data.get('project_name') or '').strip()

        if dr == 'danger_zone':
            if not danger_zone_type:
                self.add_error('danger_zone_type', 'Hazard classification is required for Option A.')
            if not danger_zone_location:
                self.add_error('danger_zone_location', 'Hazard location description is required for Option A.')
            elif _is_weak_hazard_location_input(danger_zone_location):
                self.add_error(
                    'danger_zone_location',
                    'Location particulars must be specific (at least 12 characters), for example: sitio, landmark, and riverbank/road segment.',
                )
            cleaned_data['ejection_type'] = ''
            cleaned_data['ejection_date'] = None
            cleaned_data['project_name'] = ''
        elif dr == 'ejected':
            valid_ej = {key for key, _ in Applicant.EJECTION_TYPE_CHOICES if key}
            if ejection_type not in valid_ej:
                self.add_error('ejection_type', 'Ejection classification is required for Option B.')
            cleaned_data['danger_zone_type'] = ''
            cleaned_data['danger_zone_location'] = ''
            cleaned_data['project_name'] = ''
        elif dr == 'relocated':
            if not project_name:
                self.add_error('project_name', 'Project designation is required for Option C.')
            cleaned_data['danger_zone_type'] = ''
            cleaned_data['danger_zone_location'] = ''
            cleaned_data['ejection_type'] = ''
            cleaned_data['ejection_date'] = None
        else:
            # Option D or unset — clear situational particulars on save (view also normalizes)
            cleaned_data['danger_zone_type'] = ''
            cleaned_data['danger_zone_location'] = ''
            cleaned_data['ejection_type'] = ''
            cleaned_data['ejection_date'] = None
            cleaned_data['project_name'] = ''

        for text_field in (
            'last_name',
            'first_name',
            'middle_name',
            'extension_name',
            'place_of_birth',
            'spouse_name',
            'current_address',
            'occupation',
            'danger_zone_location',
            'project_name',
        ):
            raw = cleaned_data.get(text_field)
            if raw:
                cleaned_data[text_field] = str(raw).strip().upper()

        return cleaned_data

    def clean_has_property_in_talisay(self):
        """Normalize Yes/No selection into model boolean semantics."""
        value = (self.cleaned_data.get('has_property_in_talisay') or '').strip().lower()
        if value not in {'yes', 'no'}:
            raise forms.ValidationError('Please select Yes or No for property ownership.')
        return value == 'yes'
