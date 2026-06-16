"""django-allauth adapters for THA staff Google OAuth."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import urlencode

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .auth_portal import (
    PORTAL_ROLE_SESSION_KEY,
    normalize_portal_role,
    user_allowed_for_portal,
)

User = get_user_model()


def _login_redirect_with_role(portal_role: str):
    role = normalize_portal_role(portal_role)
    if role:
        return redirect(f"{reverse('accounts:login')}?{urlencode({'role': role})}")
    return redirect('accounts:login')


def _email_allowed_domain(email: str) -> bool:
    allowed_domains = getattr(settings, 'GOOGLE_OAUTH_ALLOWED_DOMAINS', None) or ()
    if not allowed_domains:
        return True
    email_l = (email or '').strip().lower()
    if '@' not in email_l:
        return False
    domain = email_l.rsplit('@', 1)[-1]
    return domain in allowed_domains


def _allowed_domains_display() -> str:
    domains = getattr(settings, 'GOOGLE_OAUTH_ALLOWED_DOMAINS', None) or ()
    if not domains:
        return 'any'
    return ', '.join(f'@{d}' for d in domains)


class THASocialAccountAdapter(DefaultSocialAccountAdapter):
    """Connect Google sign-in to pre-provisioned staff users only."""

    def is_open_for_signup(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        portal_role = normalize_portal_role(request.session.get(PORTAL_ROLE_SESSION_KEY))

        extra = sociallogin.account.extra_data or {}
        email = (extra.get('email') or sociallogin.user.email or '').strip()

        if not email:
            messages.error(request, 'Google did not return an email address for this account.')
            raise ImmediateHttpResponse(_login_redirect_with_role(portal_role))

        if not _email_allowed_domain(email):
            messages.error(
                request,
                f'Access denied: Google account must use one of these email domains: '
                f'{_allowed_domains_display()}.',
            )
            raise ImmediateHttpResponse(_login_redirect_with_role(portal_role))

        if not sociallogin.is_existing:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                messages.error(
                    request,
                    'This Google account is not provisioned in IHSMS. Contact your system administrator.',
                )
                raise ImmediateHttpResponse(_login_redirect_with_role(portal_role))
            sociallogin.connect(request, user)

        user = sociallogin.user
        
        if portal_role:
            allowed, err = user_allowed_for_portal(user, portal_role)
            if not allowed:
                messages.error(request, err)
                raise ImmediateHttpResponse(_login_redirect_with_role(portal_role))

        request.session.pop(PORTAL_ROLE_SESSION_KEY, None)

    def get_login_redirect_url(self, request):
        return reverse('accounts:dashboard')
