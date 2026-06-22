"""Auth-related signal handlers."""

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .auth_portal import portal_role_for_position


def _queue_portal_role_cookie(request, role: str) -> None:
    if request is not None and role:
        request._ihsms_save_portal_role = role


@receiver(user_logged_out)
def remember_portal_role_on_logout(sender, request, user, **kwargs):
    """Admin logout flushes the session; stash portal role for the response cookie."""
    if user is None:
        return
    _queue_portal_role_cookie(request, portal_role_for_position(getattr(user, 'position', None)))


@receiver(user_logged_in)
def remember_portal_role_on_login(sender, request, user, **kwargs):
    """Fallback when login views did not already queue a portal role."""
    if request is None or getattr(request, '_ihsms_save_portal_role', None):
        return
    _queue_portal_role_cookie(request, portal_role_for_position(getattr(user, 'position', None)))
