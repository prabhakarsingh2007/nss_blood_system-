from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from donors.models import DonorProfile, BloodCamp, DonationHistory, log_activity, ActivityLog
from donors.forms import BloodCampForm
from requests.models import BloodRequest, Hospital, BloodBank
from requests.forms import HospitalForm, BloodBankForm
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
        "approved_requests": my_requests.filter(status__in=["APPROVED", "ASSIGNED"]).count(),
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
            Q(status="APPROVED") | Q(status="ASSIGNED", assigned_donor=profile),
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

    blood_bank_name = request.POST.get("blood_bank", "").strip()
    if blood_bank_name:
        req.blood_bank = blood_bank_name
        req.save(update_fields=["blood_bank"])

    if new_status in {"APPROVED", "ASSIGNED", "REJECTED", "COMPLETED"} and not req.otp_verified:
        req.otp_verified = True
        req.save(update_fields=["otp_verified"])
        messages.info(request, "OTP was not verified, so admin override verification was applied.")

    if new_status in {"PENDING", "APPROVED", "ASSIGNED", "REJECTED", "COMPLETED"}:
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
                    req.status = "ASSIGNED"

            req.save(update_fields=["status", "approved_at", "assigned_donor"])
            messages.success(request, "Request status updated.")
            if req.assigned_donor:
                log_activity(request.user, "REQUEST_DECISION", f"Approved request #{req.request_code} and assigned donor {req.assigned_donor.full_name}.")
            else:
                log_activity(request.user, "REQUEST_DECISION", f"Approved request #{req.request_code} (no matching donor found).")
            
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

        elif new_status == "ASSIGNED":
            req.status = new_status
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
                    req.save(update_fields=["status", "assigned_donor"])
                    messages.success(request, "Request status updated and donor assigned.")
                    log_activity(request.user, "REQUEST_DECISION", f"Assigned donor {req.assigned_donor.full_name} to request #{req.request_code}.")
                    
                    # Send SMS alerts
                    requester_msg = (
                        f"NSS Blood: Your request #{req.request_code} has been approved! "
                        f"Volunteer donor {req.assigned_donor.full_name} ({req.assigned_donor.phone}) "
                        f"has been assigned. Please coordinate with them."
                    )
                    send_sms_async.delay(req.contact_number, requester_msg)
                    
                    donor_msg = (
                        f"NSS Blood Emergency! You are assigned to request #{req.request_code} "
                        f"for patient {req.requester_name} ({req.blood_group}) "
                        f"at {req.hospital_name}. Contact: {req.contact_number}."
                )
                    send_sms_async.delay(req.assigned_donor.phone, donor_msg)
                else:
                    messages.warning(request, "No matching volunteer donor found to assign.")
                    req.status = "APPROVED"
                    req.save(update_fields=["status"])
                    log_activity(request.user, "REQUEST_DECISION", f"Updated request #{req.request_code} status to Approved (no matching donor found to assign).")
            else:
                req.save(update_fields=["status"])
                messages.success(request, "Request status updated.")
                log_activity(request.user, "REQUEST_DECISION", f"Updated request #{req.request_code} status to Assigned.")

        elif new_status == "COMPLETED":
            donor = req.assigned_donor or req.fulfilled_by
            if donor:
                completed_now = req.mark_completed(donor)
                if completed_now:
                    messages.success(request, "Request marked completed and donor history updated.")
                    log_activity(request.user, "DONATION_COMPLETE", f"Marked request #{req.request_code} as completed (fulfilled by donor {donor.full_name}).")
                    completed_msg = f"NSS Blood: Your request #{req.request_code} has been successfully completed. Thank you!"
                    send_sms_async.delay(req.contact_number, completed_msg)
                else:
                    messages.info(request, "Request was already completed.")
            else:
                req.status = "COMPLETED"
                req.save(update_fields=["status"])
                messages.warning(request, "Request marked completed without a donor assignment.")
                log_activity(request.user, "DONATION_COMPLETE", f"Marked request #{req.request_code} as completed (no donor assignment).")
        elif new_status == "REJECTED":
            req.status = new_status
            rejection_reason = request.POST.get("rejection_reason", "").strip()
            req.rejection_reason = rejection_reason or "Does not meet emergency criteria."
            req.save(update_fields=["status", "rejection_reason"])
            messages.success(request, "Request status updated to Rejected.")
            log_activity(request.user, "REQUEST_DECISION", f"Rejected request #{req.request_code}. Reason: {req.rejection_reason}")
            
            rejection_msg = f"NSS Blood: Your request #{req.request_code} has been rejected. Reason: {req.rejection_reason}"
            send_sms_async.delay(req.contact_number, rejection_msg)
        else:
            req.status = new_status
            req.save(update_fields=["status"])
            messages.success(request, "Request status updated.")
            log_activity(request.user, "REQUEST_DECISION", f"Updated request #{req.request_code} status to {new_status}.")


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
        log_activity(request.user, "DONOR_VERIFICATION", f"Updated donor {donor.full_name} verification status to {decision}.")

