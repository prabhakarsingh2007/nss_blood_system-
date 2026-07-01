from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from donors.models import DonorProfile
from requests.models import BloodRequest

class CoordinatorApprovalCooldownTests(TestCase):
    def setUp(self):
        # Create admin user
        self.admin_user = User.objects.create_superuser(username="admin_coord", password="adminpassword")
        
        # Create two donor users
        self.user_cooldown = User.objects.create_user(username="donor_cooldown", password="password")
        self.user_available = User.objects.create_user(username="donor_available", password="password")
        
        # Donor in cooldown (donated 10 days ago)
        self.donor_cooldown = DonorProfile.objects.create(
            user=self.user_cooldown,
            full_name="Donor Cooldown",
            blood_group="B+",
            age=30,
            phone="9999988888",
            city="Patna",
            verification_status="APPROVED",
            otp_verified=True,
            available=True,
            last_donation_date=timezone.localdate() - timedelta(days=10)
        )
        
        # Donor NOT in cooldown (donated 95 days ago)
        self.donor_available = DonorProfile.objects.create(
            user=self.user_available,
            full_name="Donor Available",
            blood_group="B+",
            age=30,
            phone="9999977777",
            city="Patna",
            verification_status="APPROVED",
            otp_verified=True,
            available=True,
            last_donation_date=timezone.localdate() - timedelta(days=95)
        )

    def test_admin_request_approval_cooldown_filter(self):
        # Create a pending request matching B+ in Patna
        req = BloodRequest.objects.create(
            requester_name="Test Patient",
            blood_group="B+",
            units=2,
            hospital_name="Patna Hospital",
            city="Patna",
            contact_number="9988776655",
            reason="Accident",
            priority="URGENT",
            otp_verified=True,
            status="PENDING"
        )
        
        # Login admin coordinator
        self.client.login(username="admin_coord", password="adminpassword")
        
        # POST request to approve the blood request
        response = self.client.post(
            reverse("admin_dashboard"),
            {
                "action": "request_status",
                "request_id": req.pk,
                "status": "APPROVED",
                "blood_bank": "City Central Blood Bank"
            }
        )
        self.assertEqual(response.status_code, 302)
        
        req.refresh_from_db()
        self.assertEqual(req.status, "ASSIGNED")
        self.assertEqual(req.blood_bank, "City Central Blood Bank")
        # Check that the assigned donor is donor_available, NOT donor_cooldown!
        self.assertEqual(req.assigned_donor, self.donor_available)


from requests.models import Hospital

class HospitalManagementTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username="admin_coord", password="adminpassword")
        self.hospital = Hospital.objects.create(
            name="Apex Clinic",
            city="Patna",
            address="Kankarbagh, Patna",
            is_active=True
        )
        self.client.login(username="admin_coord", password="adminpassword")

    def test_hospital_create(self):
        response = self.client.post(
            reverse("admin_dashboard"),
            {
                "action": "hospital_create",
                "name": "Nalanda Medical College",
                "city": "Patna",
                "address": "NMCH Patna",
                "is_active": "on"
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Hospital.objects.filter(name="Nalanda Medical College").exists())

    def test_hospital_update(self):
        response = self.client.post(
            reverse("admin_dashboard"),
            {
                "action": "hospital_update",
                "hospital_id": self.hospital.pk,
                "name": "Apex Clinic Updated",
                "city": "Gaya",
                "address": "Gaya Bypass",
                "is_active": "on"
            }
        )
        self.assertEqual(response.status_code, 302)
        self.hospital.refresh_from_db()
        self.assertEqual(self.hospital.name, "Apex Clinic Updated")
        self.assertEqual(self.hospital.city, "Gaya")

    def test_hospital_toggle(self):
        response = self.client.post(
            reverse("admin_dashboard"),
            {
                "action": "hospital_toggle",
                "hospital_id": self.hospital.pk
            }
        )
        self.assertEqual(response.status_code, 302)
        self.hospital.refresh_from_db()
        self.assertFalse(self.hospital.is_active)


class DashboardDateFilterTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username="admin_coord", password="adminpassword")
        self.client.login(username="admin_coord", password="adminpassword")

        # Create user + donor profile
        self.user = User.objects.create_user(username="donor1", password="password")
        self.donor = DonorProfile.objects.create(
            user=self.user,
            full_name="Donor One",
            blood_group="O+",
            age=25,
            phone="9999911111",
            city="Patna",
            verification_status="APPROVED",
            otp_verified=True,
            available=True
        )
        DonorProfile.objects.filter(pk=self.donor.pk).update(created_at=timezone.now() - timedelta(days=5))

        # Create blood requests
        self.request1 = BloodRequest.objects.create(
            requester_name="Patient One",
            blood_group="O+",
            units=1,
            hospital_name="Patna Hospital",
            city="Patna",
            contact_number="9999900000",
            otp_verified=True,
            status="PENDING"
        )
        BloodRequest.objects.filter(pk=self.request1.pk).update(requested_at=timezone.now() - timedelta(days=5))

        self.request2 = BloodRequest.objects.create(
            requester_name="Patient Two",
            blood_group="O+",
            units=2,
            hospital_name="Patna Hospital",
            city="Patna",
            contact_number="9999900002",
            otp_verified=True,
            status="PENDING"
        )

    def test_date_range_filter(self):
        today_str = timezone.localdate().strftime("%Y-%m-%d")
        past_str = (timezone.localdate() - timedelta(days=6)).strftime("%Y-%m-%d")
        three_days_ago_str = (timezone.localdate() - timedelta(days=3)).strftime("%Y-%m-%d")

        # Filter from 6 days ago to 3 days ago (should include request1/donor, exclude request2)
        response = self.client.get(
            reverse("admin_dashboard"),
            {
                "start_date": past_str,
                "end_date": three_days_ago_str
            }
        )
        self.assertEqual(response.status_code, 200)
        requests = response.context["requests"]
        self.assertTrue(any(r.pk == self.request1.pk for r in requests))
        self.assertFalse(any(r.pk == self.request2.pk for r in requests))


