"""django-allauth adapters for THA staff Google OAuth."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AbstractUser
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import urlencode

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.models import SocialLogin

from .auth_portal import (
    PORTAL_ROLE_SESSION_KEY,
    normalize_portal_role,
    portal_role_for_oauth,
    resolve_staff_user_for_portal,
    user_allowed_for_portal,
)


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


class THAAccountAdapter(DefaultAccountAdapter):
    """Staff-only app — no public username/password signup."""

    def is_open_for_signup(self, request):
        return False


class THASocialAccountAdapter(DefaultSocialAccountAdapter):
    """Connect Google sign-in to pre-provisioned staff users only."""

    def is_open_for_signup(self, request, sociallogin):
        return False

    def authenticate_by_email(
        self, sociallogin: SocialLogin
    ) -> tuple[AbstractUser, str] | None:
        """Match Google email to the staff user for the portal selected before OAuth."""
        portal_role = portal_role_for_oauth(self.request, sociallogin)
        if not portal_role:
            return None

        emails = [e.email for e in sociallogin.email_addresses if e.verified]
        extra_email = (sociallogin.account.extra_data or {}).get('email')
        if extra_email and extra_email not in emails:
            emails.append(extra_email)

        for email in emails:
            if not self.can_authenticate_by_email(sociallogin, email):
                continue
            user, err = resolve_staff_user_for_portal(email, portal_role)
            if user is not None and err is None:
                return user, email
        return None

    def pre_social_login(self, request, sociallogin):
        portal_role = portal_role_for_oauth(request, sociallogin)

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

        user, resolve_err = resolve_staff_user_for_portal(email, portal_role)
        if resolve_err or user is None:
            messages.error(request, resolve_err or 'Unable to sign in with this Google account.')
            raise ImmediateHttpResponse(_login_redirect_with_role(portal_role))

        if sociallogin.user != user:
            sociallogin.user = user
            if not sociallogin.account.pk:
                sociallogin.connect(request, user)

        allowed, err = user_allowed_for_portal(user, portal_role)
        if not allowed:
            messages.error(request, err)
            raise ImmediateHttpResponse(_login_redirect_with_role(portal_role))

        request._ihsms_save_portal_role = portal_role
        request.session.pop(PORTAL_ROLE_SESSION_KEY, None)

    def get_login_redirect_url(self, request):
        return reverse('accounts:dashboard')