def _handle_admin_broadcast_create(request):
    form = BroadcastMessageForm(request.POST)
    if form.is_valid():
        broadcast = form.save(commit=False)
        broadcast.created_by = request.user
        broadcast.save()

        messages.success(request, "Mass message published.")
        log_activity(request.user, "BROADCAST_ACTION", f"Published mass message: '{broadcast.message[:50]}...'.")
        return True
    return False

def _handle_admin_camp_create(request):
    form = BloodCampForm(request.POST)
    if form.is_valid():
        camp = form.save(commit=False)
        camp.created_by = request.user
        camp.save()
        messages.success(request, "Blood camp created successfully.")
        log_activity(request.user, "CAMP_ACTION", f"Scheduled blood camp: '{camp.title}' on {camp.date} at {camp.location}.")
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
            log_activity(request.user, "DONATION_COMPLETE", f"NSS verified donation audit for donor {donation_history.donor.full_name} (Request #{donation_history.request.request_code}) and generated certificate {donation_history.certificate_id}.")
        else:
            messages.info(request, f"Already NSS verified. Certificate {donation_history.certificate_id} is available.")

def _handle_admin_hospital_create(request):
    form = HospitalForm(request.POST)
    if form.is_valid():
        h = form.save()
        messages.success(request, "Hospital added successfully.")
        log_activity(request.user, "HOSPITAL_ACTION", f"Created hospital: '{h.name}' in {h.city}.")
        return True
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.capitalize()}: {error}")
    return False

def _handle_admin_hospital_update(request):
    hospital_id = request.POST.get("hospital_id")
    hospital = get_object_or_404(Hospital, pk=hospital_id)
    form = HospitalForm(request.POST, instance=hospital)
    if form.is_valid():
        form.save()
        messages.success(request, f"Hospital '{hospital.name}' updated successfully.")
        log_activity(request.user, "HOSPITAL_ACTION", f"Updated hospital details for '{hospital.name}' ({hospital.city}).")
        return True
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.capitalize()}: {error}")
    return False

def _handle_admin_hospital_toggle(request):
    hospital_id = request.POST.get("hospital_id")
    hospital = get_object_or_404(Hospital, pk=hospital_id)
    hospital.is_active = not hospital.is_active
    hospital.save(update_fields=["is_active"])
    status_str = "activated" if hospital.is_active else "deactivated"
    messages.success(request, f"Hospital '{hospital.name}' has been {status_str}.")
    log_activity(request.user, "HOSPITAL_ACTION", f"Toggled status of hospital '{hospital.name}' to {status_str}.")
    return True


def _handle_admin_blood_bank_create(request):
    form = BloodBankForm(request.POST)
    if form.is_valid():
        b = form.save()
        messages.success(request, "Blood Bank added successfully.")
        log_activity(request.user, "BLOOD_BANK_ACTION", f"Created blood bank: '{b.name}' in {b.city}.")
        return True
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.capitalize()}: {error}")
    return False


def _handle_admin_blood_bank_update(request):
    bank_id = request.POST.get("blood_bank_id")
    bank = get_object_or_404(BloodBank, pk=bank_id)
    form = BloodBankForm(request.POST, instance=bank)
    if form.is_valid():
        form.save()
        messages.success(request, f"Blood Bank '{bank.name}' updated successfully.")
        log_activity(request.user, "BLOOD_BANK_ACTION", f"Updated blood bank details for '{bank.name}' ({bank.city}).")
        return True
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.capitalize()}: {error}")
    return False


