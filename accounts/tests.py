from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialLogin

from accounts.adapters import THASocialAccountAdapter, _email_allowed_domain
from accounts.auth_portal import (
    LAST_PORTAL_ROLE_COOKIE,
    PORTAL_ROLE_SESSION_KEY,
    normalize_portal_role,
    portal_role_for_oauth,
    portal_role_for_position,
    resolve_login_portal_role,
    resolve_staff_user_for_portal,
    user_allowed_for_portal,
)

User = get_user_model()


class PortalRoleHelperTests(TestCase):
    def test_normalize_caretaker_legacy(self):
        self.assertEqual(normalize_portal_role('caretaker'), 'field_desk')

    def test_normalize_ronda_and_field_to_field_desk(self):
        self.assertEqual(normalize_portal_role('ronda'), 'field_desk')
        self.assertEqual(normalize_portal_role('field'), 'field_desk')

    def test_portal_role_for_oauth_prefers_oauth_state_over_session(self):
        factory = RequestFactory()
        request = factory.get('/auth/google/login/callback/')
        request.session = {PORTAL_ROLE_SESSION_KEY: 'fourth_member'}
        sociallogin = MagicMock(spec=SocialLogin)
        sociallogin.state = {'portal_role': 'second_member'}
        self.assertEqual(portal_role_for_oauth(request, sociallogin), 'second_member')

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


class ResolveStaffUserTests(TestCase):
    shared_email = 'bivosomeryl@gmail.com'

    @classmethod
    def setUpTestData(cls):
        cls.second_member = User.objects.create_user(
            username='lourynie.tingson',
            email=cls.shared_email,
            password='tha2026',
            position='second_member',
        )
        cls.fourth_member = User.objects.create_user(
            username='jocel.cuaysing',
            email=cls.shared_email,
            password='tha2026',
            position='fourth_member',
        )
        cls.ronda = User.objects.create_user(
            username='nonoy.cura',
            email=cls.shared_email,
            password='tha2026',
            position='ronda',
        )

    def test_resolves_second_member_portal(self):
        user, err = resolve_staff_user_for_portal(self.shared_email, 'second_member')
        self.assertIsNone(err)
        self.assertEqual(user, self.second_member)

    def test_resolves_fourth_member_portal(self):
        user, err = resolve_staff_user_for_portal(self.shared_email, 'fourth_member')
        self.assertIsNone(err)
        self.assertEqual(user, self.fourth_member)

    def test_resolves_ronda_portal_alias(self):
        user, err = resolve_staff_user_for_portal(self.shared_email, 'ronda')
        self.assertIsNone(err)
        self.assertEqual(user, self.ronda)

    def test_resolves_field_portal_alias_for_field_staff(self):
        field_user = User.objects.create_user(
            username='field.staff',
            email='field.only@gmail.com',
            password='tha2026',
            position='field',
        )
        user, err = resolve_staff_user_for_portal('field.only@gmail.com', 'field')
        self.assertIsNone(err)
        self.assertEqual(user, field_user)

    def test_resolves_field_desk_portal_for_ronda(self):
        user, err = resolve_staff_user_for_portal(self.shared_email, 'field_desk')
        self.assertIsNone(err)
        self.assertEqual(user, self.ronda)

    def test_requires_portal_role(self):
        user, err = resolve_staff_user_for_portal(self.shared_email, '')
        self.assertIsNone(user)
        self.assertIn('portal', err.lower())

    def test_finds_user_via_emailaddress_only(self):
        other_email = 'meryl.bivoso@chmsu.edu.ph'
        user = User.objects.create_user(
            username='joie.chmsu',
            email='joie.tingson@talisayhousing.gov.ph',
            password='tha2026',
            position='second_member',
        )
        EmailAddress.objects.create(user=user, email=other_email, verified=False, primary=False)
        resolved, err = resolve_staff_user_for_portal(other_email, 'second_member')
        self.assertIsNone(err)
        self.assertEqual(resolved, user)

    def test_ignores_inactive_user_for_email(self):
        inactive_email = 'inactive.staff@talisayhousing.gov.ph'
        User.objects.create_user(
            username='inactive.staff',
            email=inactive_email,
            password='tha2026',
            position='second_member',
            is_active=False,
        )
        resolved, err = resolve_staff_user_for_portal(inactive_email, 'second_member')
        self.assertIsNone(resolved)
        self.assertIn('not provisioned', err.lower())


