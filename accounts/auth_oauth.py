"""Google OAuth configuration helpers."""

from __future__ import annotations


def google_oauth_configured() -> bool:
    """Return True when a Google SocialApp row exists in the database."""
    from allauth.socialaccount.models import SocialApp

    return SocialApp.objects.filter(provider='google').exists()
