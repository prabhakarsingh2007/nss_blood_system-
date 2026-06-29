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
    actions = ["approve_requests", "export_requests_as_csv"]

    @admin.action(description="Approve selected blood requests")
    def approve_requests(self, request, queryset):
        rows_updated = queryset.update(status="APPROVED", otp_verified=True)
        self.message_user(request, f"Successfully approved {rows_updated} blood request(s).")

    @admin.action(description="Export selected requests to CSV")
    def export_requests_as_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="blood_requests_list.csv"'
        writer = csv.writer(response)
        
        # Header row
        writer.writerow(["Request Code", "Requester Name", "Contact Number", "Blood Group", "Units Required", "Hospital Name", "Blood Bank", "City", "Status", "Requested At"])
        
        for req in queryset:
            writer.writerow([
                req.request_code,
                req.requester_name,
                req.contact_number,
                req.blood_group,
                req.units,
                req.hospital_name,
                req.blood_bank.name if req.blood_bank else "",
                req.city,
                req.status,
                req.requested_at.strftime("%Y-%m-%d %H:%M:%S") if req.requested_at else ""
            ])
            
        return response