@override_settings(GOOGLE_OAUTH_ALLOWED_DOMAINS=('talisayhousing.gov.ph',))
class EmailDomainTests(TestCase):
    def test_allowed_domain(self):
        self.assertTrue(_email_allowed_domain('joie.tingson@talisayhousing.gov.ph'))

    def test_rejects_other_domain(self):
        self.assertFalse(_email_allowed_domain('user@gmail.com'))


@override_settings(GOOGLE_OAUTH_ALLOWED_DOMAINS=('gmail.com', 'talisayhousing.gov.ph', 'chmsu.edu.ph'))
class EmailDomainGmailTests(TestCase):
    def test_gmail_allowed(self):
        self.assertTrue(_email_allowed_domain('dev.tester@gmail.com'))

    def test_tha_domain_allowed(self):
        self.assertTrue(_email_allowed_domain('joie.tingson@talisayhousing.gov.ph'))

    def test_chmsu_domain_allowed(self):
        self.assertTrue(_email_allowed_domain('meryl.bivoso@chmsu.edu.ph'))


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

    def _make_sociallogin(
        self,
        email='joie.tingson@talisayhousing.gov.ph',
        existing=False,
        user=None,
        social_account_pk=None,
        portal_role=None,
    ):
        sociallogin = MagicMock(spec=SocialLogin)
        sociallogin.is_existing = existing
        sociallogin.user = user if user is not None else (
            self.user if existing else MagicMock(email=email)
        )
        sociallogin.account = MagicMock(extra_data={'email': email})
        sociallogin.account.pk = social_account_pk
        sociallogin.state = {'portal_role': portal_role} if portal_role else {}

        def _connect(request, connect_user):
            sociallogin.user = connect_user

        sociallogin.account.save = MagicMock()
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
        sociallogin = self._make_sociallogin(portal_role='second_member')
        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_called_once_with(request, self.user)
        self.assertNotIn(PORTAL_ROLE_SESSION_KEY, request.session)

    def test_is_open_for_signup_false(self):
        request = self.factory.get('/')
        self.assertFalse(self.adapter.is_open_for_signup(request, MagicMock()))


