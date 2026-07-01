from django.urls import path
from . import views

urlpatterns = [
    path("request-form/", views.request_form, name="request_form"),
    path("request-verify-otp/", views.request_verify_otp, name="request_verify_otp"),
    path("request-status/", views.request_status, name="request_status"),
    path("donate-request/<int:request_id>/", views.donate_request, name="donate_request"),
    path("media/prescriptions/<path:filename>", views.serve_prescription, name="serve_prescription"),
]
