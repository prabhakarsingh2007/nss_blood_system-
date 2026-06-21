from django.urls import path
from . import views

urlpatterns = [
    path("donors/", views.donor_list, name="donor_list"),
    path("donor-register/", views.donor_register, name="donor_register"),
    path("donor-verify-otp/", views.donor_verify_otp, name="donor_verify_otp"),
    path("camps/", views.camp_list, name="camp_list"),
    path("camps/<int:camp_id>/", views.camp_detail, name="camp_detail"),
    path("camps/<int:camp_id>/register/", views.register_camp, name="register_camp"),
    path("certificate/<int:history_id>/", views.donation_certificate, name="donation_certificate"),
    path("search/", views.search_donors, name="search_donors"),
]
