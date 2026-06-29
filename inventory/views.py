from django.shortcuts import render
from .models import BloodStock

def blood_inventory(request):
    # Auto-initialize all 8 standard blood groups with 0 units if not present
    groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    for group in groups:
        BloodStock.objects.get_or_create(blood_group=group)
        
    stocks = BloodStock.objects.all().order_by("blood_group")
    
    # Calculate overview metrics
    total_units = sum(stock.units for stock in stocks)
    low_stocks_count = sum(1 for stock in stocks if stock.stock_status in {"CRITICAL LOW", "OUT OF STOCK"})
    
    context = {
        "stocks": stocks,
        "total_units": total_units,
        "low_stocks_count": low_stocks_count,
    }
    return render(request, "inventory/blood_inventory.html", context)
