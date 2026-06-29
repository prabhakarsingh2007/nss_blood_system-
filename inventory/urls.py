from django.urls import path
from . import views

urlpatterns = [
    path("stock/", views.blood_inventory, name="blood_inventory"),
]
