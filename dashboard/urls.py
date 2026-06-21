from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard_router, name="dashboard_router"),
    path("user-dashboard/", views.user_dashboard, name="user_dashboard"),
    path("donor-dashboard/", views.donor_dashboard, name="donor_dashboard"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
]
