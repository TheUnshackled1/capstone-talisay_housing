"""Staff login portal role helpers (password + Google OAuth)."""

from __future__ import annotations

from .models import FIELD_DESK_POSITIONS

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
