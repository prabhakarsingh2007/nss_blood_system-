from datetime import timedelta
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from core.utils import generate_secure_otp

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
    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=120)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, db_index=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    age = models.PositiveSmallIntegerField()
    phone = models.CharField(max_length=15)
    city = models.CharField(max_length=100, db_index=True)
    last_donation_date = models.DateField(blank=True, null=True)
    available = models.BooleanField(default=True)
    donation_count = models.IntegerField(default=0)
    rating = models.FloatField(default=0.0)
    verification_status = models.CharField(max_length=10, choices=VERIFICATION_CHOICES, default="PENDING", db_index=True)
    otp_code = models.CharField(max_length=6, blank=True)
    otp_verified = models.BooleanField(default=False, db_index=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blooddonation_donorprofile'

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
        code = generate_secure_otp(6)
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


class BloodCamp(models.Model):
    title = models.CharField(max_length=180)
    description = models.TextField()
    date = models.DateField(db_index=True)
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
        db_table = 'blooddonation_bloodcamp'

    def __str__(self) -> str:
        return f"{self.title} ({self.date})"


class CampRegistration(models.Model):
    STATUS_REGISTERED = "registered"
    STATUS_ATTENDED = "attended"
    STATUS_CHOICES = [
        (STATUS_REGISTERED, "Registered"),
        (STATUS_ATTENDED, "Attended"),
    ]

    donor = models.ForeignKey('DonorProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name="camp_registrations")
    camp = models.ForeignKey('BloodCamp', on_delete=models.CASCADE, related_name="registrations")
    registered_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_REGISTERED)

    class Meta:
        ordering = ["-registered_at"]
        db_table = 'blooddonation_campregistration'
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

    donor = models.ForeignKey('DonorProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name="donation_histories")
    request = models.ForeignKey('requests.BloodRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name="donation_histories")
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    nss_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="nss_verified_donations",
    )
    verified_at = models.DateTimeField(blank=True, null=True)
    certificate_id = models.CharField(max_length=20, blank=True, null=True, default=None, unique=True)

    class Meta:
        ordering = ["-date"]
        db_table = 'blooddonation_donationhistory'
        constraints = [
            models.UniqueConstraint(fields=["donor", "request"], name="unique_donation_history_per_request"),
        ]

    def __str__(self) -> str:
        return f"{self.donor.full_name} - {self.request.request_code if self.request else 'None'} ({self.status})"

    @property
    def has_certificate(self) -> bool:
        return self.nss_verified and bool(self.certificate_id)

    def _generate_certificate_id(self) -> str:
        year = timezone.now().year
        while True:
            candidate = f"NSS-{year}-{get_random_string(4, allowed_chars='0123456789')}"
            if not DonationHistory.objects.filter(certificate_id=candidate).exists():
                return candidate

    def verify_by_nss(self, verifier):
        if self.nss_verified:
            return False

        self.nss_verified = True
        self.verified_by = verifier
        self.verified_at = timezone.now()
        if not self.certificate_id:
            self.certificate_id = self._generate_certificate_id()
        self.save(update_fields=["nss_verified", "verified_by", "verified_at", "certificate_id"])
        return True
