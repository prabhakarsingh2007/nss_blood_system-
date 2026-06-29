from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from donors.models import DonorProfile, BloodCamp, DonationHistory
from donors.forms import BloodCampForm
from requests.models import BloodRequest
from .models import BroadcastMessage
from .forms import BroadcastMessageForm
from core.tasks import send_sms_async

@login_required
def dashboard_router(request):
    if request.user.is_staff:
        return redirect("admin_dashboard")
    if DonorProfile.objects.filter(user=request.user).exists():
        return redirect("donor_dashboard")
    return redirect("user_dashboard")

@login_required
def user_dashboard(request):
    my_requests = BloodRequest.objects.filter(requester=request.user).select_related("assigned_donor", "fulfilled_by").order_by("-requested_at")
    context = {
        "my_requests": my_requests[:20],
        "total_requests": my_requests.count(),
        "pending_requests": my_requests.filter(status="PENDING").count(),
        "approved_requests": my_requests.filter(status="APPROVED").count(),
        "completed_requests": my_requests.filter(status="COMPLETED").count(),
    }
    return render(request, "dashboard/user_dashboard.html", context)


@login_required
def donor_dashboard(request):
    profile = DonorProfile.objects.filter(user=request.user).first()
    if not profile:
        messages.info(request, "Please complete donor registration first.")
        return redirect("donor_register")

    donations_qs = DonationHistory.objects.filter(donor=profile)
    past_donations = donations_qs.select_related("request")[:20]

    open_requests = []
    can_donate_now = profile.is_active_donor
    next_available_on = None

    if profile.last_donation_date and profile.is_in_cooldown:
        next_available_on = profile.last_donation_date + timedelta(days=90)

    if profile.verification_status == "APPROVED":
        open_requests = BloodRequest.objects.select_related("requester").filter(
            status="APPROVED",
            blood_group=profile.blood_group,
            city__iexact=profile.city,
            fulfilled_by__isnull=True,
        ).order_by("-requested_at")[:20]

    return render(
        request,
        "donors/donor_dashboard.html",
        {
            "profile": profile,
            "past_donations": past_donations,
            "verified_donation_count": donations_qs.filter(nss_verified=True).count(),
            "total_donations": profile.donation_count,
            "current_rating": profile.rating,
            "open_requests": open_requests,
            "can_donate_now": can_donate_now,
            "next_available_on": next_available_on,
        },
    )

def _handle_admin_request_status(request):
    req_id = request.POST.get("request_id")
    new_status = request.POST.get("status")
    req = get_object_or_404(BloodRequest, pk=req_id)

    if new_status in {"APPROVED", "REJECTED", "COMPLETED"} and not req.otp_verified:
        req.otp_verified = True
        req.save(update_fields=["otp_verified"])
        messages.info(request, "OTP was not verified, so admin override verification was applied.")

    if new_status in {"PENDING", "APPROVED", "REJECTED", "COMPLETED"}:
        if new_status == "APPROVED":
            req.status = new_status
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

            req.save(update_fields=["status", "approved_at", "assigned_donor"])
            messages.success(request, "Request status updated.")
            
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

        elif new_status == "COMPLETED":
            donor = req.assigned_donor or req.fulfilled_by
            if donor:
                completed_now = req.mark_completed(donor)
                if completed_now:
                    messages.success(request, "Request marked completed and donor history updated.")
                    completed_msg = f"NSS Blood: Your request #{req.request_code} has been successfully completed. Thank you!"
                    send_sms_async.delay(req.contact_number, completed_msg)
                else:
                    messages.info(request, "Request was already completed.")
            else:
                req.status = "COMPLETED"
                req.save(update_fields=["status"])
                messages.warning(request, "Request marked completed without a donor assignment.")
        elif new_status == "REJECTED":
            req.status = new_status
            rejection_reason = request.POST.get("rejection_reason", "").strip()
            req.rejection_reason = rejection_reason or "Does not meet emergency criteria."
            req.save(update_fields=["status", "rejection_reason"])
            messages.success(request, "Request status updated to Rejected.")
            
            rejection_msg = f"NSS Blood: Your request #{req.request_code} has been rejected. Reason: {req.rejection_reason}"
            send_sms_async.delay(req.contact_number, rejection_msg)
        else:
            req.status = new_status
            req.save(update_fields=["status"])
            messages.success(request, "Request status updated.")

def _handle_admin_donor_verify(request):
    donor_id = request.POST.get("donor_id")
    decision = request.POST.get("verification_status")
    donor = get_object_or_404(DonorProfile, pk=donor_id)

    if decision in {"APPROVED", "REJECTED"} and not donor.otp_verified:
        donor.otp_verified = True
        donor.save(update_fields=["otp_verified"])
        messages.info(request, "Donor OTP was missing, admin override verification applied.")

    if decision in {"PENDING", "APPROVED", "REJECTED"}:
        donor.verification_status = decision
        donor.save(update_fields=["verification_status"])
        messages.success(request, "Donor verification updated.")

def _handle_admin_broadcast_create(request):
    form = BroadcastMessageForm(request.POST)
    if form.is_valid():
        broadcast = form.save(commit=False)
        broadcast.created_by = request.user
        broadcast.save()
        messages.success(request, "Mass message published.")
        return True
    return False

def _handle_admin_camp_create(request):
    form = BloodCampForm(request.POST)
    if form.is_valid():
        camp = form.save(commit=False)
        camp.created_by = request.user
        camp.save()
        messages.success(request, "Blood camp created successfully.")
        return True
    return False