from requests.models import BloodBank

class BloodBankManagementTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username="admin_coord", password="adminpassword")
        self.bank = BloodBank.objects.create(
            name="City Blood Center",
            city="Patna",
            address="Gandhi Maidan, Patna",
            is_active=True
        )
        self.client.login(username="admin_coord", password="adminpassword")

    def test_blood_bank_create(self):
        response = self.client.post(
            reverse("admin_dashboard"),
            {
                "action": "blood_bank_create",
                "name": "NSS Central Blood Bank",
                "city": "Patna",
                "address": "NSS Office, Patna",
                "is_active": "on"
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BloodBank.objects.filter(name="NSS Central Blood Bank").exists())

    def test_blood_bank_update(self):
        response = self.client.post(
            reverse("admin_dashboard"),
            {
                "action": "blood_bank_update",
                "blood_bank_id": self.bank.pk,
                "name": "City Blood Center Updated",
                "city": "Gaya",
                "address": "Gaya Circle",
                "is_active": "on"
            }
        )
        self.assertEqual(response.status_code, 302)
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.name, "City Blood Center Updated")
        self.assertEqual(self.bank.city, "Gaya")

    def test_blood_bank_toggle(self):
        response = self.client.post(
            reverse("admin_dashboard"),
            {
                "action": "blood_bank_toggle",
                "blood_bank_id": self.bank.pk
            }
        )
        self.assertEqual(response.status_code, 302)
        self.bank.refresh_from_db()
        self.assertFalse(self.bank.is_active)


from donors.models import ActivityLog, log_activity

class ActivityHistoryTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username="admin_logs", password="adminpassword")
        self.client.login(username="admin_logs", password="adminpassword")

    def test_log_activity_creates_entry(self):
        log_activity(self.admin_user, "TEST_ACTIVITY", "This is a test details message.")
        self.assertEqual(ActivityLog.objects.filter(activity_type="TEST_ACTIVITY").count(), 1)
        entry = ActivityLog.objects.get(activity_type="TEST_ACTIVITY")
        self.assertEqual(entry.user, self.admin_user)
        self.assertEqual(entry.details, "This is a test details message.")

    def test_admin_login_creates_log(self):
        # We logged in in setUp, so there should already be an ADMIN_LOGIN log!
        self.assertTrue(ActivityLog.objects.filter(activity_type="ADMIN_LOGIN").exists())

    def test_hospital_actions_logged(self):
        # Create hospital
        from requests.models import Hospital
        response = self.client.post(
            reverse("admin_dashboard"),
            {
                "action": "hospital_create",
                "name": "PMCH Patna",
                "city": "Patna",
                "address": "Ashok Rajpath, Patna",
                "is_active": "on"
            }
        )
        self.assertEqual(response.status_code, 302)
        h = Hospital.objects.get(name="PMCH Patna")
        self.assertTrue(ActivityLog.objects.filter(activity_type="HOSPITAL_ACTION", details__contains="Created hospital: 'PMCH Patna'").exists())

        # Update hospital
        response = self.client.post(
            reverse("admin_dashboard"),
            {
                "action": "hospital_update",
                "hospital_id": h.pk,
                "name": "PMCH Patna Updated",
                "city": "Patna",
                "address": "Ashok Rajpath, Patna",
                "is_active": "on"
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ActivityLog.objects.filter(activity_type="HOSPITAL_ACTION", details__contains="Updated hospital details for 'PMCH Patna Updated'").exists())

        # Delete hospital
        h.refresh_from_db()
        h.delete()
        self.assertTrue(ActivityLog.objects.filter(activity_type="HOSPITAL_ACTION", details__contains="Deleted hospital: PMCH Patna Updated").exists())

    def test_activity_filters_in_dashboard(self):
        # Let's create some dummy logs with different types and dates
        log_activity(self.admin_user, "CAMP_ACTION", "Scheduled test camp")
        log_activity(self.admin_user, "DONATION_COMPLETE", "Completed donation 1")

        # Query all logs via GET
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        
        # Test search query
        response = self.client.get(reverse("admin_dashboard"), {"activity_search": "test camp"})
        self.assertContains(response, "Scheduled test camp")
        self.assertNotContains(response, "Completed donation 1")

        # Test type query
        response = self.client.get(reverse("admin_dashboard"), {"activity_type": "DONATION_COMPLETE"})
        self.assertContains(response, "Completed donation 1")
        self.assertNotContains(response, "Scheduled test camp")