@override_settings(GOOGLE_OAUTH_ALLOWED_DOMAINS=('gmail.com',))
class SharedEmailOAuthTests(TestCase):
    shared_email = 'bivosomeryl@gmail.com'

    @classmethod
    def setUpTestData(cls):
        cls.second_member = User.objects.create_user(
            username='lourynie.tingson',
            email=cls.shared_email,
            password='tha2026',
            position='second_member',
        )
        cls.fourth_member = User.objects.create_user(
            username='jocel.cuaysing',
            email=cls.shared_email,
            password='tha2026',
            position='fourth_member',
        )
        cls.ronda = User.objects.create_user(
            username='nonoy.cura',
            email=cls.shared_email,
            password='tha2026',
            position='ronda',
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = THASocialAccountAdapter()

    def _request(self, portal_role):
        request = self.factory.get('/auth/google/login/callback/')
        request.session = {PORTAL_ROLE_SESSION_KEY: portal_role}
        setattr(request, '_messages', FallbackStorage(request))
        return request

    def _make_sociallogin(self, linked_user=None, social_account_pk=None, portal_role=None):
        sociallogin = MagicMock(spec=SocialLogin)
        sociallogin.is_existing = linked_user is not None
        sociallogin.user = linked_user or MagicMock(email=self.shared_email)
        sociallogin.account = MagicMock(extra_data={'email': self.shared_email})
        sociallogin.account.pk = social_account_pk
        sociallogin.account.save = MagicMock()
        sociallogin.state = {'portal_role': portal_role} if portal_role else {}

        def _connect(request, user):
            sociallogin.user = user

        sociallogin.connect = MagicMock(side_effect=_connect)
        return sociallogin

    def test_oauth_second_member_portal(self):
        request = self._request('fourth_member')
        sociallogin = self._make_sociallogin(portal_role='second_member')
        self.adapter.pre_social_login(request, sociallogin)
        self.assertEqual(sociallogin.user, self.second_member)
        sociallogin.connect.assert_called_once_with(request, self.second_member)

    def test_oauth_second_member_portal_session_fallback(self):
        request = self._request('second_member')
        sociallogin = self._make_sociallogin()
        self.adapter.pre_social_login(request, sociallogin)
        self.assertEqual(sociallogin.user, self.second_member)
        sociallogin.connect.assert_called_once_with(request, self.second_member)

    def test_oauth_fourth_member_portal(self):
        request = self._request('fourth_member')
        sociallogin = self._make_sociallogin()
        self.adapter.pre_social_login(request, sociallogin)
        self.assertEqual(sociallogin.user, self.fourth_member)

    def test_oauth_ronda_portal_alias(self):
        request = self._request('ronda')
        sociallogin = self._make_sociallogin(portal_role='ronda')
        self.adapter.pre_social_login(request, sociallogin)
        self.assertEqual(sociallogin.user, self.ronda)

    def test_existing_social_account_logs_in_portal_user_without_db_rebind(self):
        """Regression: Google linked to Ronda, login via Second Member portal."""
        request = self._request('fourth_member')
        sociallogin = self._make_sociallogin(
            linked_user=self.ronda,
            social_account_pk=42,
            portal_role='second_member',
        )
        self.adapter.pre_social_login(request, sociallogin)
        self.assertEqual(sociallogin.user, self.second_member)
        sociallogin.account.save.assert_not_called()
        sociallogin.connect.assert_not_called()

    def test_authenticate_by_email_respects_portal(self):
        request = self._request('fourth_member')
        self.adapter.request = request
        sociallogin = MagicMock(spec=SocialLogin)
        sociallogin.email_addresses = []
        sociallogin.account = MagicMock(extra_data={'email': self.shared_email})
        sociallogin.provider = MagicMock()
        sociallogin.state = {'portal_role': 'fourth_member'}
        with self.settings(SOCIALACCOUNT_EMAIL_AUTHENTICATION=True):
            result = self.adapter.authenticate_by_email(sociallogin)
        self.assertIsNotNone(result)
        user, email = result
        self.assertEqual(user, self.fourth_member)
        self.assertEqual(email, self.shared_email)


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

    def test_password_login_rejects_external_next_redirect(self):
        url = (
            reverse('accounts:login')
            + '?role=fourth_member&next=https://evil.example/phish'
        )
        response = self.client.post(url, {
            'username': 'jocel.cuaysing',
            'password': 'tha2026',
        })
        self.assertRedirects(
            response,
            reverse('accounts:dashboard'),
            fetch_redirect_response=False,
        )


class GoogleLoginStartTests(TestCase):
    def setUp(self):
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site

        site = Site.objects.get_current()
        self.social_app = SocialApp.objects.create(
            provider='google',
            name='Google',
            client_id='test-client-id',
            secret='test-secret',
        )
        self.social_app.sites.add(site)

    def test_redirects_to_google_with_portal_role_query(self):
        client = Client()
        url = reverse('accounts:google_login_start') + '?role=second_member'
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('portal_role=second_member', response.url)
        self.assertIn('/auth/google/login/', response.url)

    def test_rejects_missing_role(self):
        client = Client()
        response = client.get(reverse('accounts:google_login_start'))
        self.assertRedirects(response, reverse('accounts:login'), fetch_redirect_response=False)


class GoogleOAuthViewTests(TestCase):
    def test_tha_google_oauth_login_without_social_app_redirects_to_login(self):
        client = Client()
        url = reverse('google_login') + '?portal_role=second_member'
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('role=second_member', response.url)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_google_login_start_without_social_app_redirects_to_login(self):
        client = Client()
        url = reverse('accounts:google_login_start') + '?role=second_member'
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('role=second_member', response.url)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_tha_google_oauth_login_with_social_app_redirects_to_google(self):
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site

        site = Site.objects.get_current()
        app = SocialApp.objects.create(
            provider='google',
            name='Google',
            client_id='test-client-id',
            secret='test-secret',
        )
        app.sites.add(site)

        client = Client()
        url = reverse('google_login') + '?portal_role=second_member'
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts.google.com', response.url)


class LoginPortalPersistenceTests(TestCase):
    def test_login_restores_role_from_cookie_without_query_param(self):
        client = Client()
        client.cookies[LAST_PORTAL_ROLE_COOKIE] = 'second_member'
        response = client.get(reverse('accounts:login') + '?next=/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Second Member')
        self.assertContains(response, 'Sign in with Google')

    def test_logout_redirects_to_portal_login(self):
        user = User.objects.create_user(
            username='lourynie.tingson',
            email='joie@talisayhousing.gov.ph',
            password='tha2026',
            position='second_member',
        )
        client = Client()
        client.login(username='lourynie.tingson', password='tha2026')
        response = client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('role=second_member', response.url)

    def test_portal_role_for_position_maps_field_staff(self):
        self.assertEqual(portal_role_for_position('ronda'), 'field_desk')
        self.assertEqual(portal_role_for_position('second_member'), 'second_member')


class SignupDisabledTests(TestCase):
    def test_signup_page_not_available(self):
        client = Client()
        response = client.get('/auth/signup/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sign Up Closed', response.content)


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
