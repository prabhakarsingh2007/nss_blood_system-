from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import BloodCampForm, BloodRequestForm, BroadcastMessageForm, DonorProfileForm, OtpVerifyForm, UserRegisterForm
from .models import BloodRequest, BroadcastMessage, CampRegistration, BloodCamp, DonationHistory, DonorProfile


BIHAR_DISTRICTS = [
    "Araria",
    "Arwal",
    "Aurangabad",
    "Banka",
    "Begusarai",
    "Bhagalpur",
    "Bhojpur",
    "Buxar",
    "Darbhanga",
    "East Champaran",
    "Gaya",
    "Gopalganj",
    "Jamui",
    "Jehanabad",
    "Kaimur",
    "Katihar",
    "Khagaria",
    "Kishanganj",
    "Lakhisarai",
    "Madhepura",
    "Madhubani",
    "Munger",
    "Muzaffarpur",
    "Nalanda",
    "Nawada",
    "Patna",
    "Purnia",
    "Rohtas",
    "Saharsa",
    "Samastipur",
    "Saran",
    "Sheikhpura",
    "Sheohar",
    "Sitamarhi",
    "Siwan",
    "Supaul",
    "Vaishali",
    "West Champaran",
]


def home(request):
    context = {
        "donor_count": DonorProfile.objects.filter(verification_status="APPROVED").count(),
        "active_requests": BloodRequest.objects.filter(status="PENDING").count(),
        "broadcast_messages": BroadcastMessage.objects.filter(is_active=True)[:5],
    }
    return render(request, "blooddonation/home.html", context)


def search_donors(request):
    blood_group = request.GET.get("blood_group", "")
    city = request.GET.get("city", "")
    context = {
        "blood_groups": DonorProfile.BLOOD_GROUP_CHOICES,
        "cities": BIHAR_DISTRICTS,
        "selected_blood_group": blood_group,
        "selected_city": city,
    }
    return render(request, "blooddonation/search.html", context)


def donor_list(request):
    blood_group = request.GET.get("blood_group", "")
    city = request.GET.get("city", "")

    donors = DonorProfile.objects.filter(verification_status="APPROVED", otp_verified=True).order_by("-created_at")
    if blood_group:
        donors = donors.filter(blood_group=blood_group)
    if city:
        donors = donors.filter(city__icontains=city)

    donors = [
        {
            "full_name": donor.full_name,
            "blood_group": donor.blood_group,
            "city": donor.city,
            "is_available": donor.is_active_donor,
        }
        for donor in donors
    ]

    context = {
        "donors": donors,
        "blood_group": blood_group,
        "city": city,
    }
    return render(request, "blooddonation/donor_list.html", context)


