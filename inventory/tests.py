from django.test import TestCase
from django.urls import reverse
from .models import BloodStock

class BloodInventoryTests(TestCase):
    def test_blood_stock_model_creation_and_status(self):
        # 1. Test status property for different stock units
        stock_out = BloodStock.objects.create(blood_group="A-", units=0)
        self.assertEqual(stock_out.stock_status, "OUT OF STOCK")
        self.assertEqual(str(stock_out), "A-: 0 Units")

        stock_critical = BloodStock.objects.create(blood_group="B-", units=3)
        self.assertEqual(stock_critical.stock_status, "CRITICAL LOW")

        stock_low = BloodStock.objects.create(blood_group="AB-", units=10)
        self.assertEqual(stock_low.stock_status, "LOW")

        stock_normal = BloodStock.objects.create(blood_group="O-", units=25)
        self.assertEqual(stock_normal.stock_status, "NORMAL")

    def test_blood_inventory_view_and_auto_generation(self):
        # View should auto-generate all 8 standard blood groups on access
        self.assertEqual(BloodStock.objects.count(), 0)

        response = self.client.get(reverse("blood_inventory"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inventory/blood_inventory.html")

        # Confirm all 8 groups are created
        self.assertEqual(BloodStock.objects.count(), 8)
        self.assertEqual(response.context["total_units"], 0)
        # All 8 groups start with 0 units which falls under OUT OF STOCK (so 8 warnings)
        self.assertEqual(response.context["low_stocks_count"], 8)
