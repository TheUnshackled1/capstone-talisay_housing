from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialLogin

from accounts.adapters import THASocialAccountAdapter, _email_allowed_domain
from accounts.auth_portal import (
    PORTAL_ROLE_SESSION_KEY,
    normalize_portal_role,
    user_allowed_for_portal,
)

User = get_user_model()


class PortalRoleHelperTests(TestCase):
    def test_normalize_caretaker_legacy(self):
        self.assertEqual(normalize_portal_role('caretaker'), 'field_desk')

    def test_second_member_portal(self):
        user = User(position='second_member')
        allowed, err = user_allowed_for_portal(user, 'second_member')
        self.assertTrue(allowed)
        self.assertIsNone(err)

    def test_wrong_portal_rejected(self):
        user = User(position='fourth_member')
        allowed, err = user_allowed_for_portal(user, 'second_member')
        self.assertFalse(allowed)
        self.assertIn('Access Denied', err)

    def test_field_desk_accepts_ronda_and_field(self):
        for pos in ('ronda', 'field'):
            user = User(position=pos)
            allowed, _ = user_allowed_for_portal(user, 'field_desk')
            self.assertTrue(allowed)

    def test_field_desk_rejects_second_member(self):
        user = User(position='second_member')
        allowed, err = user_allowed_for_portal(user, 'field_desk')
        self.assertFalse(allowed)
        self.assertIn('field desk', err.lower())

    def test_empty_portal_allows_password_login(self):
        user = User(position='second_member')
        allowed, err = user_allowed_for_portal(user, '')
        self.assertTrue(allowed)
        self.assertIsNone(err)


@override_settings(GOOGLE_OAUTH_ALLOWED_DOMAINS=('talisayhousing.gov.ph',))
class EmailDomainTests(TestCase):
    def test_allowed_domain(self):
        self.assertTrue(_email_allowed_domain('joie.tingson@talisayhousing.gov.ph'))

    def test_rejects_other_domain(self):
        self.assertFalse(_email_allowed_domain('user@gmail.com'))


@override_settings(GOOGLE_OAUTH_ALLOWED_DOMAINS=('gmail.com', 'talisayhousing.gov.ph'))
class EmailDomainGmailTests(TestCase):
    def test_gmail_allowed(self):
        self.assertTrue(_email_allowed_domain('dev.tester@gmail.com'))

    def test_tha_domain_allowed(self):
        self.assertTrue(_email_allowed_domain('joie.tingson@talisayhousing.gov.ph'))


@override_settings(GOOGLE_OAUTH_ALLOWED_DOMAINS=('talisayhousing.gov.ph',))
class THASocialAccountAdapterTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = THASocialAccountAdapter()
        self.user = User.objects.create_user(
            username='joie.tingson',
            email='joie.tingson@talisayhousing.gov.ph',
            password='tha2026',
            position='second_member',
        )

    def _request(self, session=None):
        request = self.factory.get('/auth/google/login/callback/')
        request.session = session if session is not None else {}
        setattr(request, '_messages', FallbackStorage(request))
        return request

    def _make_sociallogin(self, email='joie.tingson@talisayhousing.gov.ph', existing=False):
        sociallogin = MagicMock(spec=SocialLogin)
        sociallogin.is_existing = existing
        sociallogin.user = self.user if existing else MagicMock(email=email)
        sociallogin.account = MagicMock(extra_data={'email': email})

        def _connect(request, user):
            sociallogin.user = user

        sociallogin.connect = MagicMock(side_effect=_connect)
        return sociallogin

    def test_rejects_missing_portal_role_in_session(self):
        request = self._request()
        sociallogin = self._make_sociallogin()
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

    def test_rejects_unprovisioned_email(self):
        request = self._request(session={PORTAL_ROLE_SESSION_KEY: 'second_member'})
        sociallogin = self._make_sociallogin(email='unknown@talisayhousing.gov.ph')
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

    def test_rejects_wrong_portal(self):
        request = self._request(session={PORTAL_ROLE_SESSION_KEY: 'fourth_member'})
        sociallogin = self._make_sociallogin()
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)

    def test_allows_provisioned_user_on_correct_portal(self):
        request = self._request(session={PORTAL_ROLE_SESSION_KEY: 'second_member'})
        sociallogin = self._make_sociallogin()
        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_called_once_with(request, self.user)
        self.assertNotIn(PORTAL_ROLE_SESSION_KEY, request.session)

    def test_is_open_for_signup_false(self):
        request = self.factory.get('/')
        self.assertFalse(self.adapter.is_open_for_signup(request, MagicMock()))


class PasswordLoginTests(TestCase):
    def setUp(self):
        self.client = Client()
        User.objects.create_user(
            username='jocel.cuaysing',
            email='jocel.cuaysing@talisayhousing.gov.ph',
            password='tha2026',
            position='fourth_member',
        )

    def test_password_login_success_with_matching_portal(self):
        url = reverse('accounts:login') + '?role=fourth_member'
        response = self.client.post(url, {
            'username': 'jocel.cuaysing',
            'password': 'tha2026',
        })
        self.assertRedirects(response, reverse('accounts:dashboard'), fetch_redirect_response=False)

    def test_password_login_wrong_portal_denied(self):
        url = reverse('accounts:login') + '?role=second_member'
        response = self.client.post(url, {
            'username': 'jocel.cuaysing',
            'password': 'tha2026',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('role=second_member', response.url)


class GoogleLoginStartTests(TestCase):
    def test_stores_role_and_redirects(self):
        client = Client()
        url = reverse('accounts:google_login_start') + '?role=second_member'
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session.get(PORTAL_ROLE_SESSION_KEY), 'second_member')

    def test_rejects_missing_role(self):
        client = Client()
        response = client.get(reverse('accounts:google_login_start'))
        self.assertRedirects(response, reverse('accounts:login'), fetch_redirect_response=False)


@override_settings(DEBUG=True)
class LocalhostCanonicalizationMiddlewareTests(TestCase):
    def test_redirects_127_to_localhost(self):
        client = Client()
        response = client.get(
            reverse('accounts:login'),
            HTTP_HOST='127.0.0.1:8000',
        )
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response['Location'].startswith('http://localhost:8000/'))

    def test_localhost_not_redirected(self):
        client = Client()
        response = client.get(
            reverse('accounts:login'),
            HTTP_HOST='localhost:8000',
        )
        self.assertEqual(response.status_code, 200)

    def test_google_login_start_from_127_canonicalizes_host(self):
        client = Client()
        url = reverse('accounts:google_login_start') + '?role=second_member'
        response = client.get(url, HTTP_HOST='127.0.0.1:8000')
        self.assertEqual(response.status_code, 301)
        self.assertIn('localhost:8000', response['Location'])