def _handle_admin_nss_verify_donation(request):
    history_id = request.POST.get("history_id")
    donation_history = get_object_or_404(DonationHistory, pk=history_id)
    if donation_history.status != DonationHistory.STATUS_SUCCESS:
        messages.error(request, "Only successful donations can be NSS verified.")
    else:
        verified_now = donation_history.verify_by_nss(request.user)
        if verified_now:
            messages.success(request, f"NSS verification completed. Certificate {donation_history.certificate_id} generated.")
        else:
            messages.info(request, f"Already NSS verified. Certificate {donation_history.certificate_id} is available.")

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect("dashboard_router")

    broadcast_form = BroadcastMessageForm()
    camp_form = BloodCampForm()
    selected_blood_group = request.GET.get("blood_group", "")
    selected_city = request.GET.get("city", "")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "request_status":
            _handle_admin_request_status(request)
            return redirect(f"{reverse('admin_dashboard')}#verify-requests")

        elif action == "donor_verify":
            _handle_admin_donor_verify(request)
            return redirect(f"{reverse('admin_dashboard')}#verify-donors")

        elif action == "broadcast_create":
            if _handle_admin_broadcast_create(request):
                return redirect(f"{reverse('admin_dashboard')}#mass-message")

        elif action == "camp_create":
            if _handle_admin_camp_create(request):
                return redirect(f"{reverse('admin_dashboard')}#manage-camps")

        elif action == "nss_verify_donation":
            _handle_admin_nss_verify_donation(request)
            return redirect(f"{reverse('admin_dashboard')}#verify-donations")

    donor_queryset = DonorProfile.objects.select_related("user").order_by("-created_at")
    request_queryset = BloodRequest.objects.select_related("requester", "assigned_donor", "fulfilled_by").order_by("-requested_at")

    if selected_blood_group:
        donor_queryset = donor_queryset.filter(blood_group=selected_blood_group)
        request_queryset = request_queryset.filter(blood_group=selected_blood_group)

    if selected_city:
        donor_queryset = donor_queryset.filter(city__iexact=selected_city)
        request_queryset = request_queryset.filter(city__iexact=selected_city)

    approved_donor_queryset = donor_queryset.filter(verification_status="APPROVED")

    today = timezone.localdate()
    start_date = today - timedelta(days=6)

    requests_per_day_qs = (
        request_queryset.filter(requested_at__date__gte=start_date)
        .annotate(day=TruncDate("requested_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )
    requests_per_day_map = {item["day"]: item["total"] for item in requests_per_day_qs}

    requests_per_day_labels = []
    requests_per_day_values = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        requests_per_day_labels.append(day.strftime("%d %b"))
        requests_per_day_values.append(requests_per_day_map.get(day, 0))

    donor_group_counts = {
        item["blood_group"]: item["total"]
        for item in approved_donor_queryset.values("blood_group").annotate(total=Count("id"))
    }
    donors_by_group_labels = [label for value, label in DonorProfile.BLOOD_GROUP_CHOICES]
    donors_by_group_values = [donor_group_counts.get(value, 0) for value, _ in DonorProfile.BLOOD_GROUP_CHOICES]

    cities = sorted(
        {
            city
            for city in list(DonorProfile.objects.values_list("city", flat=True))
            + list(BloodRequest.objects.values_list("city", flat=True))
            if city
        }
    )

    camps = BloodCamp.objects.annotate(registered_count=Count("registrations", distinct=True)).order_by("-date", "-created_at")[:10]
    recent_donations = DonationHistory.objects.select_related("donor", "request", "verified_by").order_by("-date")[:30]

    cooldown_limit = timezone.localdate() - timedelta(days=90)
    
    donor_aggregates = DonorProfile.objects.values("blood_group").annotate(
        total=Count("id"),
        active=Count("id", filter=Q(
            verification_status="APPROVED",
            otp_verified=True,
            available=True
        ) & (Q(last_donation_date__isnull=True) | Q(last_donation_date__lte=cooldown_limit)))
    )
    donor_aggregates_map = {item["blood_group"]: item for item in donor_aggregates}
    
    request_aggregates = BloodRequest.objects.filter(status="PENDING").values("blood_group").annotate(
        total=Count("id")
    )
    request_aggregates_map = {item["blood_group"]: item["total"] for item in request_aggregates}

    blood_group_summary = []
    for group_value, group_label in DonorProfile.BLOOD_GROUP_CHOICES:
        donor_stats = donor_aggregates_map.get(group_value, {})
        blood_group_summary.append(
            {
                "value": group_value,
                "label": group_label,
                "donor_count": donor_stats.get("total", 0),
                "active_donor_count": donor_stats.get("active", 0),
                "pending_request_count": request_aggregates_map.get(group_value, 0),
            }
        )

    context = {
        "total_donors": approved_donor_queryset.count(),
        "total_requests": request_queryset.count(),
        "pending_requests": request_queryset.filter(status="PENDING").count(),
        "emergency_requests": request_queryset.filter(status="PENDING", is_emergency=True).count(),
        "requests": request_queryset[:30],
        "donors": donor_queryset[:25],
        "broadcast_form": broadcast_form,
        "camp_form": camp_form,
        "camps": camps,
        "recent_donations": recent_donations,
        "blood_groups": DonorProfile.BLOOD_GROUP_CHOICES,
        "cities": cities,
        "selected_blood_group": selected_blood_group,
        "selected_city": selected_city,
        "blood_group_summary": blood_group_summary,
        "requests_per_day_labels": requests_per_day_labels,
        "requests_per_day_values": requests_per_day_values,
        "donors_by_group_labels": donors_by_group_labels,
        "donors_by_group_values": donors_by_group_values,
    }
    return render(request, "dashboard/admin_dashboard.html", context)
