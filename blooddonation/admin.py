from django.contrib import admin

from .models import BloodCamp, BloodRequest, BroadcastMessage, CampRegistration, DonationHistory, DonorProfile


class CampRegistrationInline(admin.TabularInline):
    model = CampRegistration
    extra = 0
    autocomplete_fields = ("donor",)
    fields = ("donor", "status", "registered_at")
    readonly_fields = ("registered_at",)


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "blood_group", "city", "verification_status", "otp_verified", "available", "created_at")
    list_filter = ("blood_group", "city", "verification_status", "otp_verified", "available")
    search_fields = ("full_name", "phone", "city")


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


@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(admin.ModelAdmin):
    list_display = ("message", "is_active", "created_by", "created_at")
    list_filter = ("is_active",)


@admin.register(DonationHistory)
class DonationHistoryAdmin(admin.ModelAdmin):
    list_display = ("donor", "request", "date", "status")
    list_filter = ("status", "date")
    search_fields = ("donor__full_name", "request__request_code", "request__requester_name")


@admin.register(BloodCamp)
class BloodCampAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "location", "created_by", "created_at")
    list_filter = ("date", "location")
    search_fields = ("title", "location", "description")
    autocomplete_fields = ("created_by",)
    inlines = [CampRegistrationInline]

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CampRegistration)
class CampRegistrationAdmin(admin.ModelAdmin):
    list_display = ("donor", "camp", "status", "registered_at")
    list_filter = ("status", "camp__date")
    search_fields = ("donor__full_name", "camp__title", "camp__location")