from django.shortcuts import render
from django.db.models import Case, When, Value, IntegerField
from donors.models import DonorProfile
from requests.models import BloodRequest
from dashboard.models import BroadcastMessage

def home(request):
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

    context = {
        "donor_count": DonorProfile.objects.filter(verification_status="APPROVED").count(),
        "active_requests": BloodRequest.objects.filter(status="PENDING").count(),
        "broadcast_messages": BroadcastMessage.objects.filter(is_active=True)[:5],
        "recent_donors": DonorProfile.objects.filter(verification_status="APPROVED", otp_verified=True).order_by("-created_at")[:6],
        "emergency_cases": emergency_cases,
    }
    return render(request, "core/home.html", context)

def eligibility_checker(request):
    return render(request, "core/eligibility.html")


