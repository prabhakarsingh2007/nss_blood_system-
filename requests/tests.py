from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.auth.models import User, AnonymousUser
from requests.models import BloodRequest
from donors.models import DonorProfile
from requests.views import request_status

class RequestStatusTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="password")

    def test_unauthenticated_request_status_masks_details(self):
        # Create a mock donor
        donor_user = User.objects.create_user(username="donor_user", password="password")
        donor = DonorProfile.objects.create(
            user=donor_user,
            full_name="Jane Donor",
            blood_group="A+",
            age=25,
            phone="1122334455",
            city="Patna",
            verification_status="APPROVED",
            otp_verified=True,
            available=True
        )

        # Create a mock BloodRequest and assign the donor
        BloodRequest.objects.create(
            requester_name="John Doe",
            blood_group="A+",
            units=1,
            hospital_name="Patna Medical College",
            city="Patna",
            contact_number="9876543210",
            reason="Accident emergency",
            otp_verified=True,
            status="APPROVED",
            assigned_donor=donor
        )

        # Build request for searching phone number
        request = self.factory.get(reverse("request_status") + "?phone=9876543210")

        # Set up sessions and messages middleware fallback
        request.session = {}
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        request.user = AnonymousUser()

        # Execute views
        response = request_status(request)
        self.assertEqual(response.status_code, 200)

        # Verify that the rendered HTML immediately contains full details (no masking, no OTP prompt)
        html_content = response.content.decode("utf-8")
        self.assertNotIn("[Hospital Address Masked]", html_content)
        self.assertNotIn("Verify Phone to Unlock", html_content)
        self.assertIn("Patna Medical College", html_content)
        
        # Verify that no OTP has been generated
        self.assertNotIn("status_search_otp", request.session)

    def test_verified_search_shows_full_details(self):
        # Create a mock donor
        donor_user = User.objects.create_user(username="donor_user2", password="password")
        donor = DonorProfile.objects.create(
            user=donor_user,
            full_name="Jane Donor",
            blood_group="A+",
            age=25,
            phone="1122334455",
            city="Patna",
            verification_status="APPROVED",
            otp_verified=True,
            available=True
        )

        # Create a mock BloodRequest
        BloodRequest.objects.create(
            requester_name="John Doe",
            blood_group="A+",
            units=1,
            hospital_name="Patna Medical College",
            city="Patna",
            contact_number="9876543210",
            reason="Accident emergency",
            otp_verified=True,
            status="APPROVED",
            assigned_donor=donor
        )

        # Search phone search request with verified status phone in session
        request = self.factory.get(reverse("request_status") + "?phone=9876543210")
        request.session = {"verified_status_phone": "9876543210"}
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        request.user = AnonymousUser()

        response = request_status(request)
        self.assertEqual(response.status_code, 200)

        # Verify that the rendered HTML contains the unmasked details
        html_content = response.content.decode("utf-8")
        self.assertNotIn("[Hospital Address Masked]", html_content)
        self.assertNotIn("Verify Phone to Unlock", html_content)
        self.assertIn("Patna Medical College", html_content)
        self.assertIn("1122334455", html_content)

    def test_emergency_priority_field(self):
        # Create requests with different priorities
        req_normal = BloodRequest.objects.create(
            requester_name="Normal Patient",
            blood_group="O-",
            units=2,
            hospital_name="Patna Hospital",
            city="Patna",
            contact_number="9876543220",
            reason="Routine surgery",
            priority="NORMAL",
            otp_verified=True,
            status="PENDING"
        )
        req_urgent = BloodRequest.objects.create(
            requester_name="Urgent Patient",
            blood_group="B+",
            units=1,
            hospital_name="Gaya General",
            city="Gaya",
            contact_number="9876543221",
            reason="Accident case",
            priority="URGENT",
            otp_verified=True,
            status="PENDING"
        )
        req_critical = BloodRequest.objects.create(
            requester_name="Critical Patient",
            blood_group="AB-",
            units=3,
            hospital_name="Patna Medical",
            city="Patna",
            contact_number="9876543222",
            reason="Severe bleeding",
            priority="CRITICAL",
            otp_verified=True,
            status="PENDING"
        )

        # Check self.is_emergency auto calculation
        self.assertFalse(req_normal.is_emergency)
        self.assertTrue(req_urgent.is_emergency)
        self.assertTrue(req_critical.is_emergency)

        # Check rendering priority choices in requests status page
        request = self.factory.get(reverse("request_status") + "?phone=9876543222")
        request.session = {}
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        request.user = AnonymousUser()

        response = request_status(request)
        self.assertEqual(response.status_code, 200)
        html_content = response.content.decode("utf-8")
        self.assertIn("Critical", html_content)

