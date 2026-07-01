from datetime import timedelta
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from core.utils import generate_secure_otp

class BloodBank(models.Model):
    name = models.CharField(max_length=180, unique=True)
    city = models.CharField(max_length=100, db_index=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'blooddonation_bloodbank'
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.city})"


class Hospital(models.Model):
    name = models.CharField(max_length=180, unique=True)
    city = models.CharField(max_length=100, db_index=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'blooddonation_hospital'
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.city})"


class BloodRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Verification"),
        ("APPROVED", "Approved"),
        ("ASSIGNED", "Donor Assigned"),
        ("COMPLETED", "Completed"),
        ("REJECTED", "Rejected"),
    ]

    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
    ]

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="blood_requests",
    )
    requester_name = models.CharField(max_length=120)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, db_index=True)
    units = models.PositiveSmallIntegerField(default=1)
    hospital_name = models.CharField(max_length=180)
    blood_bank = models.CharField(max_length=180, blank=True, null=True)
    city = models.CharField(max_length=100, db_index=True)
    contact_number = models.CharField(max_length=15)
    reason = models.TextField()
    is_emergency = models.BooleanField(default=False)
    PRIORITY_CHOICES = [
        ("NORMAL", "Normal"),
        ("URGENT", "Urgent"),
        ("CRITICAL", "Critical"),
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="NORMAL", db_index=True)
    request_code = models.CharField(max_length=12, unique=True, blank=True)
    otp_code = models.CharField(max_length=6, blank=True)
    otp_verified = models.BooleanField(default=False)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING", db_index=True)
    rejection_reason = models.TextField(blank=True, null=True)
    prescription = models.FileField(upload_to="prescriptions/", null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    approved_at = models.DateTimeField(blank=True, null=True)

    @property
    def is_pdf(self):
        if self.prescription:
            return self.prescription.name.lower().endswith('.pdf')
        return False
    assigned_donor = models.ForeignKey(
        'donors.DonorProfile',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_requests",
    )
    fulfilled_by = models.ForeignKey(
        'donors.DonorProfile',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="fulfilled_requests",
    )

    class Meta:
        db_table = 'blooddonation_bloodrequest'

    def __str__(self) -> str:
        return f"{self.requester_name} - {self.blood_group} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.request_code:
            self.request_code = f"REQ{get_random_string(9, allowed_chars='0123456789')}"
        if self.priority in {"URGENT", "CRITICAL"}:
            self.is_emergency = True
        else:
            self.is_emergency = False
        super().save(*args, **kwargs)

    def generate_otp(self) -> str:
        code = generate_secure_otp(6)
        self.otp_code = code
        self.otp_verified = False
        self.otp_created_at = timezone.now()
        return code

    def otp_is_valid(self, code: str) -> bool:
        if not self.otp_created_at:
            return False
        return self.otp_code == code and timezone.now() <= self.otp_created_at + timedelta(minutes=10)

    def mark_completed(self, donor) -> bool:
        from donors.models import DonationHistory, DonorProfile
        with transaction.atomic():
            locked_request = BloodRequest.objects.select_for_update().get(pk=self.pk)

            if locked_request.status == "COMPLETED":
                return False

            locked_request.status = "COMPLETED"
            locked_request.fulfilled_by = donor
            locked_request.save(update_fields=["status", "fulfilled_by"])

            locked_donor = DonorProfile.objects.select_for_update().get(pk=donor.pk)
            locked_donor.donation_count += 1
            locked_donor.last_donation_date = timezone.localdate()
            locked_donor.recalculate_rating()
            locked_donor.save(update_fields=["donation_count", "rating", "last_donation_date"])

            DonationHistory.objects.create(
                donor=locked_donor,
                request=locked_request,
                status=DonationHistory.STATUS_SUCCESS,
            )

            self.status = locked_request.status
            self.fulfilled_by = locked_request.fulfilled_by
            return True
