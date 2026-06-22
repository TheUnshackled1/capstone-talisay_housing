"""Staff login portal role helpers (password + Google OAuth)."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from allauth.account.models import EmailAddress

from .models import FIELD_DESK_POSITIONS

User = get_user_model()

PORTAL_ROLE_SESSION_KEY = 'login_portal_role'

PORTAL_ROLE_DISPLAY = {
    'second_member': 'Second Member',
    'fourth_member': 'Fourth Member',
    'ronda': 'Ronda / Field Personnel',
    'field': 'Field Personnel',
    'field_desk': 'Field verification desk',
}


def normalize_portal_role(role: str | None) -> str:
    """Normalize legacy portal role query values."""
    value = (role or '').strip()
    if value == 'caretaker':
        return 'field_desk'
    return value


def portal_role_display(role: str | None) -> str | None:
    normalized = normalize_portal_role(role)
    if not normalized:
        return None
    return PORTAL_ROLE_DISPLAY.get(normalized)


def user_allowed_for_portal(user, portal_role: str | None) -> tuple[bool, str | None]:
    """
    Return (allowed, error_message).

    When portal_role is empty, password login keeps legacy behavior (no portal gate).
    Google OAuth requires a portal role before starting the flow.
    """
    role = normalize_portal_role(portal_role)
    if not role:
        return True, None

    if role == 'field_desk':
        if user.position not in FIELD_DESK_POSITIONS:
            return False, (
                'Access denied: this portal is only for field desk staff (Ronda or Field).'
            )
        return True, None

    if user.position != role:
        expected = portal_role_display(role) or role
        actual = user.get_position_display() or user.position or 'Staff'
        return False, (
            f'Access Denied: Your account is registered as {actual}, '
            f'not {expected}. Please use the correct login portal for your position.'
        )

    return True, None


def _users_for_email(email: str):
    """All staff users linked to an email via User.email or allauth EmailAddress."""
    email_l = (email or '').strip().lower()
    if not email_l:
        return User.objects.none()

    user_ids = set(
        User.objects.filter(email__iexact=email_l).values_list('pk', flat=True)
    )
    user_ids.update(
        EmailAddress.objects.filter(email__iexact=email_l).values_list('user_id', flat=True)
    )
    return User.objects.filter(pk__in=user_ids)


def resolve_staff_user_for_portal(email: str, portal_role: str | None):
    """
    Resolve a single staff user for Google OAuth when email may be shared across portals.

    Returns (user, None) on success or (None, error_message) on failure.
    """
    role = normalize_portal_role(portal_role)
    if not role:
        return None, 'Select your staff portal before signing in with Google.'

    candidates = _users_for_email(email)
    if not candidates.exists():
        return None, (
            'This Google account is not provisioned in IHSMS. '
            'Contact your system administrator.'
        )

    if role == 'field_desk':
        matched = candidates.filter(position__in=FIELD_DESK_POSITIONS)
    else:
        matched = candidates.filter(position=role)

    count = matched.count()
    if count == 0:
        expected = portal_role_display(role) or role
        return None, (
            f'No staff account for this Google email on the {expected} portal. '
            f'Use the login page that matches your position.'
        )
    if count > 1:
        return None, (
            'Multiple staff accounts match this email for the selected portal. '
            'Contact your system administrator.'
        )

    return matched.first(), None
