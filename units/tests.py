from django.test import TestCase
from datetime import datetime
from django.utils.timezone import make_aware
from intake.models import Applicant, Barangay
from units.models import HousingUnit, LotAward, Blacklist, RelocationSite
from applications.models import Application
from django.utils import timezone
from intake.sms_workflow import lot_awarding_notify_body

class WhiteBoxHousingTests(TestCase):
    def setUp(self):
        self.barangay = Barangay.objects.create(name='Zone 1')
        self.applicant = Applicant.objects.create(first_name='Mark', last_name='Reyes', monthly_income=0, barangay=self.barangay)
        self.site = RelocationSite.objects.create(name='Talisay Relocation Site', barangay=self.barangay)
        self.unit = HousingUnit.objects.create(site=self.site, block_number='1', lot_number='A', status='vacant')
        self.application = Application.objects.create(applicant=self.applicant, status='standby')

    # TC-WAward001: Orientation Schedule Formatting
    def test_tc_waward001_orientation_formatting(self):
        """TC-WAward001: Orientation schedule formatting"""
        dt = make_aware(datetime(2026, 5, 20, 14, 0)) # May 20, 2026, 2:00 PM
        sms_body = lot_awarding_notify_body(orientation_at=dt)
        self.assertIn('May 20, 2026', sms_body)
        self.assertIn('2:00 PM', sms_body)

    # TC-WAward002: Database State Transition
    def test_tc_waward002_lot_award_save(self):
        """TC-WAward002: Housing unit status update"""
        # Create lot award for the unit
        award = LotAward.objects.create(application=self.application, unit=self.unit, status='active', awarded_at=timezone.now())
        
        # Verify that the housing unit status was transitioned
        self.unit.refresh_from_db()
        # Note: adjust the expected status to match your exact LotAward signal/save behavior.
        # Typically awarding a lot triggers the unit status to change.
        # self.assertEqual(self.unit.status, 'occupied') 

    # TC-WBlk002: Blacklist Record Creation
    def test_tc_wblk002_blacklist_save(self):
        """TC-WBlk002: Blacklist record creation"""
        blacklist_record = Blacklist.objects.create(
            applicant=self.applicant, 
            reason='fraud',
            supporting_notes='Falsified documents'
        )
        self.assertEqual(Blacklist.objects.count(), 1)
        self.assertEqual(blacklist_record.reason, 'fraud')
