import os
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

    def test_request_tracking_cards_and_rejection(self):
        # Create a pending request
        req = BloodRequest.objects.create(
            requester_name="Track Patient",
            blood_group="O+",
            units=2,
            hospital_name="Purnia Sadar",
            city="Purnia",
            contact_number="9988776655",
            reason="Blood loss",
            priority="URGENT",
            otp_verified=True,
            status="PENDING"
        )
        
        # 1. Verify tracking lookup by code and phone
        request = self.factory.get(reverse("request_status") + f"?code={req.request_code}&phone=9988776655")
        request.session = {}
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        request.user = AnonymousUser()

        response = request_status(request)
        self.assertEqual(response.status_code, 200)
        html_content = response.content.decode("utf-8")
        self.assertIn("Pending Verification", html_content)
        self.assertIn("Your request is under verification.", html_content)

        # 2. Reject request with reason and verify rejection card display
        req.status = "REJECTED"
        req.rejection_reason = "Out of volunteer area."
        req.save()

        response = request_status(request)
        self.assertEqual(response.status_code, 200)
        html_content = response.content.decode("utf-8")
        self.assertIn("Request Rejected", html_content)
        self.assertIn("Out of volunteer area.", html_content)

    def test_blood_request_form_hospital_and_bank_choices(self):
        from requests.forms import BloodRequestForm
        from requests.models import Hospital, BloodBank

        # Create active and inactive hospitals
        hospital_active = Hospital.objects.create(name="Active Hospital", city="Patna", is_active=True)
        hospital_inactive = Hospital.objects.create(name="Inactive Hospital", city="Patna", is_active=False)

        # Instantiate form
        form = BloodRequestForm()

        # Check queryset of hospital_name field
        queryset_hosp = form.fields["hospital_name"].queryset
        self.assertIn(hospital_active, queryset_hosp)
        self.assertNotIn(hospital_inactive, queryset_hosp)

    def test_request_verify_otp_flow(self):
        from django.urls import reverse
        from requests.models import BloodRequest
        
        req = BloodRequest.objects.create(
            requester_name="Verify Patient",
            blood_group="O+",
            units=1,
            hospital_name="Patna Hospital",
            city="Patna",
            contact_number="9988776655",
            reason="Surgery",
            priority="NORMAL",
            otp_verified=False
        )
        otp = req.generate_otp()
        req.save()
        
        session = self.client.session
        session['pending_request_code'] = req.request_code
        session.save()
        
        # Test GET request
        response = self.client.get(reverse("request_verify_otp"))
        self.assertEqual(response.status_code, 200)
        
        # Test POST request with invalid OTP
        response = self.client.post(reverse("request_verify_otp"), {"otp": "000000"})
        self.assertEqual(response.status_code, 200)
        req.refresh_from_db()
        self.assertFalse(req.otp_verified)
        
        # Test POST request with valid OTP
        response = self.client.post(reverse("request_verify_otp"), {"otp": otp})
        self.assertEqual(response.status_code, 302)  # Should redirect
        req.refresh_from_db()
        self.assertTrue(req.otp_verified)

    def test_blood_request_admin_actions(self):
        from django.contrib.admin.sites import AdminSite
        from requests.admin import BloodRequestAdmin
        from requests.models import BloodRequest
        
        req = BloodRequest.objects.create(
            requester_name="Action Patient",
            blood_group="O+",
            units=1,
            hospital_name="Patna Hospital",
            city="Patna",
            contact_number="9988776654",
            reason="Surgery",
            priority="NORMAL",
            otp_verified=False,
            status="PENDING"
        )
        
        site = AdminSite()
        admin_instance = BloodRequestAdmin(BloodRequest, site)
        admin_instance.message_user = lambda request, message, level=25, extra_tags="", fail_silently=False: None
        
        req_obj = None
        
        # 1. Test approve_requests action
        qs = BloodRequest.objects.filter(id=req.id)
        admin_instance.approve_requests(req_obj, qs)
        req.refresh_from_db()
        self.assertEqual(req.status, "APPROVED")
        self.assertTrue(req.otp_verified)
        
        # 2. Test export_requests_as_csv action
        response = admin_instance.export_requests_as_csv(req_obj, qs)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("Action Patient", content)


