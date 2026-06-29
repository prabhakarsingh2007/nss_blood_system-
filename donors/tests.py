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

    def test_donor_cooldown_days_and_availability(self):
        from django.contrib.auth.models import User
        from django.utils import timezone
        from datetime import timedelta
        from donors.models import DonorProfile
        
        user_new = User.objects.create_user(username="new_donor", password="password")
        profile_new = DonorProfile.objects.create(
            user=user_new,
            full_name="New Volunteer",
            blood_group="B+",
            age=25,
            phone="9999988888",
            city="Patna",
            verification_status="APPROVED",
            otp_verified=True,
            available=True
        )
        # 1. No donation history means cooldown is 0 and active donor is True
        self.assertEqual(profile_new.cooldown_days_remaining, 0)
        self.assertTrue(profile_new.is_active_donor)
        
        # 2. Donation 45 days ago means cooldown is 45 and active donor is False
        profile_new.last_donation_date = timezone.localdate() - timedelta(days=45)
        profile_new.save()
        self.assertTrue(profile_new.cooldown_days_remaining > 0)
        self.assertFalse(profile_new.is_active_donor)
        
        # 3. Donation 95 days ago means cooldown is 0 and active donor is True
        profile_new.last_donation_date = timezone.localdate() - timedelta(days=95)
        profile_new.save()
        self.assertEqual(profile_new.cooldown_days_remaining, 0)
        self.assertTrue(profile_new.is_active_donor)

        # 4. Form validation check for future donation date
        from donors.forms import DonorProfileForm
        data_future = {
            "full_name": "Eligible Volunteer",
            "blood_group": "B+",
            "age": 25,
            "phone": "9999988888",
            "city": "Patna",
            "last_donation_date": timezone.localdate() + timedelta(days=5),
            "available": True,
        }
        form = DonorProfileForm(data=data_future)
        self.assertFalse(form.is_valid())
        self.assertIn("last_donation_date", form.errors)

    def test_donor_search_rate_limiter(self):
        from django.urls import reverse
        from django.core.cache import cache
        
        # Clear cache first to ensure a clean state
        cache.clear()
        
        url = reverse("search_donors")
        
        # Make 30 requests - all should succeed (status 200)
        for _ in range(30):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            
        # The 31st request should be rate-limited (status 429)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 429)
