from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model

from cases.views import (
    _CASE_LIST_DEFER,
    _DESK_ACTIVE_ROW_LIMIT,
    _DRAWER_CASE_LIST_LIMIT,
    _SETTLED_INCIDENT_ROW_LIMIT,
    _case_management_list_context,
)

User = get_user_model()


class CaseDeskListPerfGuardTests(TestCase):
    """Guards lean case-desk list context (caps + deferred text fields)."""

    def setUp(self):
        self.factory = RequestFactory()
        self.field_user = User.objects.create_user(
            username='field.desk',
            email='field.desk@example.com',
            password='tha2026',
            position='field',
        )

    def test_list_context_limits_and_defer_constants(self):
        self.assertEqual(_DESK_ACTIVE_ROW_LIMIT, 100)
        self.assertEqual(_SETTLED_INCIDENT_ROW_LIMIT, 50)
        self.assertEqual(_DRAWER_CASE_LIST_LIMIT, 50)
        self.assertIn('investigation_notes', _CASE_LIST_DEFER)
        self.assertIn('resolution_notes', _CASE_LIST_DEFER)

    def test_field_list_context_does_not_materialize_full_cases(self):
        request = self.factory.get('/field/cases/')
        request.user = self.field_user
        ctx = _case_management_list_context(request, 'field')
        self.assertEqual(ctx['cases'], [])
        self.assertLessEqual(len(ctx['desk_rows']), _DESK_ACTIVE_ROW_LIMIT)
        self.assertLessEqual(len(ctx['resolved_cases']), _DRAWER_CASE_LIST_LIMIT)
        self.assertLessEqual(len(ctx['pending_cases']), _DRAWER_CASE_LIST_LIMIT)
        self.assertLessEqual(len(ctx['settled_incident_rows']), _SETTLED_INCIDENT_ROW_LIMIT)
