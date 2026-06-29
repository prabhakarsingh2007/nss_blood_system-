from django.contrib import admin
from .models import DonorProfile, BloodCamp, CampRegistration, DonationHistory

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
    actions = ["approve_donors", "mark_available", "mark_unavailable", "export_donors_as_csv"]

    @admin.action(description="Approve selected donor profiles")
    def approve_donors(self, request, queryset):
        rows_updated = queryset.update(verification_status="APPROVED", otp_verified=True)
        self.message_user(request, f"Successfully approved {rows_updated} donor profile(s).")

    @admin.action(description="Mark selected donors as Available")
    def mark_available(self, request, queryset):
        rows_updated = queryset.update(available=True)
        self.message_user(request, f"Successfully marked {rows_updated} donor(s) as Available.")

    @admin.action(description="Mark selected donors as Unavailable")
    def mark_unavailable(self, request, queryset):
        rows_updated = queryset.update(available=False)
        self.message_user(request, f"Successfully marked {rows_updated} donor(s) as Unavailable.")

    @admin.action(description="Export selected donors to CSV")
    def export_donors_as_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="volunteers_list.csv"'
        writer = csv.writer(response)
        
        # Header row
        writer.writerow(["Full Name", "Phone", "Blood Group", "City", "Age", "Gender", "Available", "Verification Status", "OTP Verified", "Created At"])
        
        for donor in queryset:
            writer.writerow([
                donor.full_name,
                donor.phone,
                donor.blood_group,
                donor.city,
                donor.age,
                donor.gender,
                "Yes" if donor.available else "No",
                donor.verification_status,
                "Yes" if donor.otp_verified else "No",
                donor.created_at.strftime("%Y-%m-%d %H:%M:%S") if donor.created_at else ""
            ])
            
        return response

@admin.register(BloodCamp)
class BloodCampAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "location", "created_by", "created_at")
    list_filter = ("date", "location")
    search_fields = ("title", "location", "description")
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

@admin.register(DonationHistory)
class DonationHistoryAdmin(admin.ModelAdmin):
    list_display = ("donor", "request", "date", "status", "nss_verified", "certificate_id", "verified_by", "verified_at")
    list_filter = ("status", "nss_verified", "date")
    search_fields = ("donor__full_name", "request__request_code", "request__requester_name")
