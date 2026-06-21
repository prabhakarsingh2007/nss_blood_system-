from django.test import TestCase

class ValidationAndSecurityTests(TestCase):
    def test_donor_profile_age_validation(self):
        from donors.forms import DonorProfileForm
        
        # Age below 18 should fail validation
        data_underage = {
            "full_name": "Young Volunteer",
            "blood_group": "B+",
            "age": 16,
            "phone": "9999988888",
            "city": "Patna",
            "available": True,
        }
        form = DonorProfileForm(data=data_underage)
        self.assertFalse(form.is_valid())
        self.assertIn("age", form.errors)

        # Age above 65 should fail validation
        data_overage = {
            "full_name": "Senior Volunteer",
            "blood_group": "B+",
            "age": 70,
            "phone": "9999988888",
            "city": "Patna",
            "available": True,
        }
        form = DonorProfileForm(data=data_overage)
        self.assertFalse(form.is_valid())
        self.assertIn("age", form.errors)

        # Valid age should pass
        data_valid = {
            "full_name": "Eligible Volunteer",
            "blood_group": "B+",
            "age": 25,
            "phone": "9999988888",
            "city": "Patna",
            "available": True,
        }
        form = DonorProfileForm(data=data_valid)
        self.assertTrue(form.is_valid())

    def test_blood_camp_past_date_validation(self):
        from donors.forms import BloodCampForm
        from datetime import timedelta
        from django.utils import timezone
        
        # Past date should fail
        yesterday = timezone.localdate() - timedelta(days=1)
        data_past = {
            "title": "Expired Blood Camp",
            "description": "Past date camp",
            "date": yesterday,
            "location": "Patna",
        }
        form = BloodCampForm(data=data_past)
        self.assertFalse(form.is_valid())
        self.assertIn("date", form.errors)

    def test_donor_dashboard_view_resolves_without_type_error(self):
        from django.contrib.auth.models import User
        from django.urls import reverse
        from donors.models import DonorProfile
        
        user = User.objects.create_user(username="test_donor", password="password")
        profile = DonorProfile.objects.create(
            user=user,
            full_name="Test Donor",
            blood_group="B+",
            age=25,
            phone="9999988888",
            city="Patna",
            verification_status="APPROVED",
            otp_verified=True,
            available=True
        )
        self.client.login(username="test_donor", password="password")
        response = self.client.get(reverse("donor_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["verified_donation_count"], 0)
