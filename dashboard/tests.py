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

