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
                "status": "APPROVED"
            }
        )
        self.assertEqual(response.status_code, 302)
        
        req.refresh_from_db()
        self.assertEqual(req.status, "APPROVED")
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


