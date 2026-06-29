import logging
import os
import requests

logger = logging.getLogger(__name__)

def send_sms(to_number: str, message: str) -> bool:
    """
    Sends an SMS using a live SMS provider (Twilio or Msg91) if configured in the environment.
    Falls back to console output for local development and verification.
    """
    # Normalize phone number (ensure country code like +91 for India if not present)
    if not to_number.startswith("+"):
        if len(to_number) == 10:
            to_number = f"+91{to_number}"
        elif len(to_number) == 12 and to_number.startswith("91"):
            to_number = f"+{to_number}"

    # Provider 1: Twilio
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    twilio_number = os.environ.get("TWILIO_PHONE_NUMBER")

    if twilio_sid and twilio_token and twilio_number:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            data = {
                "To": to_number,
                "From": twilio_number,
                "Body": message
            }
            response = requests.post(url, data=data, auth=(twilio_sid, twilio_token), timeout=10)
            if response.status_code in (200, 201):
                logger.info(f"SMS successfully dispatched via Twilio to {to_number}.")
                return True
            else:
                logger.error(f"Twilio SMS delivery failed: {response.text}")
        except Exception as e:
            logger.exception(f"Exception during Twilio SMS dispatch: {e}")

    # Provider 2: Msg91
    msg91_authkey = os.environ.get("MSG91_AUTH_KEY")
    msg91_flow_id = os.environ.get("MSG91_FLOW_ID")
    msg91_sender = os.environ.get("MSG91_SENDER_ID", "NSSBLD")

    if msg91_authkey and msg91_flow_id:
        try:
            url = "https://api.msg91.com/api/v5/flow/"
            headers = {
                "authkey": msg91_authkey,
                "content-type": "application/json"
            }
            # Msg91 Flow API payload structure
            payload = {
                "flow_id": msg91_flow_id,
                "sender": msg91_sender,
                "mobiles": to_number.replace("+", ""),  # Msg91 expects mobile without +
                "var": message
            }
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                logger.info(f"SMS successfully dispatched via Msg91 to {to_number}.")
                return True
            else:
                logger.error(f"Msg91 SMS delivery failed: {response.text}")
        except Exception as e:
            logger.exception(f"Exception during Msg91 SMS dispatch: {e}")

    # Fallback to local console printout if no provider is configured
    print("\n" + "=" * 50)
    print(f"--- DUMMY SMS OUTGOING DISPATCH ---")
    print(f"TO: {to_number}")
    print(f"MESSAGE: {message}")
    print("=" * 50 + "\n")
    logger.info(f"Local mock SMS logged to console for {to_number}.")
    return True
