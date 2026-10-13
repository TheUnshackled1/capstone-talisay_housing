"""Google OAuth configuration helpers."""

from __future__ import annotations


def google_oauth_configured() -> bool:
    """Return True when a Google SocialApp row exists in the database.

    Returns False if the table doesn't exist yet (e.g. before migrations run
    on a fresh / just-created database) so that ``migrate`` can run without
    crashing on startup checks.
    """
    from django.db import ProgrammingError, OperationalError
    from allauth.socialaccount.models import SocialApp

    try:
        return SocialApp.objects.filter(provider='google').exists()
    except (ProgrammingError, OperationalError):
        # Table doesn't exist yet — migrations haven't run.
        return False
