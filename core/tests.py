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

