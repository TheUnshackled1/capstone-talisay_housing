"""
Management command to test all analytics views and verify data flow.
Usage: python manage.py test_analytics
"""
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from intake.models import Applicant
from applications.models import Application
from documents.models import SignatoryRouting, ElectricityConnection
from units.models import HousingUnit, ComplianceNotice
from cases.models import Case

User = get_user_model()


class Command(BaseCommand):
    help = 'Test all Module 6 Analytics views for proper data rendering'

    def add_arguments(self, parser):
        parser.add_argument('--verbose', action='store_true', help='Show detailed output')

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        self.stdout.write(self.style.SUCCESS('STARTING ANALYTICS VERIFICATION\n'))

        # Dictionary of views to test
        analytics_views = {
            'head': {
                'position': 'head',
                'url_name': 'accounts:head_analytics',
                'required_context': [
                    'total_applicants', 'pending_count', 'housing_units',
                    'approved_this_month', 'occupancy_rate', 'open_cases'
                ]
            },
            'oic': {
                'position': 'oic',
                'url_name': 'accounts:oic_analytics',
                'required_context': [
                    'pending_signatures', 'open_cases', 'compliance_decisions',
                    'apps_signed', 'cases_resolved'
                ]
            },
            'second_member': {
                'position': 'second_member',
                'url_name': 'accounts:second_member_analytics',
                'required_context': [
                    'pending_notices', 'electricity_pending', 'total_applications',
                    'notices_issued'
                ]
            },
            'fourth_member': {
                'position': 'fourth_member',
                'url_name': 'accounts:fourth_member_analytics',
                'required_context': [
                    'priority_queue', 'documents_filed', 'lot_awards',
                    'custodian_items'
                ]
            },
            'fifth_member': {
                'position': 'fifth_member',
                'url_name': 'accounts:fifth_member_analytics',
                'required_context': [
                    'electricity_pending', 'electricity_completed',
                    'electricity_processing', 'processed'
                ]
            },
            'caretaker': {
                'position': 'caretaker',
                'url_name': 'accounts:caretaker_analytics',
                'required_context': [
                    'occupied', 'vacant', 'occupancy_rate',
                    'issues', 'maintenance_alerts'
                ]
            },
            'field': {
                'position': 'field',
                'url_name': 'accounts:field_analytics',
                'required_context': [
                    'occupied_visited', 'open_investigations', 'escalated',
                    'open_cases', 'compliant_units'
                ]
            },
        }

        # Database statistics
        self.stdout.write(self.style.HTTP_INFO('\nDATABASE STATISTICS'))
        self.stdout.write(f"  • Applicants: {Applicant.objects.count()}")
        self.stdout.write(f"  • Applications: {Application.objects.count()}")
        self.stdout.write(f"  • Housing Units: {HousingUnit.objects.count()}")
        self.stdout.write(f"  • Compliance Notices: {ComplianceNotice.objects.count()}")
        self.stdout.write(f"  • Cases: {Case.objects.count()}")
        self.stdout.write(f"  • Signatory Routings: {SignatoryRouting.objects.count()}")

        # Test each analytics view
        passed = 0
        failed = 0
        errors = []

        for role, view_config in analytics_views.items():
            self.stdout.write(f"\n{'='*70}")
            self.stdout.write(self.style.HTTP_INFO(f"Testing {role.upper()} Analytics View"))
            self.stdout.write(f"{'='*70}")

            try:
                # Create or get test user
                user, created = User.objects.get_or_create(
                    username=f'test_{role}',
                    defaults={'position': view_config['position']}
                )
                if not created:
                    user.position = view_config['position']
                    user.save()

                # Create client and login
                client = Client()
                client.force_login(user)

                # Get URL
                try:
                    url = reverse(view_config['url_name'])
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  [X] URL ROUTE FAILED: {str(e)}")
                    )
                    failed += 1
                    errors.append((role, f"URL route error: {str(e)}"))
                    continue

                # Make request
                response = client.get(url)

                # Check response status
                if response.status_code == 200:
                    self.stdout.write(
                        self.style.SUCCESS(f"  [+] HTTP 200 OK")
                    )
                elif response.status_code == 302:
                    self.stdout.write(
                        self.style.WARNING(f"  [!] REDIRECT (302) - Access Control?")
                    )
                    failed += 1
                    errors.append((role, "Redirected - possible access control issue"))
                    continue
                else:
                    self.stdout.write(
                        self.style.ERROR(f"  [X] HTTP {response.status_code}")
                    )
                    failed += 1
                    errors.append((role, f"HTTP {response.status_code}"))
                    continue

                # Check context variables
                missing_context = []
                for ctx_var in view_config['required_context']:
                    if ctx_var not in response.context:
                        missing_context.append(ctx_var)

                if missing_context:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  [!] MISSING CONTEXT VARS: {', '.join(missing_context)}"
                        )
                    )
                    failed += 1
                    errors.append((role, f"Missing: {', '.join(missing_context)}"))
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"  [+] All {len(view_config['required_context'])} context vars present")
                    )
                    passed += 1

                # Show context values if verbose
                if verbose and response.context:
                    self.stdout.write(f"\n  Context Variables:")
                    for key, value in response.context.items():
                        if not key.startswith('_'):
                            if isinstance(value, (int, float, str, bool, type(None))):
                                self.stdout.write(f"    {key}: {value}")
                            else:
                                self.stdout.write(f"    {key}: {type(value).__name__}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ EXCEPTION: {str(e)}")
                )
                failed += 1
                errors.append((role, str(e)))

        # Summary
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(self.style.HTTP_INFO('TEST SUMMARY'))
        self.stdout.write(f"{'='*70}")
        self.stdout.write(self.style.SUCCESS(f"  [+] Passed: {passed}/{len(analytics_views)}"))
        if failed > 0:
            self.stdout.write(self.style.ERROR(f"  [X] Failed: {failed}/{len(analytics_views)}"))
            self.stdout.write(self.style.ERROR('\n  ERROR DETAILS:'))
            for role, error in errors:
                self.stdout.write(self.style.ERROR(f"    * {role}: {error}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n  ALL TESTS PASSED!"))

        self.stdout.write(f"\n{'='*70}\n")
