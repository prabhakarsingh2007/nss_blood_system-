from django.test import TestCase
from django.contrib.auth.models import User

class RegistrationFormTests(TestCase):
    def test_valid_registration(self):
        from accounts.forms import UserRegisterForm
        data = {
            "name": "Prabhakar Singh",
            "email": "prabhakar@gmail.com",
            "phone": "9876543210",
            "blood_group": "O+",
            "gender": "Male",
            "city": "Patna",
            "age": 25,
            "password": "Password123",
            "confirm_password": "Password123",
        }
        form = UserRegisterForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.username, "prabhakar@gmail.com")
        self.assertEqual(user.email, "prabhakar@gmail.com")
        self.assertEqual(user.first_name, "Prabhakar")
        self.assertEqual(user.last_name, "Singh")
        
        # Check DonorProfile
        self.assertTrue(hasattr(user, "donorprofile"))
        profile = user.donorprofile
        self.assertEqual(profile.full_name, "Prabhakar Singh")
        self.assertEqual(profile.phone, "9876543210")
        self.assertEqual(profile.blood_group, "O+")
        self.assertEqual(profile.gender, "Male")
        self.assertEqual(profile.age, 25)
        self.assertTrue(profile.otp_verified)

    def test_invalid_name_fails(self):
        from accounts.forms import UserRegisterForm
        data = {
            "name": "Prabhakar123",
            "email": "prabhakar2@gmail.com",
            "phone": "9876543210",
            "blood_group": "O+",
            "gender": "Male",
            "city": "Patna",
            "age": 25,
            "password": "Password123",
            "confirm_password": "Password123",
        }
        form = UserRegisterForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_invalid_phone_fails(self):
        from accounts.forms import UserRegisterForm
        data = {
            "name": "Prabhakar Singh",
            "email": "prabhakar3@gmail.com",
            "phone": "98765432100",  # 11 digits
            "blood_group": "O+",
            "gender": "Male",
            "city": "Patna",
            "age": 25,
            "password": "Password123",
            "confirm_password": "Password123",
        }
        form = UserRegisterForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_invalid_age_fails(self):
        from accounts.forms import UserRegisterForm
        data = {
            "name": "Prabhakar Singh",
            "email": "prabhakar4@gmail.com",
            "phone": "9876543210",
            "blood_group": "O+",
            "gender": "Male",
            "city": "Patna",
            "age": 17,  # underage
            "password": "Password123",
            "confirm_password": "Password123",
        }
        form = UserRegisterForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("age", form.errors)

    def test_invalid_password_format_fails(self):
        from accounts.forms import UserRegisterForm
        data = {
            "name": "Prabhakar Singh",
            "email": "prabhakar5@gmail.com",
            "phone": "9876543210",
            "blood_group": "O+",
            "gender": "Male",
            "city": "Patna",
            "age": 25,
            "password": "password",  # no numbers
            "confirm_password": "password",
        }
        form = UserRegisterForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_mismatched_password_fails(self):
        from accounts.forms import UserRegisterForm
        data = {
            "name": "Prabhakar Singh",
            "email": "prabhakar6@gmail.com",
            "phone": "9876543210",
            "blood_group": "O+",
            "gender": "Male",
            "city": "Patna",
            "age": 25,
            "password": "Password123",
            "confirm_password": "Password124",
        }
        form = UserRegisterForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("confirm_password", form.errors)

from django.test import override_settings

@override_settings(AXES_ENABLED=True)
class BruteForceLockoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="ValidPassword123")

    def test_brute_force_lockout_admin_and_login_attempts(self):
        from django.urls import reverse
        from axes.utils import reset
        
        login_url = reverse("login")
        
        # Reset axes state
        reset()
        
        # Make 5 failed login attempts
        for _ in range(5):
            self.client.post(login_url, {
                "username": "testuser",
                "password": "WrongPassword"
            })
            
        # The 6th attempt should result in a lockout
        response = self.client.post(login_url, {
            "username": "testuser",
            "password": "WrongPassword"
        })
        
        self.assertEqual(response.status_code, 429)
        self.assertTemplateUsed(response, "core/lockout.html")
