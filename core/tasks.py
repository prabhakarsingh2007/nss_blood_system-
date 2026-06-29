import logging
from celery import shared_task
from core.sms import send_sms as sync_send_sms

logger = logging.getLogger(__name__)

@shared_task
def send_sms_async(to_number: str, message: str) -> bool:
    """
    Asynchronously dispatches an SMS alert via the configured SMS Gateway (Twilio / Msg91).
    """
    logger.info(f"Asynchronously dispatching SMS to {to_number}")
    return sync_send_sms(to_number, message)
