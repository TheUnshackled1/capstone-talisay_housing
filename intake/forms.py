from django import forms
from .models import LandownerSubmission, ISFRecord


# Talisay City barangays
BARANGAY_CHOICES = [
    ('', 'Select Barangay'),
    ('Abuanan', 'Abuanan'),
    ('Bago', 'Bago'),
    ('Cabatangan', 'Cabatangan'),
    ('Caradio-an', 'Caradio-an'),
    ('Concordia Sur', 'Concordia Sur'),
    ('Dos Hermanas', 'Dos Hermanas'),
    ('Efigenio Lizares', 'Efigenio Lizares'),
    ('Esperanza', 'Esperanza'),
    ('Guimbala-on', 'Guimbala-on'),
    ('Himoga-an Baybay', 'Himoga-an Baybay'),
    ('Lag-asan', 'Lag-asan'),
    ('Matab-ang', 'Matab-ang'),
    ('Nabitasan', 'Nabitasan'),
    ('Rizal', 'Rizal'),
    ('San Fernando', 'San Fernando'),
    ('San Francisco', 'San Francisco'),
    ('San Jose', 'San Jose'),
    ('San Juan', 'San Juan'),
    ('San Roque', 'San Roque'),
    ('Tabao', 'Tabao'),
    ('Taloc', 'Taloc'),
    ('Tamlang', 'Tamlang'),
    ('Tangub', 'Tangub'),
    ('Tanjay', 'Tanjay'),
    ('Tigbao', 'Tigbao'),
    ('Zone 1', 'Zone 1'),
    ('Zone 2', 'Zone 2'),
]


class LandownerSubmissionForm(forms.ModelForm):
    """
    Form for landowners to submit ISF list.
    Public form - no authentication required.
    """
    barangay = forms.ChoiceField(
        choices=BARANGAY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    class Meta:
        model = LandownerSubmission
        fields = [
            'landowner_name',
            'landowner_phone', 
            'landowner_email',
            'property_address',
            'barangay',
        ]
        widgets = {
            'landowner_name': forms.TextInput(attrs={
                'placeholder': 'Enter your full name',
                'autofocus': True,
            }),
            'landowner_phone': forms.TextInput(attrs={
                'placeholder': '09XX XXX XXXX',
            }),
            'landowner_email': forms.EmailInput(attrs={
                'placeholder': 'email@example.com (optional)',
            }),
            'property_address': forms.Textarea(attrs={
                'placeholder': 'Complete address of the property where ISFs are residing',
                'rows': 3,
            }),
        }
        labels = {
            'landowner_name': 'Your Full Name',
            'landowner_phone': 'Contact Number',
            'landowner_email': 'Email Address (Optional)',
            'property_address': 'Property Address',
            'barangay': 'Barangay',
        }


class ISFRecordForm(forms.ModelForm):
    """
    Form for individual ISF record within a landowner submission.
    Used dynamically in the landowner form.
    """
    class Meta:
        model = ISFRecord
        fields = [
            'full_name',
            'household_members',
            'monthly_income',
            'years_residing',
            'phone_number',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'placeholder': 'Full name of head of household',
            }),
            'household_members': forms.NumberInput(attrs={
                'placeholder': 'Number of people',
                'min': 1,
                'max': 20,
            }),
            'monthly_income': forms.NumberInput(attrs={
                'placeholder': 'Monthly income in pesos',
                'min': 0,
                'step': '0.01',
            }),
            'years_residing': forms.NumberInput(attrs={
                'placeholder': 'Years on property',
                'min': 0,
                'max': 100,
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': '09XX XXX XXXX (for SMS updates)',
            }),
        }
        labels = {
            'full_name': 'Full Name',
            'household_members': 'Household Members',
            'monthly_income': 'Monthly Income (₱)',
            'years_residing': 'Years Residing',
            'phone_number': 'Contact Number (Optional)',
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
