from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from core.utils import (
    get_client_ip,
    check_otp_rate_limit,
    increment_otp_attempts,
    clear_otp_attempts,
    generate_secure_otp,
)
from donors.models import DonorProfile
from donors.forms import OtpVerifyForm
from .forms import BloodRequestForm
from .models import BloodRequest

def request_form(request):
    if request.method == "POST":
        form = BloodRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            if request.user.is_authenticated:
                req.requester = request.user
            req.otp_verified = True
            req.save()
            messages.success(request, f"Request submitted successfully with ID {req.request_code}. Status is Pending.")
            return redirect("request_status")
    else:
        initial_data = {
            "blood_group": request.GET.get("blood_group", ""),
            "city": request.GET.get("city", ""),
        }
        form = BloodRequestForm(initial=initial_data)
    return render(request, "requests/request_form.html", {"form": form})

def request_verify_otp(request):
    return redirect("request_status")

def request_status(request):
    phone = request.GET.get("phone", "")
    phone_verified = False
    requests = []

    if request.user.is_authenticated:
        requests = BloodRequest.objects.filter(requester=request.user).order_by("-requested_at")
        phone_verified = True
    else:
        if phone:
            phone = phone.strip()
            phone_verified = True
            requests = BloodRequest.objects.filter(contact_number=phone).order_by("-requested_at")

    context = {
        "requests": requests,
        "phone_verified": phone_verified,
        "phone": phone,
    }
    return render(request, "requests/request_status.html", context)

@login_required
def donate_request(request, request_id):
    profile = get_object_or_404(DonorProfile, user=request.user)
    blood_request = get_object_or_404(BloodRequest, pk=request_id, status="APPROVED", fulfilled_by__isnull=True)

    if profile.verification_status != "APPROVED":
        messages.error(request, "Your donor profile is not approved by admin yet.")
        return redirect("donor_dashboard")

    if profile.is_in_cooldown:
        messages.error(request, f"You are in cooldown for {profile.cooldown_days_remaining} more day(s).")
        return redirect("donor_dashboard")

    if profile.blood_group != blood_request.blood_group:
        messages.error(request, "You can only donate to matching blood group requests.")
        return redirect("donor_dashboard")

    completed_now = blood_request.mark_completed(profile)
    if completed_now:
        messages.success(request, "Donation marked complete. Cooldown of 90 days has started.")
    else:
        messages.info(request, "This request is already marked as completed.")
    return redirect("donor_dashboard")
