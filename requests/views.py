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
from core.tasks import send_sms_async

def request_form(request):
    if request.method == "POST":
        form = BloodRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            if request.user.is_authenticated:
                req.requester = request.user
                req.otp_verified = True
                req.save()
                messages.success(request, f"Request submitted successfully. Status is Pending.")
                return redirect(reverse("request_status") + f"?code={req.request_code}&phone={req.contact_number}")
            
            # For guests, generate OTP and redirect to verification view
            req.otp_verified = False
            req.save()
            otp = req.generate_otp()
            req.save(update_fields=["otp_code", "otp_verified", "otp_created_at"])
            
            # Send OTP SMS
            submit_msg = f"NSS Blood: Your request verification OTP is {otp}. Expiry: 10 mins."
            send_sms_async.delay(req.contact_number, submit_msg)
            
            request.session['pending_request_code'] = req.request_code
            messages.info(request, "Please verify the 6-digit OTP sent to your phone.")
            return redirect("request_verify_otp")
    else:
        initial_data = {
            "blood_group": request.GET.get("blood_group", ""),
            "city": request.GET.get("city", ""),
        }
        form = BloodRequestForm(initial=initial_data)
    return render(request, "requests/request_form.html", {"form": form})

def request_verify_otp(request):
    req_code = request.session.get('pending_request_code')
    if not req_code:
        messages.error(request, "No pending request found to verify.")
        return redirect("home")
        
    req = get_object_or_404(BloodRequest, request_code=req_code)
    
    if request.method == "POST":
        form = OtpVerifyForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data.get("otp").strip()
            ip = get_client_ip(request)
            action_key = f"req_otp_{req.request_code}"
            
            # Check rate limit
            is_allowed, remaining = check_otp_rate_limit(ip, action_key)
            if not is_allowed:
                form.add_error(None, f"Too many failed attempts. Locked out. Please try again after {remaining} seconds.")
                return render(request, "requests/request_verify_otp.html", {"form": form})
                
            # Verify OTP
            if req.otp_is_valid(otp_code):
                req.otp_verified = True
                req.save(update_fields=["otp_verified"])
                clear_otp_attempts(ip, action_key)
                
                # Delete session key
                del request.session['pending_request_code']
                
                messages.success(request, "Request verified and activated successfully!")
                return redirect(reverse("request_status") + f"?code={req.request_code}&phone={req.contact_number}")
            else:
                increment_otp_attempts(ip, action_key)
                form.add_error("otp", "Invalid or expired OTP code.")
    else:
        form = OtpVerifyForm()
        
    return render(request, "requests/request_verify_otp.html", {"form": form})

def request_status(request):
    code = request.GET.get("code", "").strip()
    phone = request.GET.get("phone", "").strip()
    phone_verified = False
    requests = []

    if code and phone:
        requests = BloodRequest.objects.filter(request_code=code, contact_number=phone).select_related("assigned_donor", "fulfilled_by").order_by("-requested_at")
        phone_verified = True
    elif request.user.is_authenticated:
        requests = BloodRequest.objects.filter(requester=request.user).select_related("assigned_donor", "fulfilled_by").order_by("-requested_at")
        phone_verified = True
    elif phone:
        phone_verified = True
        requests = BloodRequest.objects.filter(contact_number=phone).select_related("assigned_donor", "fulfilled_by").order_by("-requested_at")

    context = {
        "requests": requests,
        "phone_verified": phone_verified,
        "phone": phone,
        "code": code,
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
