from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard_router, name="dashboard_router"),
    path("user-dashboard/", views.user_dashboard, name="user_dashboard"),
    path("search/", views.search_donors, name="search_donors"),
    path("donors/", views.donor_list, name="donor_list"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("donor-register/", views.donor_register, name="donor_register"),
    path("donor-verify-otp/", views.donor_verify_otp, name="donor_verify_otp"),
    path("request-form/", views.request_form, name="request_form"),
    path("request-verify-otp/", views.request_verify_otp, name="request_verify_otp"),
    path("request-status/", views.request_status, name="request_status"),
    path("camps/", views.camp_list, name="camp_list"),
    path("camps/<int:camp_id>/", views.camp_detail, name="camp_detail"),
    path("camps/<int:camp_id>/register/", views.register_camp, name="register_camp"),
    path("donor-dashboard/", views.donor_dashboard, name="donor_dashboard"),
    path("donate-request/<int:request_id>/", views.donate_request, name="donate_request"),
    path("certificate/<int:history_id>/", views.donation_certificate, name="donation_certificate"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
]