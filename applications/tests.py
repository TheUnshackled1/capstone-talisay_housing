from django.test import TestCase
from intake.models import Applicant, Barangay
from intake.sms_workflow import message_ready_for_form_queue_reminder
from applications.form_pipeline import applicant_has_signed_application_payload

class WhiteBoxFormQueueTests(TestCase):
    def setUp(self):
        self.barangay = Barangay.objects.create(name='Zone 1')
        self.applicant = Applicant.objects.create(
            first_name='Jane',
            last_name='Doe',
            reference_number='THA-2026-002',
            monthly_income=0,
            barangay=self.barangay
        )

    # TC-WForm001: Form Progression Block
    def test_tc_wform001_signed_application_validation(self):
        """TC-WForm001: Form progression block validation (Missing signed form)"""
        # Applicant has no documents uploaded in setUp
        has_signed_form = applicant_has_signed_application_payload(self.applicant)
        self.assertFalse(has_signed_form, "Should return False when doc_signed_application is missing")

    # TC-WForm002: Form Queue SMS
    def test_tc_wform002_form_queue_reminder_sms(self):
        """TC-WForm002: Form queue SMS trigger"""
        sms_message = message_ready_for_form_queue_reminder(self.applicant, base_url='http://test.com')
        self.assertIn('Form Generation', sms_message)
        self.assertIn('THA-2026-002', sms_message)
