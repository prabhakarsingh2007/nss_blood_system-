from django.contrib import admin
from .models import BloodRequest, Hospital, BloodBank

@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "is_active")
    list_filter = ("city", "is_active")
    search_fields = ("name", "city")

@admin.register(BloodBank)
class BloodBankAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "is_active")
    list_filter = ("city", "is_active")
    search_fields = ("name", "city")

@admin.register(BloodRequest)
class BloodRequestAdmin(admin.ModelAdmin):
    list_display = (
        "requester_name",
        "blood_group",
        "units",
        "city",
        "status",
        "request_code",
        "otp_verified",
        "assigned_donor",
        "fulfilled_by",
        "requested_at",
    )
    list_filter = ("blood_group", "status", "city")
    search_fields = ("requester_name", "contact_number", "hospital_name")
