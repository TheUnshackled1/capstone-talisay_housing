from pathlib import Path
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.db import connection

from cases.views import (
    _CASE_LIST_DEFER,
    _DESK_ACTIVE_ROW_LIMIT,
    _DRAWER_CASE_LIST_LIMIT,
    _SETTLED_INCIDENT_ROW_LIMIT,
    _bump_case_desk_data_version,
    _case_desk_poll_version,
    _case_management_list_context,
    _get_case_desk_data_version,
    case_desk_feed,
)

User = get_user_model()

DESK_TEMPLATE_FILES = [
    Path('templates/field/case_desk_unified_tbody.html'),
    Path('templates/field/case_desk_mobile_cards.html'),
    Path('templates/field/case_desk_resolved_drawer_inner.html'),
    Path('templates/field/case_desk_pending_drawer_inner.html'),
    Path('templates/field/case_desk_settled_drawer_inner.html'),
    Path('templates/staff/case_management.html'),
]


class CaseDeskListPerfGuardTests(TestCase):
    """Guards lean case-desk list context (caps + deferred text fields)."""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.field_user = User.objects.create_user(
            username='field.desk',
            email='field.desk@example.com',
            password='tha2026',
            position='field',
        )
        self.ronda_user = User.objects.create_user(
            username='ronda.desk',
            email='ronda.desk@example.com',
            password='tha2026',
            position='ronda',
        )

    def test_list_context_limits_and_defer_constants(self):
        self.assertEqual(_DESK_ACTIVE_ROW_LIMIT, 25)
        self.assertEqual(_SETTLED_INCIDENT_ROW_LIMIT, 50)
        self.assertEqual(_DRAWER_CASE_LIST_LIMIT, 50)
        self.assertIn('investigation_notes', _CASE_LIST_DEFER)
        self.assertIn('resolution_notes', _CASE_LIST_DEFER)

    def test_field_list_context_does_not_materialize_full_cases(self):
        request = self.factory.get('/field/cases/')
        request.user = self.field_user
        ctx = _case_management_list_context(request, 'field', include_drawer_rows=False)
        self.assertEqual(ctx['cases'], [])
        self.assertLessEqual(len(ctx['desk_rows']), _DESK_ACTIVE_ROW_LIMIT)
        self.assertEqual(ctx['resolved_cases'], [])
        self.assertEqual(ctx['pending_cases'], [])
        self.assertEqual(ctx['settled_incident_rows'], [])

    def test_field_skips_pending_even_with_drawers(self):
        request = self.factory.get('/field/cases/')
        request.user = self.field_user
        ctx = _case_management_list_context(request, 'field', include_drawer_rows=True)
        self.assertEqual(ctx['pending_cases'], [])
        self.assertLessEqual(len(ctx['resolved_cases']), _DRAWER_CASE_LIST_LIMIT)
        self.assertLessEqual(len(ctx['settled_incident_rows']), _SETTLED_INCIDENT_ROW_LIMIT)

    def test_desk_templates_never_use_active_unit_label(self):
        for path in DESK_TEMPLATE_FILES:
            text = path.read_text(encoding='utf-8')
            self.assertNotIn(
                'active_unit_label',
                text,
                msg=f'{path} still references active_unit_label (N+1 risk)',
            )

    def test_desk_feed_unchanged_skips_heavy_work(self):
        request = self.factory.get('/cases/ronda/desk-feed/')
        request.user = self.ronda_user
        version = _case_desk_poll_version(request)
        feed_req = self.factory.get(
            '/cases/ronda/desk-feed/',
            {'v': version},
        )
        feed_req.user = self.ronda_user
        with CaptureQueriesContext(connection) as ctx:
            response = case_desk_feed(feed_req, 'ronda')
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertTrue(payload.get('unchanged'))
        self.assertEqual(payload.get('version'), version)
        # Unchanged path: version stamp cache get (+ maybe auth session) only.
        self.assertLessEqual(len(ctx), 5)

    def test_bump_invalidates_poll_version(self):
        request = self.factory.get('/cases/field/desk-feed/')
        request.user = self.field_user
        before = _get_case_desk_data_version()
        _bump_case_desk_data_version()
        after = _get_case_desk_data_version()
        self.assertNotEqual(before, after)

    def test_field_page_query_budget_cold(self):
        client = Client()
        client.force_login(self.field_user)
        cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = client.get('/field/cases/')
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(
            len(ctx),
            40,
            msg=f'Cold /field/cases/ ran {len(ctx)} queries (budget 40)',
        )
