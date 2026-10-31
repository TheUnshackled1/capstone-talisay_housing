from __future__ import annotations


def google_oauth_configured() -> bool:
    from django.db import ProgrammingError, OperationalError
    from allauth.socialaccount.models import SocialApp

    try:
        return SocialApp.objects.filter(provider='google').exists()
    except (ProgrammingError, OperationalError):
        # Table doesn't exist yet — migrations haven't run.
        return False
