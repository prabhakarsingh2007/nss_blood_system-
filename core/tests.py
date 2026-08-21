from django.test import TestCase
from django.urls import reverse

class CoreViewsTestCase(TestCase):
    def test_home_view(self):
        url = reverse("home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")

    def test_eligibility_view(self):
        url = reverse("eligibility_checker")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/eligibility.html")

    def test_about_view(self):
        url = reverse("about")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/about.html")
        self.assertIn("upcoming_camps", response.context)
        self.assertIn("completed_camps", response.context)
        self.assertIn("verified_donations", response.context)
        self.assertIn("recent_gallery", response.context)
        self.assertIn("total_districts", response.context)

    def test_blood_heroes_section(self):
        from django.contrib.auth import get_user_model
        from donors.models import DonorProfile, DonationHistory
        from requests.models import BloodRequest
        
        User = get_user_model()
        user1 = User.objects.create_user(username="donor1", password="password")
        user2 = User.objects.create_user(username="donor2", password="password")
        
        donor1 = DonorProfile.objects.create(
            user=user1,
            full_name="Hero Donor One",
            blood_group="O+",
            age=30,
            phone="9999999901",
            city="Purnia",
            verification_status="APPROVED",
            otp_verified=True
        )
        donor2 = DonorProfile.objects.create(
            user=user2,
            full_name="Hero Donor Two",
            blood_group="A+",
            age=28,
            phone="9999999902",
            city="Patna",
            verification_status="APPROVED",
            otp_verified=True
        )
        
        req = BloodRequest.objects.create(
            requester_name="Patient",
            contact_number="9876543210",
            blood_group="O+",
            units=1,
            hospital_name="Hospital",
            city="Purnia",
            otp_verified=True,
            status="COMPLETED"
        )
        
        # 1. Verified and Success -> included
        dh1 = DonationHistory.objects.create(
            donor=donor1,
            request=req,
            status="SUCCESS",
            nss_verified=True,
            certificate_id="NSS-HERO-1"
        )
        
        req2 = BloodRequest.objects.create(
            requester_name="Patient 2",
            contact_number="9876543212",
            blood_group="O+",
            units=1,
            hospital_name="Hospital 2",
            city="Purnia",
            otp_verified=True,
            status="COMPLETED"
        )
        # 2. Duplicate verified success for donor1 -> should be deduplicated
        dh1_dup = DonationHistory.objects.create(
            donor=donor1,
            request=req2,
            status="SUCCESS",
            nss_verified=True,
            certificate_id="NSS-HERO-1-DUP"
        )
        
        # 3. Unverified -> excluded
        dh2 = DonationHistory.objects.create(
            donor=donor2,
            request=req,
            status="SUCCESS",
            nss_verified=False,
            certificate_id="NSS-HERO-2"
        )
        
        # 4. Failed donation -> excluded
        user3 = User.objects.create_user(username="donor3", password="password")
        donor3 = DonorProfile.objects.create(
            user=user3,
            full_name="Hero Donor Three",
            blood_group="B+",
            age=25,
            phone="9999999903",
            city="Katihar",
            verification_status="APPROVED",
            otp_verified=True
        )
        dh3 = DonationHistory.objects.create(
            donor=donor3,
            request=req,
            status="FAILED",
            nss_verified=True,
            certificate_id="NSS-HERO-3"
        )

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        
        # Verify that verified_donations are in the context
        verified_donations = response.context["verified_donations"]
        
        # dh1 or dh1_dup should be included
        self.assertTrue(any(d.id == dh1.id or d.id == dh1_dup.id for d in verified_donations))
        # Deduplication check: donor1 should only appear once
        donor_ids = [d.donor.id for d in verified_donations]
        self.assertEqual(donor_ids.count(donor1.id), 1)
        
        # dh2 (unverified) should be excluded
        self.assertFalse(any(d.id == dh2.id for d in verified_donations))
        # dh3 (failed) should be excluded
        self.assertFalse(any(d.id == dh3.id for d in verified_donations))

