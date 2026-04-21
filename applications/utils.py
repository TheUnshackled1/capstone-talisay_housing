"""
Module 2 utility helpers.
"""

from .models import BlacklistProxy


def check_blacklist_module2(full_name, phone_number=None):
    """
    Module 2 automatic blacklist gate (workflow step 2.1).

    Returns:
        tuple[bool, BlacklistProxy | None]
    """
    full_name = (full_name or '').strip()
    phone_number = (phone_number or '').strip()

    if full_name:
        name_match = BlacklistProxy.objects.filter(
            full_name__icontains=full_name,
        ).first()
        if name_match:
            return True, name_match

    if phone_number:
        phone_match = BlacklistProxy.objects.filter(
            phone_number=phone_number,
        ).first()
        if phone_match:
            return True, phone_match

    return False, None