def register(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("user_dashboard")
    else:
        form = UserRegisterForm()
    return render(request, "blooddonation/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("admin_dashboard")
        if DonorProfile.objects.filter(user=request.user).exists():
            return redirect("donor_dashboard")
        return redirect("user_dashboard")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_staff:
                return redirect("admin_dashboard")
            if DonorProfile.objects.filter(user=user).exists():
                return redirect("donor_dashboard")
            return redirect("user_dashboard")
        messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, "blooddonation/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("home")


@login_required
def dashboard_router(request):
    if request.user.is_staff:
        return redirect("admin_dashboard")
    if DonorProfile.objects.filter(user=request.user).exists():
        return redirect("donor_dashboard")
    return redirect("user_dashboard")


@login_required
def user_dashboard(request):
    my_requests = BloodRequest.objects.filter(requester=request.user).order_by("-requested_at")
    context = {
        "my_requests": my_requests[:20],
        "total_requests": my_requests.count(),
        "pending_requests": my_requests.filter(status="PENDING").count(),
        "approved_requests": my_requests.filter(status="APPROVED").count(),
        "completed_requests": my_requests.filter(status="COMPLETED").count(),
    }
    return render(request, "blooddonation/user_dashboard.html", context)


def donor_register(request):
    profile = DonorProfile.objects.filter(user=request.user).first() if request.user.is_authenticated else None

    if not request.user.is_authenticated:
        return render(request, "blooddonation/donor_register.html", {"form": None, "public_page": True})

    if request.method == "POST":
        form = DonorProfileForm(request.POST, instance=profile)
        if form.is_valid():
            donor = form.save(commit=False)
            donor.user = request.user
            if profile is None:
                donor.verification_status = "PENDING"
            otp_code = donor.generate_otp()
            donor.save()
            request.session["donor_otp_profile_id"] = donor.id
            messages.info(request, f"Demo OTP for donor verification: {otp_code}")
            return redirect("donor_verify_otp")
    else:
        form = DonorProfileForm(instance=profile)
    return render(request, "blooddonation/donor_register.html", {"form": form, "public_page": False})


@login_required
def donor_verify_otp(request):
    profile_id = request.session.get("donor_otp_profile_id")
    if not profile_id:
        messages.error(request, "No pending donor OTP verification found.")
        return redirect("donor_register")

    donor = get_object_or_404(DonorProfile, pk=profile_id, user=request.user)

    if request.method == "POST":
        form = OtpVerifyForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data["otp"]
            if donor.otp_is_valid(otp):
                donor.otp_verified = True
                donor.save(update_fields=["otp_verified"])
                request.session.pop("donor_otp_profile_id", None)
                messages.success(request, "Donor OTP verified. Profile sent for admin verification.")
                return redirect("donor_dashboard")
            messages.error(request, "Invalid or expired OTP.")
    else:
        form = OtpVerifyForm()

    return render(request, "blooddonation/donor_verify_otp.html", {"form": form})


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
    return render(request, "blooddonation/request_form.html", {"form": form})


def request_verify_otp(request):
    req_id = request.session.get("request_otp_request_id")
    if not req_id:
        messages.error(request, "No pending request OTP verification found.")
        return redirect("request_form")

    blood_req = get_object_or_404(BloodRequest, pk=req_id)

    if request.method == "POST":
        form = OtpVerifyForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data["otp"]
            if blood_req.otp_is_valid(otp):
                blood_req.otp_verified = True
                blood_req.save(update_fields=["otp_verified"])
                request.session.pop("request_otp_request_id", None)
                messages.success(request, f"Request submitted with ID {blood_req.request_code}. Status is Pending.")
                return redirect("request_status")
            messages.error(request, "Invalid or expired OTP.")
    else:
        form = OtpVerifyForm()

    return render(request, "blooddonation/request_verify_otp.html", {"form": form})


def request_status(request):
    if request.user.is_authenticated:
        requests = BloodRequest.objects.filter(requester=request.user).order_by("-requested_at")
    else:
        phone = request.GET.get("phone", "")
        requests = BloodRequest.objects.filter(contact_number=phone).order_by("-requested_at") if phone else []
    return render(request, "blooddonation/request_status.html", {"requests": requests})


def camp_list(request):
    today = timezone.localdate()
    camps = (
        BloodCamp.objects.filter(date__gte=today)
        .annotate(registered_count=Count("registrations", distinct=True))
        .order_by("date", "created_at")
    )
    return render(request, "blooddonation/camp_list.html", {"camps": camps, "today": today})


def camp_detail(request, camp_id):
    today = timezone.localdate()
    camp = get_object_or_404(
        BloodCamp.objects.annotate(registered_count=Count("registrations", distinct=True)),
        pk=camp_id,
        date__gte=today,
    )
    is_approved_donor = False
    has_registered = False
    donor_profile = None

    if request.user.is_authenticated:
        donor_profile = DonorProfile.objects.filter(user=request.user, verification_status="APPROVED", otp_verified=True).first()
        is_approved_donor = donor_profile is not None
        if donor_profile:
            has_registered = CampRegistration.objects.filter(donor=donor_profile, camp=camp).exists()

    registrations = camp.registrations.select_related("donor").order_by("registered_at")
    return render(
        request,
        "blooddonation/camp_detail.html",
        {
            "camp": camp,
            "registrations": registrations,
            "is_approved_donor": is_approved_donor,
            "has_registered": has_registered,
            "donor_profile": donor_profile,
        },
    )


@login_required
def register_camp(request, camp_id):
    donor_profile = get_object_or_404(DonorProfile, user=request.user)
    if donor_profile.verification_status != "APPROVED" or not donor_profile.otp_verified:
        messages.error(request, "Only approved donors can register for a blood camp.")
        return redirect("camp_detail", camp_id=camp_id)

    camp = get_object_or_404(BloodCamp, pk=camp_id, date__gte=timezone.localdate())
    registration, created = CampRegistration.objects.get_or_create(donor=donor_profile, camp=camp)

    if created:
        messages.success(request, "You have successfully registered for the camp.")
    else:
        messages.info(request, "You are already registered for this camp.")

    return redirect("camp_detail", camp_id=camp.id)


@login_required
def donor_dashboard(request):
    profile = DonorProfile.objects.filter(user=request.user).first()
    if not profile:
        messages.info(request, "Please complete donor registration first.")
        return redirect("donor_register")

    past_donations = DonationHistory.objects.filter(donor=profile).select_related("request")[:20]

    open_requests = []
    can_donate_now = profile.is_active_donor
    next_available_on = None

    if profile.last_donation_date and profile.is_in_cooldown:
        next_available_on = profile.last_donation_date + timedelta(days=90)

    if profile.verification_status == "APPROVED":
        open_requests = BloodRequest.objects.filter(
            status="APPROVED",
            blood_group=profile.blood_group,
            city__iexact=profile.city,
            fulfilled_by__isnull=True,
        ).order_by("-requested_at")[:20]

    return render(
        request,
        "blooddonation/donor_dashboard.html",
        {
            "profile": profile,
            "past_donations": past_donations,
            "total_donations": profile.donation_count,
            "current_rating": profile.rating,
            "open_requests": open_requests,
            "can_donate_now": can_donate_now,
            "next_available_on": next_available_on,
        },
    )


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
            req_id = request.POST.get("request_id")
            new_status = request.POST.get("status")
            req = get_object_or_404(BloodRequest, pk=req_id)

            # Admin can manually verify old or offline requests.
            if new_status in {"APPROVED", "REJECTED", "COMPLETED"} and not req.otp_verified:
                req.otp_verified = True
                req.save(update_fields=["otp_verified"])
                messages.info(request, "OTP was not verified, so admin override verification was applied.")

            if new_status in {"PENDING", "APPROVED", "REJECTED", "COMPLETED"}:
                if new_status == "APPROVED":
                    req.status = new_status
                    req.approved_at = timezone.now()
                    if req.assigned_donor is None:
                        matching_donor = (
                            DonorProfile.objects.filter(
                                blood_group=req.blood_group,
                                city__iexact=req.city,
                                verification_status="APPROVED",
                                otp_verified=True,
                                available=True,
                            )
                            .order_by("created_at")
                            .first()
                        )
                        if matching_donor and not matching_donor.is_in_cooldown:
                            req.assigned_donor = matching_donor

                    req.save(update_fields=["status", "approved_at", "assigned_donor"])
                    messages.success(request, "Request status updated.")
                elif new_status == "COMPLETED":
                    donor = req.assigned_donor or req.fulfilled_by
                    if donor:
                        completed_now = req.mark_completed(donor)
                        if completed_now:
                            messages.success(request, "Request marked completed and donor history updated.")
                        else:
                            messages.info(request, "Request was already completed.")
                    else:
                        req.status = "COMPLETED"
                        req.save(update_fields=["status"])
                        messages.warning(request, "Request marked completed without a donor assignment.")
                else:
                    req.status = new_status
                    req.save(update_fields=["status"])
                    messages.success(request, "Request status updated.")

        if action == "donor_verify":
            donor_id = request.POST.get("donor_id")
            decision = request.POST.get("verification_status")
            donor = get_object_or_404(DonorProfile, pk=donor_id)

            # Admin can manually verify donor in case of offline verification.
            if decision in {"APPROVED", "REJECTED"} and not donor.otp_verified:
                donor.otp_verified = True
                donor.save(update_fields=["otp_verified"])
                messages.info(request, "Donor OTP was missing, admin override verification applied.")

            if decision in {"PENDING", "APPROVED", "REJECTED"}:
                donor.verification_status = decision
                donor.save(update_fields=["verification_status"])
                messages.success(request, "Donor verification updated.")

        if action == "broadcast_create":
            broadcast_form = BroadcastMessageForm(request.POST)
            if broadcast_form.is_valid():
                broadcast = broadcast_form.save(commit=False)
                broadcast.created_by = request.user
                broadcast.save()
                messages.success(request, "Mass message published.")
                return redirect("admin_dashboard")

        if action == "camp_create":
            camp_form = BloodCampForm(request.POST)
            if camp_form.is_valid():
                camp = camp_form.save(commit=False)
                camp.created_by = request.user
                camp.save()
                messages.success(request, "Blood camp created successfully.")
                return redirect("admin_dashboard")

    donor_queryset = DonorProfile.objects.order_by("-created_at")
    request_queryset = BloodRequest.objects.order_by("-requested_at")

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

    blood_group_summary = []
    for group_value, group_label in DonorProfile.BLOOD_GROUP_CHOICES:
        donor_count = DonorProfile.objects.filter(blood_group=group_value).count()
        active_donor_count = [
            donor
            for donor in DonorProfile.objects.filter(
                blood_group=group_value,
                verification_status="APPROVED",
                otp_verified=True,
            )
            if donor.is_active_donor
        ]
        pending_request_count = BloodRequest.objects.filter(blood_group=group_value, status="PENDING").count()
        blood_group_summary.append(
            {
                "value": group_value,
                "label": group_label,
                "donor_count": donor_count,
                "active_donor_count": len(active_donor_count),
                "pending_request_count": pending_request_count,
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
    return render(request, "blooddonation/admin_dashboard.html", context)