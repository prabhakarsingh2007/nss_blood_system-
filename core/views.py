from django.shortcuts import render
from donors.models import DonorProfile
from requests.models import BloodRequest
from dashboard.models import BroadcastMessage

def home(request):
    context = {
        "donor_count": DonorProfile.objects.filter(verification_status="APPROVED").count(),
        "active_requests": BloodRequest.objects.filter(status="PENDING").count(),
        "broadcast_messages": BroadcastMessage.objects.filter(is_active=True)[:5],
        "recent_donors": DonorProfile.objects.filter(verification_status="APPROVED", otp_verified=True).order_by("-created_at")[:6],
    }
    return render(request, "core/home.html", context)
