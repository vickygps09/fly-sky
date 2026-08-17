"""SMS & WhatsApp Service — Supports Twilio and mock (console) mode.

If TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are configured:
  - SMS sent via Twilio Programmable SMS (TWILIO_FROM_NUMBER)
  - WhatsApp sent via Twilio WhatsApp API (TWILIO_WHATSAPP_FROM_NUMBER or TWILIO_FROM_NUMBER)
Otherwise, falls back to console logging (mock mode).

Twilio Free Trial:
  - $15 trial credit
  - SMS: send only to verified numbers
  - WhatsApp: send only to verified numbers (join sandbox first)
  - Get keys: https://console.twilio.com/
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional
from config import settings


def _get_twilio_auth() -> tuple:
    """Get Twilio auth credentials and account SID.

    Supports two auth methods:
    1. API Key SID (SK...) + API Key Secret — requires TWILIO_ACCOUNT_SID (AC...) for URL
    2. Account SID (AC...) + Auth Token — classic basic auth

    Returns (account_sid, auth_username, auth_password)
    """
    if settings.TWILIO_API_KEY_SID and settings.TWILIO_API_KEY_SECRET:
        # API Key auth: use SK...:secret as basic auth, AC... in URL
        account_sid = settings.TWILIO_ACCOUNT_SID
        if not account_sid or not account_sid.startswith("AC"):
            raise ValueError(
                "TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET are set, but "
                "TWILIO_ACCOUNT_SID must also be set to your Account SID (starts with AC...). "
                "Find it at https://console.twilio.com/"
            )
        return (account_sid, settings.TWILIO_API_KEY_SID, settings.TWILIO_API_KEY_SECRET)

    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        return (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    raise ValueError("No Twilio credentials configured")


def _twilio_request(payload: dict) -> dict:
    """Make a Twilio Messages API request using configured auth method."""
    import base64

    account_sid, auth_user, auth_pass = _get_twilio_auth()

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = urllib.parse.urlencode(payload).encode("utf-8")

    auth_str = f"{auth_user}:{auth_pass}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result


# Twilio trial account predefined SMS templates
# See: https://www.twilio.com/docs/usage/trials/try-out-sms
# These are Twilio-defined template names — not configurable via env
TWILIO_TRIAL_SMS_TEMPLATES = {
    "booking_confirmation": "sms_order_confirmation",
    "check_in": "sms_appointment_reminders",
    "cancellation": "sms_account_alerts",
    "flight_status": "sms_delivery_updates",
    "otp": "sms_2fa",
    "support": "sms_customer_support",
    "event": "sms_event_notifications",
    "feedback": "sms_feedback_surveys",
    "marketing": "sms_marketing_promotions",
    "internal": "sms_internal_alerts",
}


def _is_trial_account() -> bool:
    """Check if this is a Twilio trial account (uses predefined templates)."""
    return settings.TWILIO_TRIAL_MODE


def send_via_twilio_sms(to_phone: str, body: str, template: str = None) -> dict:
    """Send SMS via Twilio Programmable SMS API.

    On trial accounts, uses predefined template names instead of custom body.
    """
    from_num = settings.TWILIO_FROM_NUMBER

    # On trial accounts, use predefined templates
    if _is_trial_account():
        tpl = TWILIO_TRIAL_SMS_TEMPLATES.get(template, settings.TWILIO_SMS_DEFAULT_TEMPLATE)
        body_to_send = tpl
    else:
        body_to_send = body

    result = _twilio_request({
        "To": to_phone,
        "From": from_num,
        "Body": body_to_send,
    })

    return {
        "success": True,
        "method": "twilio_sms",
        "recipient": to_phone,
        "message_sid": result.get("sid"),
        "status": result.get("status", "queued"),
        "template_used": body_to_send if _is_trial_account() else None,
        "body": result.get("body", body),
    }


def send_via_twilio_whatsapp(to_phone: str, body: str, template: str = None) -> dict:
    """Send WhatsApp message via Twilio WhatsApp API.

    On trial accounts, uses pre-approved ContentSid templates.
    On paid accounts, sends custom body text.
    """
    from_num = settings.TWILIO_WHATSAPP_FROM_NUMBER or settings.TWILIO_FROM_NUMBER
    if not from_num:
        from_num = settings.TWILIO_WHATSAPP_SANDBOX_NUMBER

    if _is_trial_account():
        content_sid = settings.TWILIO_WHATSAPP_CONTENT_SID
        result = _twilio_request({
            "To": f"whatsapp:{to_phone}",
            "From": f"whatsapp:{from_num}",
            "ContentSid": content_sid,
        })
    else:
        result = _twilio_request({
            "To": f"whatsapp:{to_phone}",
            "From": f"whatsapp:{from_num}",
            "Body": body,
        })

    return {
        "success": True,
        "method": "twilio_whatsapp",
        "recipient": to_phone,
        "message_sid": result.get("sid"),
        "status": result.get("status", "queued"),
        "template_used": content_sid if _is_trial_account() else None,
        "body": result.get("body", body),
    }


def _clean_phone(phone: str) -> str:
    """Clean and normalize a phone number to E.164 format."""
    cleaned = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not cleaned.startswith("+"):
        # If 10-digit number (Indian mobile), add +91 country code
        if len(cleaned) == 10:
            cleaned = "+91" + cleaned
        # If starts with 91 and is 12 digits, add +
        elif len(cleaned) == 12 and cleaned.startswith("91"):
            cleaned = "+" + cleaned
        else:
            cleaned = "+" + cleaned
    return cleaned


def _mock_log(channel: str, to_phone: str, body: str) -> dict:
    """Log message to console in mock mode."""
    print(f"\n{'='*60}")
    print(f"📱 [MOCK {channel.upper()}] To: {to_phone}")
    print(f"   Body: {body[:200]}")
    print(f"{'='*60}\n")
    return {"success": True, "method": "mock", "channel": channel, "recipient": to_phone}


def _is_twilio_configured() -> bool:
    """Check if Twilio credentials are set (either auth method)."""
    # Method 1: API Key SID + Secret + Account SID (AC...)
    if (settings.TWILIO_API_KEY_SID
            and settings.TWILIO_API_KEY_SECRET
            and settings.TWILIO_ACCOUNT_SID
            and settings.TWILIO_ACCOUNT_SID.startswith("AC")):
        return True
    # Method 2: Account SID + Auth Token + phone number
    if (settings.TWILIO_ACCOUNT_SID
            and settings.TWILIO_AUTH_TOKEN
            and settings.TWILIO_FROM_NUMBER):
        return True
    return False


def _is_sms_configured() -> bool:
    """Check if SMS specifically is configured (needs a from number)."""
    return _is_twilio_configured() and bool(settings.TWILIO_FROM_NUMBER)


def _is_whatsapp_configured() -> bool:
    """Check if WhatsApp is configured (uses sandbox number if no dedicated number)."""
    return _is_twilio_configured()


def send_sms(to_phone: str, body: str, template: str = None) -> dict:
    """Send an SMS using the best available method.

    Priority: Twilio SMS API > Console (mock)

    Args:
        to_phone: Recipient phone number.
        body: Custom message body (used on paid accounts).
        template: Template key for trial accounts (e.g. 'booking_confirmation',
                  'check_in', 'cancellation', 'otp', 'flight_status').
    """
    if not to_phone:
        return {"success": False, "error": "Invalid phone number"}

    phone_clean = _clean_phone(to_phone)

    if _is_sms_configured():
        try:
            return send_via_twilio_sms(phone_clean, body, template)
        except urllib.error.HTTPError as e:
            err_body = json.loads(e.read().decode("utf-8"))
            print(f"⚠️  Twilio SMS failed: {err_body.get('message', str(e))}. Falling back to console.")
        except Exception as e:
            print(f"⚠️  Twilio SMS send failed: {e}. Falling back to console.")

    return _mock_log("sms", phone_clean, body)


def send_whatsapp(to_phone: str, body: str, template: str = None) -> dict:
    """Send a WhatsApp message using the best available method.

    Priority: Twilio WhatsApp API > Console (mock)

    Args:
        to_phone: Recipient phone number.
        body: Custom message body (used on paid accounts).
        template: Template key for trial accounts (e.g. 'booking_confirmation').
    """
    if not to_phone:
        return {"success": False, "error": "Invalid phone number"}

    phone_clean = _clean_phone(to_phone)

    if _is_whatsapp_configured():
        try:
            return send_via_twilio_whatsapp(phone_clean, body, template)
        except urllib.error.HTTPError as e:
            err_body = json.loads(e.read().decode("utf-8"))
            print(f"⚠️  Twilio WhatsApp failed: {err_body.get('message', str(e))}. Falling back to console.")
        except Exception as e:
            print(f"⚠️  Twilio WhatsApp send failed: {e}. Falling back to console.")

    return _mock_log("whatsapp", phone_clean, body)


def send_notification_message(
    to_phone: str,
    body: str,
    channels: list[str] = None,
) -> dict:
    """Send a message via multiple channels (SMS + WhatsApp).

    Args:
        to_phone: Recipient phone number in E.164 or local format.
        body: Message body text.
        channels: List of channels to use. Default: ['sms', 'whatsapp']

    Returns dict with per-channel results.
    """
    if channels is None:
        channels = ["sms", "whatsapp"]

    results = {}
    for ch in channels:
        if ch == "sms":
            results["sms"] = send_sms(to_phone, body)
        elif ch == "whatsapp":
            results["whatsapp"] = send_whatsapp(to_phone, body)

    return {
        "success": any(r.get("success") for r in results.values()),
        "channels": results,
    }


def send_booking_confirmation_sms(
    to_phone: str,
    pnr: str,
    flight_number: str,
    departure_city: str,
    arrival_city: str,
    departure_time: str,
    channels: list[str] = None,
) -> dict:
    """Send a booking confirmation via SMS and/or WhatsApp."""
    body = (
        f"✈️ SkyBook AI: Booking confirmed!\n"
        f"PNR: {pnr}\n"
        f"Flight {flight_number}: {departure_city} → {arrival_city}\n"
        f"Departure: {departure_time}\n"
        f"Check-in opens 24h before departure."
    )
    if channels is None:
        channels = ["sms", "whatsapp"]
    results = {}
    for ch in channels:
        if ch == "sms":
            results["sms"] = send_sms(to_phone, body, template="booking_confirmation")
        elif ch == "whatsapp":
            results["whatsapp"] = send_whatsapp(to_phone, body, template="booking_confirmation")
    return {"success": any(r.get("success") for r in results.values()), "channels": results}


def send_checkin_sms(
    to_phone: str,
    pnr: str,
    seat: str,
    gate: str,
    boarding_time: str,
    channels: list[str] = None,
) -> dict:
    """Send a check-in confirmation via SMS and/or WhatsApp."""
    body = (
        f"✅ SkyBook AI: Check-in complete!\n"
        f"PNR: {pnr}\n"
        f"Seat: {seat}, Gate: {gate}\n"
        f"Boarding: {boarding_time}\n"
        f"Please arrive 2h before departure."
    )
    if channels is None:
        channels = ["sms", "whatsapp"]
    results = {}
    for ch in channels:
        if ch == "sms":
            results["sms"] = send_sms(to_phone, body, template="check_in")
        elif ch == "whatsapp":
            results["whatsapp"] = send_whatsapp(to_phone, body, template="check_in")
    return {"success": any(r.get("success") for r in results.values()), "channels": results}


def send_cancellation_sms(
    to_phone: str,
    pnr: str,
    refund_amount: float,
    channels: list[str] = None,
) -> dict:
    """Send a booking cancellation via SMS and/or WhatsApp."""
    body = (
        f"❌ SkyBook AI: Booking {pnr} cancelled.\n"
        f"Refund of ₹{refund_amount:,.0f} will be processed in 5-7 business days."
    )
    if channels is None:
        channels = ["sms", "whatsapp"]
    results = {}
    for ch in channels:
        if ch == "sms":
            results["sms"] = send_sms(to_phone, body, template="cancellation")
        elif ch == "whatsapp":
            results["whatsapp"] = send_whatsapp(to_phone, body, template="cancellation")
    return {"success": any(r.get("success") for r in results.values()), "channels": results}
