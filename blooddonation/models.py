from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string


class DonorProfile(models.Model):
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
    VERIFICATION_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=120)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES)
    age = models.PositiveSmallIntegerField()
    phone = models.CharField(max_length=15)
    city = models.CharField(max_length=100)
    last_donation_date = models.DateField(blank=True, null=True)
    available = models.BooleanField(default=True)
    donation_count = models.IntegerField(default=0)
    rating = models.FloatField(default=0.0)
    verification_status = models.CharField(max_length=10, choices=VERIFICATION_CHOICES, default="PENDING")
    otp_code = models.CharField(max_length=6, blank=True)
    otp_verified = models.BooleanField(default=False)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.full_name} ({self.blood_group})"

    @property
    def cooldown_days_remaining(self) -> int:
        if not self.last_donation_date:
            return 0
        days_since_donation = (timezone.localdate() - self.last_donation_date).days
        return max(0, 90 - days_since_donation)

    @property
    def is_in_cooldown(self) -> bool:
        return self.cooldown_days_remaining > 0

    @property
    def is_active_donor(self) -> bool:
        return self.verification_status == "APPROVED" and self.otp_verified and self.available and not self.is_in_cooldown

    def generate_otp(self) -> str:
        code = get_random_string(6, allowed_chars="0123456789")
        self.otp_code = code
        self.otp_verified = False
        self.otp_created_at = timezone.now()
        return code

    def otp_is_valid(self, code: str) -> bool:
        if not self.otp_created_at:
            return False
        return self.otp_code == code and timezone.now() <= self.otp_created_at + timedelta(minutes=10)

    def recalculate_rating(self) -> float:
        if self.donation_count >= 8:
            self.rating = 5.0
        elif self.donation_count >= 4:
            self.rating = 4.0
        elif self.donation_count >= 1:
            self.rating = 3.0
        else:
            self.rating = 0.0
        return self.rating


class BloodRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("COMPLETED", "Completed"),
    ]

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="blood_requests",
    )
    requester_name = models.CharField(max_length=120)
    blood_group = models.CharField(max_length=3, choices=DonorProfile.BLOOD_GROUP_CHOICES)
    units = models.PositiveSmallIntegerField(default=1)
    hospital_name = models.CharField(max_length=180)
    city = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=15)
    reason = models.TextField()
    is_emergency = models.BooleanField(default=False)
    request_code = models.CharField(max_length=12, unique=True, blank=True)
    otp_code = models.CharField(max_length=6, blank=True)
    otp_verified = models.BooleanField(default=False)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    assigned_donor = models.ForeignKey(
        DonorProfile,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_requests",
    )
    fulfilled_by = models.ForeignKey(
        DonorProfile,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="fulfilled_requests",
    )

    def __str__(self) -> str:
        return f"{self.requester_name} - {self.blood_group} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.request_code:
            self.request_code = f"REQ{get_random_string(9, allowed_chars='0123456789')}"
        super().save(*args, **kwargs)

    def generate_otp(self) -> str:
        code = get_random_string(6, allowed_chars="0123456789")
        self.otp_code = code
        self.otp_verified = False
        self.otp_created_at = timezone.now()
        return code

    def otp_is_valid(self, code: str) -> bool:
        if not self.otp_created_at:
            return False
        return self.otp_code == code and timezone.now() <= self.otp_created_at + timedelta(minutes=10)

    def mark_completed(self, donor: DonorProfile) -> bool:
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


class BroadcastMessage(models.Model):
    message = models.CharField(max_length=240)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.message


class BloodCamp(models.Model):
    title = models.CharField(max_length=180)
    description = models.TextField()
    date = models.DateField()
    location = models.CharField(max_length=180)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_blood_camps",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.date})"


class CampRegistration(models.Model):
    STATUS_REGISTERED = "registered"
    STATUS_ATTENDED = "attended"
    STATUS_CHOICES = [
        (STATUS_REGISTERED, "Registered"),
        (STATUS_ATTENDED, "Attended"),
    ]

    donor = models.ForeignKey(DonorProfile, on_delete=models.CASCADE, related_name="camp_registrations")
    camp = models.ForeignKey(BloodCamp, on_delete=models.CASCADE, related_name="registrations")
    registered_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_REGISTERED)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(fields=["donor", "camp"], name="unique_camp_registration_per_donor"),
        ]

    def __str__(self) -> str:
        return f"{self.donor.full_name} -> {self.camp.title} ({self.status})"


class DonationHistory(models.Model):
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    donor = models.ForeignKey(DonorProfile, on_delete=models.CASCADE, related_name="donation_histories")
    request = models.ForeignKey(BloodRequest, on_delete=models.CASCADE, related_name="donation_histories")
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SUCCESS)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["donor", "request"], name="unique_donation_history_per_request"),
        ]

    def __str__(self) -> str:
        return f"{self.donor.full_name} - {self.request.request_code} ({self.status})"