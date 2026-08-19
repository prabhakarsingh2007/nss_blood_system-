from datetime import timedelta, date, time
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from donors.models import BloodCamp, CampRegistration, DonationHistory, DonorProfile, validate_camp_image

User = get_user_model()

class BloodCampTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="password", is_staff=True)
        self.donor_user = User.objects.create_user(username="donor", password="password")
        self.donor = DonorProfile.objects.create(
            user=self.donor_user,
            full_name="John Doe",
            blood_group="B+",
            age=25,
            phone="9999999999",
            city="Purnia",
            verification_status="APPROVED",
            otp_verified=True
        )

    def test_dynamic_status_auto(self):
        # Tomorrow -> UPCOMING
        tomorrow = timezone.localdate() + timedelta(days=1)
        camp = BloodCamp.objects.create(
            title="Upcoming Camp",
            description="Test description",
            date=tomorrow,
            location="VVIT Purnia",
            district="Purnia",
            status="AUTO"
        )
        self.assertEqual(camp.current_status, "UPCOMING")

        # Yesterday -> COMPLETED
        yesterday = timezone.localdate() - timedelta(days=1)
        camp2 = BloodCamp.objects.create(
            title="Past Camp",
            description="Test description",
            date=yesterday,
            location="VVIT Purnia",
            district="Purnia",
            status="AUTO"
        )
        self.assertEqual(camp2.current_status, "COMPLETED")

    def test_manual_status_override(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        camp = BloodCamp.objects.create(
            title="Forced Completed Camp",
            description="Test description",
            date=tomorrow,
            location="VVIT Purnia",
            district="Purnia",
            status="COMPLETED"
        )
        # Even though date is in the future, status is manually set to COMPLETED
        self.assertEqual(camp.current_status, "COMPLETED")

    def test_image_validator(self):
        # Valid image
        small_valid = SimpleUploadedFile("test.png", b"file_content", content_type="image/png")
        # Should not raise any exception
        validate_camp_image(small_valid)

        # Invalid extension
        invalid_ext = SimpleUploadedFile("test.txt", b"file_content", content_type="text/plain")
        with self.assertRaises(ValidationError):
            validate_camp_image(invalid_ext)

        # File too large (6MB)
        large_file = SimpleUploadedFile("large.png", b"0" * (6 * 1024 * 1024), content_type="image/png")
        with self.assertRaises(ValidationError):
            validate_camp_image(large_file)

    def test_donation_history_relationship_and_fallback(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        camp = BloodCamp.objects.create(
            title="VVIT Purnia Camp",
            description="Test description",
            date=yesterday,
            location="VVIT Purnia",
            district="Purnia",
            status="COMPLETED",
            manual_donation_count=15
        )
        # Fallback count when no database records exist
        self.assertEqual(camp.successful_donations_count, 15)

        # Link a verified donation
        from requests.models import BloodRequest
        req = BloodRequest.objects.create(
            requester_name="Patient",
            contact_number="9876543210",
            blood_group="B+",
            units=2,
            hospital_name="Hospital",
            city="Purnia",
            otp_verified=True,
            status="COMPLETED"
        )
        DonationHistory.objects.create(
            donor=self.donor,
            request=req,
            camp=camp,
            status="SUCCESS",
            nss_verified=True
        )
        # Dynamic count now should evaluate to database count (1) instead of manual fallback (15)
        self.assertEqual(camp.successful_donations_count, 1)

    def test_registration_prevention_on_completed_camp(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        camp = BloodCamp.objects.create(
            title="Finished Camp",
            description="Test description",
            date=yesterday,
            location="VVIT Purnia",
            district="Purnia",
            status="COMPLETED"
        )
        self.client.force_login(self.donor_user)
        response = self.client.post(f"/camps/{camp.id}/register/")
        self.assertRedirects(response, f"/camps/{camp.id}/")
        
        # Verify no registration is created
        self.assertFalse(CampRegistration.objects.filter(donor=self.donor, camp=camp).exists())

    def test_verify_certificate_view(self):
        # Create verified donation history with certificate ID
        from requests.models import BloodRequest
        req = BloodRequest.objects.create(
            requester_name="Verify Patient",
            contact_number="9876543211",
            blood_group="O+",
            units=1,
            hospital_name="Purnea Hospital",
            city="Purnia",
            otp_verified=True,
            status="COMPLETED"
        )
        dh = DonationHistory.objects.create(
            donor=self.donor,
            request=req,
            status="SUCCESS",
            nss_verified=True,
            certificate_id="NSS-2026-9999",
            verified_at=timezone.now()
        )
        
        # Query existing certificate
        response = self.client.get("/verify-certificate/?cert_id=NSS-2026-9999")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verified Record")
        self.assertContains(response, "John Doe")
        
        # Query non-existing certificate
        response = self.client.get("/verify-certificate/?cert_id=INVALID-ID")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Certificate Verification Failed")
