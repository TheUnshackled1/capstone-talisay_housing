from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom user model for THA staff.
    Extends Django's AbstractUser with position and contact info.
    """
    
    POSITION_CHOICES = [
        ('head', 'First Member — Head'),
        ('oic', 'OIC-THA (Officer-in-Charge)'),
        ('second_member', 'Second Member'),
        ('fourth_member', 'Fourth Member'),
        ('fifth_member', 'Fifth Member'),
        ('caretaker', 'Caretaker'),
        ('ronda', 'Ronda (Field Personnel)'),
        ('field', 'Field Personnel'),
    ]
    
    position = models.CharField(
        max_length=50,
        choices=POSITION_CHOICES,
        blank=True,
        help_text="Staff position in THA organizational structure"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number"
    )
    
    class Meta:
        verbose_name = 'Staff User'
        verbose_name_plural = 'Staff Users'
    
    def __str__(self):
        if self.get_full_name():
            return f"{self.get_full_name()} ({self.get_position_display() or 'Staff'})"
        return self.username
    
    def get_position_display_short(self):
        """Return a shorter position label for UI display."""
        short_labels = {
            'head': 'Head',
            'oic': 'OIC',
            'second_member': '2nd Member',
            'fourth_member': '4th Member',
            'fifth_member': '5th Member',
            'caretaker': 'Caretaker',
            'ronda': 'Ronda',
            'field': 'Field',
        }
        return short_labels.get(self.position, 'Staff')
