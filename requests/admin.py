from django.contrib import admin
from django.utils.html import format_html
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
    readonly_fields = ["prescription_preview"]
    fields = [
        "requester",
        "requester_name",
        "blood_group",
        "units",
        "hospital_name",
        "blood_bank",
        "city",
        "contact_number",
        "reason",
        "priority",
        "request_code",
        "otp_code",
        "otp_verified",
        "otp_created_at",
        "status",
        "rejection_reason",
        "prescription",
        "prescription_preview",
        "approved_at",
        "assigned_donor",
        "fulfilled_by",
    ]

    def prescription_preview(self, obj):
        if obj.prescription:
            if obj.is_pdf:
                return format_html('<a href="{}" target="_blank" style="font-weight: bold; color: #2563eb; text-decoration: underline;">Download PDF</a>', obj.prescription.url)
            else:
                return format_html('<img src="{}" style="max-height: 200px; max-width: 200px; border-radius: 8px; border: 1px solid #e2e8f0;" />', obj.prescription.url)
        return "No prescription uploaded"
    prescription_preview.short_description = "Prescription Preview"

    @admin.action(description="Approve selected blood requests")
    def approve_requests(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Q
        from donors.models import DonorProfile
        from core.tasks import send_sms_async
        
        rows_updated = 0
        for req in queryset:
            req.otp_verified = True
            req.status = "APPROVED"
            req.approved_at = timezone.now()
            
            if req.assigned_donor is None:
                cooldown_limit = timezone.localdate() - timedelta(days=90)
                matching_donor = (
                    DonorProfile.objects.filter(
                        blood_group=req.blood_group,
                        city__iexact=req.city,
                        verification_status="APPROVED",
                        otp_verified=True,
                        available=True,
                    )
                    .filter(Q(last_donation_date__isnull=True) | Q(last_donation_date__lte=cooldown_limit))
                    .order_by("created_at")
                    .first()
                )
                if matching_donor:
                    req.assigned_donor = matching_donor
                    req.status = "ASSIGNED"
            
            req.save()
            
            # Send SMS alerts
            requester_msg = f"NSS Blood: Your request #{req.request_code} has been approved! We are coordinating volunteer donors."
            if req.assigned_donor:
                requester_msg = (
                    f"NSS Blood: Your request #{req.request_code} has been approved! "
                    f"Volunteer donor {req.assigned_donor.full_name} ({req.assigned_donor.phone}) "
                    f"has been assigned. Please coordinate with them."
                )
            send_sms_async.delay(req.contact_number, requester_msg)
            
            if req.assigned_donor:
                donor_msg = (
                    f"NSS Blood Emergency! You are assigned to request #{req.request_code} "
                    f"for patient {req.requester_name} ({req.blood_group}) "
                    f"at {req.hospital_name}. Contact: {req.contact_number}."
                )
                send_sms_async.delay(req.assigned_donor.phone, donor_msg)
                
            rows_updated += 1
            
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