def _handle_admin_blood_bank_toggle(request):
    bank_id = request.POST.get("blood_bank_id")
    bank = get_object_or_404(BloodBank, pk=bank_id)
    bank.is_active = not bank.is_active
    bank.save(update_fields=["is_active"])
    status_str = "activated" if bank.is_active else "deactivated"
    messages.success(request, f"Blood Bank '{bank.name}' has been {status_str}.")
    log_activity(request.user, "BLOOD_BANK_ACTION", f"Toggled status of blood bank '{bank.name}' to {status_str}.")
    return True


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect("dashboard_router")

    broadcast_form = BroadcastMessageForm()
    camp_form = BloodCampForm()
    hospital_form = HospitalForm()
    blood_bank_form = BloodBankForm()
    selected_blood_group = request.GET.get("blood_group", "")
    selected_city = request.GET.get("city", "")
    selected_start_date = request.GET.get("start_date", "")
    selected_end_date = request.GET.get("end_date", "")

    activity_start_date = request.GET.get("activity_start_date", "")
    activity_end_date = request.GET.get("activity_end_date", "")
    activity_type = request.GET.get("activity_type", "")
    activity_search = request.GET.get("activity_search", "")

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

        elif action == "hospital_create":
            if _handle_admin_hospital_create(request):
                return redirect(f"{reverse('admin_dashboard')}#manage-hospitals")

        elif action == "hospital_update":
            if _handle_admin_hospital_update(request):
                return redirect(f"{reverse('admin_dashboard')}#manage-hospitals")

        elif action == "hospital_toggle":
            _handle_admin_hospital_toggle(request)
            return redirect(f"{reverse('admin_dashboard')}#manage-hospitals")

        elif action == "blood_bank_create":
            if _handle_admin_blood_bank_create(request):
                return redirect(f"{reverse('admin_dashboard')}#manage-blood-banks")

        elif action == "blood_bank_update":
            if _handle_admin_blood_bank_update(request):
                return redirect(f"{reverse('admin_dashboard')}#manage-blood-banks")

        elif action == "blood_bank_toggle":
            _handle_admin_blood_bank_toggle(request)
            return redirect(f"{reverse('admin_dashboard')}#manage-blood-banks")

    hospitals = Hospital.objects.all().order_by("name")
    blood_banks_all = BloodBank.objects.all().order_by("name")
    donor_queryset = DonorProfile.objects.select_related("user").order_by("-created_at")
    request_queryset = BloodRequest.objects.select_related("requester", "assigned_donor", "fulfilled_by").order_by("-requested_at")

    if selected_blood_group:
        donor_queryset = donor_queryset.filter(blood_group=selected_blood_group)
        request_queryset = request_queryset.filter(blood_group=selected_blood_group)

    if selected_city:
        donor_queryset = donor_queryset.filter(city__iexact=selected_city)
        request_queryset = request_queryset.filter(city__iexact=selected_city)

    if selected_start_date:
        donor_queryset = donor_queryset.filter(created_at__date__gte=selected_start_date)
        request_queryset = request_queryset.filter(requested_at__date__gte=selected_start_date)

    if selected_end_date:
        donor_queryset = donor_queryset.filter(created_at__date__lte=selected_end_date)
        request_queryset = request_queryset.filter(requested_at__date__lte=selected_end_date)

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

    activity_logs = ActivityLog.objects.select_related("user").all()

    if activity_start_date:
        activity_logs = activity_logs.filter(created_at__date__gte=activity_start_date)
    if activity_end_date:
        activity_logs = activity_logs.filter(created_at__date__lte=activity_end_date)
    if activity_type:
        activity_logs = activity_logs.filter(activity_type=activity_type)
    if activity_search:
        activity_logs = activity_logs.filter(
            Q(details__icontains=activity_search) | 
            Q(user_name__icontains=activity_search) |
            Q(activity_type__icontains=activity_search)
        )

    ACTIVITY_TYPES = [
        ("BLOOD_REQUEST", "New Blood Requests"),
        ("DONATION_COMPLETE", "Completed Donations"),
        ("DONOR_REGISTER", "New Donor Registrations"),
        ("DONOR_VERIFICATION", "Donor Verification"),
        ("HOSPITAL_ACTION", "Hospital Add/Edit/Delete"),
        ("BLOOD_BANK_ACTION", "Blood Bank Add/Edit/Delete"),
        ("CAMP_ACTION", "Blood Camp Activities"),
        ("BROADCAST_ACTION", "Mass Message"),
        ("ADMIN_LOGIN", "Admin Login History"),
        ("REQUEST_DECISION", "Request Approvals/Rejections"),
    ]

    context = {
        "total_donors": approved_donor_queryset.count(),
        "total_requests": request_queryset.count(),
        "pending_requests": request_queryset.filter(status="PENDING").count(),
        "emergency_requests": request_queryset.filter(status="PENDING", is_emergency=True).count(),
        "requests": request_queryset[:30],
        "donors": donor_queryset[:25],
        "broadcast_form": broadcast_form,
        "camp_form": camp_form,
        "hospital_form": hospital_form,
        "blood_bank_form": blood_bank_form,
        "hospitals": hospitals,
        "blood_banks_all": blood_banks_all,
        "camps": camps,
        "recent_donations": recent_donations,
        "blood_groups": DonorProfile.BLOOD_GROUP_CHOICES,
        "blood_banks": BloodBank.objects.filter(is_active=True).order_by("name"),
        "cities": cities,
        "selected_blood_group": selected_blood_group,
        "selected_city": selected_city,
        "selected_start_date": selected_start_date,
        "selected_end_date": selected_end_date,
        "blood_group_summary": blood_group_summary,
        "requests_per_day_labels": requests_per_day_labels,
        "requests_per_day_values": requests_per_day_values,
        "donors_by_group_labels": donors_by_group_labels,
        "donors_by_group_values": donors_by_group_values,
        
        "activity_logs": activity_logs[:200],
        "activity_types": ACTIVITY_TYPES,
        "selected_activity_start_date": activity_start_date,
        "selected_activity_end_date": activity_end_date,
        "selected_activity_type": activity_type,
        "selected_activity_search": activity_search,
    }
    return render(request, "dashboard/admin_dashboard.html", context)
