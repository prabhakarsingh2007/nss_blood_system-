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
            otp_code = req.generate_otp()
            req.save()
            request.session["request_otp_request_id"] = req.id
            messages.info(request, f"Demo OTP for request verification: {otp_code}")
            return redirect("request_verify_otp")
    else:
        initial_data = {
            "blood_group": request.GET.get("blood_group", ""),
            "city": request.GET.get("city", ""),
        }
        form = BloodRequestForm(initial=initial_data)
    return render(request, "requests/request_form.html", {"form": form})

def request_verify_otp(request):
    req_id = request.session.get("request_otp_request_id")
    if not req_id:
        messages.error(request, "No pending request OTP verification found.")
        return redirect("request_form")

    blood_req = get_object_or_404(BloodRequest, pk=req_id)

    # Enforce OTP Verification Rate Limit
    client_ip = get_client_ip(request)
    action_key = f"request_verify_{req_id}"
    is_allowed, info = check_otp_rate_limit(client_ip, action_key)
    if not is_allowed:
        messages.error(request, f"Too many verification attempts. Locked out for {info} seconds.")
        return render(request, "requests/request_verify_otp.html", {"form": OtpVerifyForm()})

    if request.method == "POST":
        form = OtpVerifyForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data["otp"]
            if blood_req.otp_is_valid(otp):
                blood_req.otp_verified = True
                blood_req.save(update_fields=["otp_verified"])
                request.session.pop("request_otp_request_id", None)
                clear_otp_attempts(client_ip, action_key)
                messages.success(request, f"Request submitted with ID {blood_req.request_code}. Status is Pending.")
                return redirect("request_status")
            else:
                increment_otp_attempts(client_ip, action_key)
                messages.error(request, "Invalid or expired OTP.")
    else:
        form = OtpVerifyForm()

    return render(request, "requests/request_verify_otp.html", {"form": form})

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
            session_verified_phone = request.session.get("verified_status_phone", "")
            if session_verified_phone == phone:
                phone_verified = True
                requests = BloodRequest.objects.filter(contact_number=phone).order_by("-requested_at")
            else:
                requests = BloodRequest.objects.filter(contact_number=phone).order_by("-requested_at")
                if requests.exists():
                    if request.session.get("status_search_phone") != phone or "status_search_otp" not in request.session:
                        otp = generate_secure_otp(6)
                        request.session["status_search_otp"] = otp
                        request.session["status_search_phone"] = phone
                        messages.info(request, f"Demo OTP for search verification: {otp}")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "verify_search_otp":
            saved_phone = request.session.get("status_search_phone")
            
            # Enforce Rate Limit for Search OTP
            client_ip = get_client_ip(request)
            action_key = f"search_verify_{saved_phone or 'unknown'}"
            is_allowed, info = check_otp_rate_limit(client_ip, action_key)
            if not is_allowed:
                messages.error(request, f"Too many verification attempts. Locked out for {info} seconds.")
                if saved_phone:
                    phone = saved_phone
                    requests = BloodRequest.objects.filter(contact_number=phone).order_by("-requested_at")
            else:
                otp_entered = request.POST.get("otp", "").strip()
                saved_otp = request.session.get("status_search_otp")
                
                if saved_otp and saved_otp == otp_entered:
                    request.session["verified_status_phone"] = saved_phone
                    request.session.pop("status_search_otp", None)
                    clear_otp_attempts(client_ip, action_key)
                    messages.success(request, "Phone number verified successfully. Access granted to details.")
                    return redirect(f"{reverse('request_status')}?phone={saved_phone}")
                else:
                    increment_otp_attempts(client_ip, action_key)
                    messages.error(request, "Invalid search OTP. Please try again.")
                    if saved_phone:
                        phone = saved_phone
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