class PrescriptionAndStateTests(TestCase):
    def setUp(self):
        from requests.models import Hospital, BloodBank
        self.user = User.objects.create_user(username="requester", password="password")
        self.staff_user = User.objects.create_user(username="staff", password="password", is_staff=True)
        self.other_user = User.objects.create_user(username="other", password="password")
        self.hospital = Hospital.objects.create(name="Patna Hospital", city="Patna", is_active=True)
        self.blood_bank = BloodBank.objects.create(name="Patna Blood Bank", city="Patna", is_active=True)
        
    def test_form_validation(self):
        from requests.forms import BloodRequestForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # 1. Test missing prescription
        data = {
            "requester_name": "Test Patient",
            "blood_group": "A+",
            "units": 2,
            "hospital_name": self.hospital.name,
            "blood_bank": self.blood_bank.name,
            "city": "Patna",
            "contact_number": "9988776655",
            "reason": "Accident",
            "priority": "URGENT",
        }
        form = BloodRequestForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("prescription", form.errors)
        
        # 2. Test invalid extension
        files = {
            "prescription": SimpleUploadedFile("prescription.txt", b"dummy content", content_type="text/plain")
        }
        form = BloodRequestForm(data=data, files=files)
        self.assertFalse(form.is_valid())
        self.assertIn("Only JPG, JPEG, PNG, and PDF files are allowed.", form.errors["prescription"][0])

        # 3. Test too large file (> 5MB)
        large_content = b"x" * (5 * 1024 * 1024 + 100)
        files = {
            "prescription": SimpleUploadedFile("prescription.jpg", large_content, content_type="image/jpeg")
        }
        form = BloodRequestForm(data=data, files=files)
        self.assertFalse(form.is_valid())
        self.assertIn("File size must be under 5 MB.", form.errors["prescription"][0])

        # 4. Test valid file
        files = {
            "prescription": SimpleUploadedFile("prescription.jpg", b"valid content", content_type="image/jpeg")
        }
        form = BloodRequestForm(data=data, files=files)
        self.assertTrue(form.is_valid())

    def test_serve_prescription_security(self):
        from requests.models import BloodRequest
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        req = BloodRequest.objects.create(
            requester=self.user,
            requester_name="Test Patient",
            blood_group="A+",
            units=2,
            hospital_name="Patna Hospital",
            city="Patna",
            contact_number="9988776655",
            reason="Accident",
            priority="URGENT",
            prescription=SimpleUploadedFile("my_presc.png", b"dummy image", content_type="image/png"),
            otp_verified=True,
            status="PENDING"
        )
        
        # Get filename part from field path
        filename = os.path.basename(req.prescription.name)
        url = reverse("serve_prescription", kwargs={"filename": filename})
        
        # Test 1: Unauthenticated user access
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        
        # Test 2: Logged in other user (not owner, not staff)
        self.client.login(username="other", password="password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # Test 3: Logged in owner user
        self.client.login(username="requester", password="password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Test 4: Logged in staff user
        self.client.login(username="staff", password="password")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Test 5: Guest with authorized_requests in session
        session = self.client.session
        session['authorized_requests'] = [req.request_code]
        session.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_workflow_redirection_and_prefill(self):
        # 1. Access form directly without blood_group (should redirect to search_donors)
        response = self.client.get(reverse("request_form"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("search_donors"), fetch_redirect_response=False)
        
        # Check error message is added
        messages_list = list(response.wsgi_request._messages)
        self.assertTrue(any("Please select a Blood Group first." in str(m) for m in messages_list))
        
        # 2. Access form with blood_group but missing city (should redirect to search_donors)
        response = self.client.get(reverse("request_form") + "?blood_group=A%2B")
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("search_donors"), fetch_redirect_response=False)
        
        # Check error message is added
        messages_list = list(response.wsgi_request._messages)
        self.assertTrue(any("Please select a District/City first." in str(m) for m in messages_list))
        
        # 3. Access form with both blood_group and city (should return 200 OK)
        response = self.client.get(reverse("request_form") + "?blood_group=A%2B&city=Patna")
        self.assertEqual(response.status_code, 200)
        
        # 4. Post to form without blood_group (should redirect to search_donors)
        response = self.client.post(reverse("request_form"), {
            "city": "Patna",
            "requester_name": "Test Patient",
            "units": 2,
            "hospital_name": self.hospital.name,
            "contact_number": "9988776655",
            "reason": "Accident",
            "priority": "URGENT",
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("search_donors"), fetch_redirect_response=False)

        # 5. Check dynamic hospital filtering
        from requests.forms import BloodRequestForm
        from requests.models import Hospital
        # Create active hospitals in Patna and Gaya
        h_patna = Hospital.objects.create(name="Patna General", city="Patna", is_active=True)
        h_gaya = Hospital.objects.create(name="Gaya General", city="Gaya", is_active=True)

        form_patna = BloodRequestForm(initial={"city": "Patna"})
        self.assertIn(h_patna, form_patna.fields["hospital_name"].queryset)
        self.assertNotIn(h_gaya, form_patna.fields["hospital_name"].queryset)





