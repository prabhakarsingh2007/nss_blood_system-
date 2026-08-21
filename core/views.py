from django.shortcuts import render
from django.db.models import Case, When, Value, IntegerField, Q, Count
from django.utils import timezone
from donors.models import DonorProfile, BloodCamp, DonationHistory
from requests.models import BloodRequest
from dashboard.models import BroadcastMessage

def home(request):
    today = timezone.localdate()
    now_time = timezone.localtime().time()

    # Q filters matching property logic for completed/upcoming
    completed_q = Q(status="COMPLETED") | (
        Q(status="AUTO") & (
            Q(date__lt=today) |
            Q(date=today, end_time__lt=now_time)
        )
    )

    upcoming_q = Q(status__in=["UPCOMING", "ONGOING"]) | (
        Q(status="AUTO") & (
            Q(date__gt=today) |
            Q(date=today, end_time__isnull=True) |
            Q(date=today, end_time__gte=now_time)
        )
    )

    upcoming_camps = BloodCamp.objects.annotate(registered_count=Count("registrations", distinct=True)).filter(upcoming_q).order_by("date", "start_time")[:3]
    completed_camps = BloodCamp.objects.filter(completed_q).order_by("-date", "-start_time")[:3]

    emergency_cases = BloodRequest.objects.filter(
        status__in=["PENDING", "APPROVED", "ASSIGNED"],
        priority__in=["URGENT", "CRITICAL"]
    ).annotate(
        priority_order=Case(
            When(priority="CRITICAL", then=Value(1)),
            When(priority="URGENT", then=Value(2)),
            default=Value(3),
            output_field=IntegerField()
        )
    ).order_by("priority_order", "-requested_at")[:6]

    # Query verified successful donations and extract unique donors to avoid duplicates
    all_verified = DonationHistory.objects.filter(
        status="SUCCESS",
        nss_verified=True
    ).select_related('donor', 'camp', 'request').order_by("-date")

    seen_donors = set()
    verified_donations = []
    for donation in all_verified:
        if donation.donor_id and donation.donor_id not in seen_donors:
            seen_donors.add(donation.donor_id)
            verified_donations.append(donation)
            if len(verified_donations) >= 6:
                break

    context = {
        "donor_count": DonorProfile.objects.filter(verification_status="APPROVED", otp_verified=True).count(),
        "active_requests": BloodRequest.objects.filter(status="PENDING").count(),
        "total_requests": BloodRequest.objects.count(),
        "successful_donations": DonationHistory.objects.filter(status="SUCCESS", nss_verified=True).count(),
        "total_camps": BloodCamp.objects.count(),
        "total_districts": DonorProfile.objects.filter(verification_status="APPROVED", otp_verified=True).values("city").distinct().count(),
        "broadcast_messages": BroadcastMessage.objects.filter(is_active=True)[:5],
        "recent_donors": DonorProfile.objects.filter(verification_status="APPROVED", otp_verified=True).order_by("-created_at")[:6],
        "emergency_cases": emergency_cases,
        "upcoming_camps": upcoming_camps,
        "completed_camps": completed_camps,
        "verified_donations": verified_donations,
    }
    return render(request, "core/home.html", context)

def eligibility_checker(request):
    return render(request, "core/eligibility.html")

def about(request):
    today = timezone.localdate()
    now_time = timezone.localtime().time()

    completed_q = Q(status="COMPLETED") | (
        Q(status="AUTO") & (
            Q(date__lt=today) |
            Q(date=today, end_time__lt=now_time)
        )
    )

    completed_camps = BloodCamp.objects.filter(completed_q).order_by("-date", "-start_time")[:6]

    context = {
        "donor_count": DonorProfile.objects.filter(verification_status="APPROVED", otp_verified=True).count(),
        "total_requests": BloodRequest.objects.count(),
        "successful_donations": DonationHistory.objects.filter(status="SUCCESS", nss_verified=True).count(),
        "total_camps": BloodCamp.objects.count(),
        "completed_camps": completed_camps,
    }
    return render(request, "core/about.html", context)



