from django.core.checks import Warning, register


@register()
def check_google_social_app(app_configs, **kwargs):
    from .auth_oauth import google_oauth_configured

    if google_oauth_configured():
        return []

    return [
        Warning(
            'Google SocialApp is not configured in the database.',
            hint='Run: python manage.py setup_google_oauth',
            id='accounts.W001',
        )
    ]
