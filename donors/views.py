from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from core.utils import (
    get_client_ip,
    check_otp_rate_limit,
    increment_otp_attempts,
    clear_otp_attempts,
)
from requests.models import BloodRequest
from .forms import DonorProfileForm, OtpVerifyForm
from .models import BloodCamp, CampRegistration, DonationHistory, DonorProfile

BIHAR_DISTRICTS = [
    "Araria", "Arwal", "Aurangabad", "Banka", "Begusarai", "Bhagalpur", "Bhojpur", "Buxar",
    "Darbhanga", "East Champaran", "Gaya", "Gopalganj", "Jamui", "Jehanabad", "Kaimur", "Katihar",
    "Khagaria", "Kishanganj", "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur",
    "Nalanda", "Nawada", "Patna", "Purnia", "Rohtas", "Saharsa", "Samastipur", "Saran",
    "Sheikhpura", "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali", "West Champaran",
]

def search_donors(request):
    blood_group = request.GET.get("blood_group", "")
    city = request.GET.get("city", "")
    context = {
        "blood_groups": DonorProfile.BLOOD_GROUP_CHOICES,
        "cities": BIHAR_DISTRICTS,
        "selected_blood_group": blood_group,
        "selected_city": city,
    }
    return render(request, "donors/search.html", context)

def donor_list(request):
    blood_group = request.GET.get("blood_group", "")
    city = request.GET.get("city", "")

    cooldown_limit = timezone.localdate() - timedelta(days=90)
    donors_qs = (
        DonorProfile.objects.filter(
            verification_status="APPROVED",
            otp_verified=True,
            available=True,
        )
        .filter(Q(last_donation_date__isnull=True) | Q(last_donation_date__lte=cooldown_limit))
        .order_by("-created_at")
    )
    if blood_group:
        donors_qs = donors_qs.filter(blood_group=blood_group)
    if city:
        donors_qs = donors_qs.filter(city__icontains=city)

    paginator = Paginator(donors_qs, 12)  # 12 donors per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    donors = [
        {
            "full_name": donor.full_name,
            "blood_group": donor.blood_group,
            "city": donor.city,
            "is_available": donor.is_active_donor,
        }
        for donor in page_obj
    ]

    context = {
        "donors": donors,
        "page_obj": page_obj,
        "blood_group": blood_group,
        "city": city,
    }
    return render(request, "donors/donor_list.html", context)

@login_required
def donor_register(request):
    profile = DonorProfile.objects.filter(user=request.user).first()

    if request.method == "POST":
        form = DonorProfileForm(request.POST, instance=profile)
        if form.is_valid():
            donor = form.save(commit=False)
            donor.user = request.user
            if profile is None:
                donor.verification_status = "PENDING"
            donor.otp_verified = True
            donor.save()
            messages.success(request, "Donor profile registered successfully. Profile is pending admin approval.")
            return redirect("donor_dashboard")
    else:
        form = DonorProfileForm(instance=profile)
    return render(request, "donors/donor_register.html", {"form": form, "public_page": False})

@login_required
def donor_verify_otp(request):
    return redirect("donor_dashboard")

def camp_list(request):
    today = timezone.localdate()
    camps_qs = (
        BloodCamp.objects.filter(date__gte=today)
        .annotate(registered_count=Count("registrations", distinct=True))
        .order_by("date", "created_at")
    )
    paginator = Paginator(camps_qs, 10)  # 10 camps per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "donors/camp_list.html", {"camps": page_obj, "page_obj": page_obj, "today": today})

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
        "donors/camp_detail.html",
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
def donation_certificate(request, history_id):
    donation_history = get_object_or_404(
        DonationHistory.objects.select_related("donor", "request", "verified_by", "donor__user"),
        pk=history_id,
    )

    if not request.user.is_staff and donation_history.donor.user_id != request.user.id:
        messages.error(request, "You are not allowed to view this certificate.")
        return redirect("dashboard_router")

    if not donation_history.has_certificate:
        messages.error(request, "Certificate is not available until NSS verification is completed.")
        return redirect("donor_dashboard")

    context = {
        "donation": donation_history,
        "issued_date": timezone.localtime(donation_history.verified_at) if donation_history.verified_at else timezone.localtime(),
    }
    return render(request, "donors/certificate.html", context)
