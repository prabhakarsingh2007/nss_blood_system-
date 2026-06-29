import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from donors.models import DonorProfile
from core.sms import send_sms

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Sends SMS notifications to volunteers whose 90-day cooldown period has ended today."

    def handle(self, *args, **options):
        today = timezone.localdate()
        cooldown_target_date = today - timedelta(days=90)
        
        # Query donors who donated exactly 90 days ago and have not been alerted today
        donors = DonorProfile.objects.filter(
            last_donation_date=cooldown_target_date,
            verification_status="APPROVED",
            otp_verified=True,
            available=True
        ).exclude(last_cooldown_alert_date=today)

        self.stdout.write(f"Found {donors.count()} donor(s) whose cooldown ended today ({cooldown_target_date}).")
        
        sent_count = 0
        for donor in donors:
            msg = (
                f"NSS Blood: Hello {donor.full_name}! Your 90-day donation cooldown has successfully ended. "
                f"You are now marked as available to donate and save lives again."
            )
            success = send_sms(donor.phone, msg)
            if success:
                donor.last_cooldown_alert_date = today
                donor.save(update_fields=["last_cooldown_alert_date"])
                sent_count += 1
                self.stdout.write(self.style.SUCCESS(f"Successfully alerted {donor.full_name} ({donor.phone})."))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to send SMS to {donor.full_name}."))

        self.stdout.write(f"Alert dispatch completed. Sent: {sent_count} alerts.")
