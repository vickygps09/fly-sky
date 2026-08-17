"""External API router — Weather, Currency, Maps, SMS endpoints.

Exposes all third-party API integrations as REST endpoints:
- Weather: Open-Meteo (free, no key)
- Currency Conversion: open.er-api.com (free, no key)
- Maps/Geocoding/Directions: OpenStreetMap Nominatim + OSRM (free, no key)
- SMS: Twilio (free trial) or mock fallback
- Email: SMTP / Resend (already in notifications router)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from chatbot.tools import get_weather, convert_currency
from cache import cache_get, cache_set
from services.maps_service import (
    geocode_location,
    get_airport_location,
    get_directions_to_airport,
    get_static_map_url,
)
from services.sms_service import (
    send_sms,
    send_whatsapp,
    send_notification_message,
    send_booking_confirmation_sms,
)
from services.email_service import send_email

router = APIRouter(prefix="/api/external", tags=["External APIs"])


# ── Weather ─────────────────────────────────────────────────────────────────

@router.get("/weather/{city}")
def weather(city: str):
    """Get current weather for a city (Open-Meteo, free, no key needed)."""
    cache_key = f"weather:{city.lower()}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    result = get_weather(city)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    cache_set(cache_key, result, ttl=600)
    return result


# ── Currency Conversion ─────────────────────────────────────────────────────

class CurrencyConvertRequest(BaseModel):
    amount: float
    from_currency: str = "INR"
    to_currency: str = "USD"


@router.post("/currency/convert")
def currency_convert(data: CurrencyConvertRequest):
    """Convert currency using free exchange rate API."""
    cache_key = f"currency:convert:{data.from_currency}:{data.to_currency}:{data.amount}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    result = convert_currency(data.amount, data.from_currency, data.to_currency)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    cache_set(cache_key, result, ttl=3600)
    return result


@router.get("/currency/rates/{base}")
def currency_rates(base: str = "INR"):
    """Get latest exchange rates for a base currency."""
    import httpx
    from config import settings
    cache_key = f"currency:rates:{base.upper()}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    try:
        resp = httpx.get(f"{settings.EXCHANGE_RATE_API_URL}/{base}", timeout=10)
        data = resp.json()
        result = {
            "base": base,
            "rates": data.get("rates", {}),
            "last_updated": data.get("time_last_update_utc"),
        }
        cache_set(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch rates: {str(e)}")


# ── Maps ────────────────────────────────────────────────────────────────────

@router.get("/maps/geocode")
def maps_geocode(q: str = Query(..., description="Place name to geocode")):
    """Geocode a place name to lat/lon (OpenStreetMap Nominatim, free)."""
    cache_key = f"geocode:{q.lower().strip()}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    result = geocode_location(q)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    cache_set(cache_key, result, ttl=86400)
    return result


@router.get("/maps/airport/{airport_code}")
def maps_airport(airport_code: str, db: Session = Depends(get_db)):
    """Get airport location by IATA code."""
    import models
    airport = db.query(models.Airport).filter(models.Airport.code.ilike(airport_code)).first()
    if not airport:
        raise HTTPException(status_code=404, detail=f"Airport {airport_code} not found")
    result = get_airport_location(airport.code, airport.city)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "airport_code": airport.code,
        "airport_name": airport.name,
        "city": airport.city,
        **result,
    }


class DirectionsRequest(BaseModel):
    origin: str
    airport_name: str
    airport_city: str = ""


@router.post("/maps/directions")
def maps_directions(data: DirectionsRequest):
    """Get driving directions from origin to airport."""
    result = get_directions_to_airport(data.origin, data.airport_name, data.airport_city)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/maps/static")
def maps_static(lat: float = Query(...), lon: float = Query(...), zoom: int = Query(13, ge=1, le=19)):
    """Get a static map image URL for a location."""
    return {
        "url": get_static_map_url(lat, lon, zoom),
        "lat": lat,
        "lon": lon,
        "zoom": zoom,
    }


# ── SMS ─────────────────────────────────────────────────────────────────────

class SmsSendRequest(BaseModel):
    to_phone: str
    body: str


@router.post("/sms/send")
def sms_send(data: SmsSendRequest):
    """Send an SMS via Twilio (or mock fallback)."""
    result = send_sms(data.to_phone, data.body)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "SMS failed"))
    return result


class BookingSmsRequest(BaseModel):
    to_phone: str
    pnr: str
    flight_number: str
    departure_city: str
    arrival_city: str
    departure_time: str


@router.post("/sms/booking-confirmation")
def sms_booking_confirmation(data: BookingSmsRequest):
    """Send a booking confirmation via SMS + WhatsApp."""
    result = send_booking_confirmation_sms(
        data.to_phone, data.pnr, data.flight_number,
        data.departure_city, data.arrival_city, data.departure_time,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Notification failed"))
    return result


# ── WhatsApp ────────────────────────────────────────────────────────────────

class WhatsappSendRequest(BaseModel):
    to_phone: str
    body: str


@router.post("/whatsapp/send")
def whatsapp_send(data: WhatsappSendRequest):
    """Send a WhatsApp message via Twilio WhatsApp API (or mock fallback).

    On Twilio free trial, the recipient must first join the WhatsApp sandbox
    by sending 'join <sandbox-code>' to the Twilio WhatsApp number.
    """
    result = send_whatsapp(data.to_phone, data.body)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "WhatsApp failed"))
    return result


# ── Multi-channel Notification (SMS + WhatsApp) ─────────────────────────────

class MultiChannelRequest(BaseModel):
    to_phone: str
    body: str
    channels: list[str] = ["sms", "whatsapp"]


@router.post("/notify")
def notify_multi_channel(data: MultiChannelRequest):
    """Send a notification via multiple channels (SMS + WhatsApp).

    Defaults to both SMS and WhatsApp. Specify channels to select specific ones.
    """
    result = send_notification_message(data.to_phone, data.body, data.channels)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail="All channels failed")
    return result


# ── Email ───────────────────────────────────────────────────────────────────

class EmailSendRequest(BaseModel):
    to_email: str
    subject: str
    body: str


@router.post("/email/send")
def email_send(data: EmailSendRequest):
    """Send an email via SMTP/Resend (or mock fallback)."""
    result = send_email(data.to_email, data.subject, data.body)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Email failed"))
    return result


# ── API Status ──────────────────────────────────────────────────────────────

@router.get("/status")
def api_status():
    """Check which external APIs are configured."""
    from config import settings
    return {
        "weather": {
            "provider": "open-meteo",
            "configured": True,
            "url": settings.WEATHER_API_URL,
        },
        "currency": {
            "provider": "open.er-api.com",
            "configured": True,
            "url": settings.EXCHANGE_RATE_API_URL,
        },
        "maps": {
            "provider": "openstreetmap",
            "configured": True,
            "geocoding_url": settings.MAPS_GEOCODING_URL,
            "routing_url": settings.MAPS_ROUTING_URL,
        },
        "sms": {
            "provider": "twilio" if settings.TWILIO_ACCOUNT_SID else "mock",
            "configured": bool(
                settings.TWILIO_ACCOUNT_SID
                and (
                    (settings.TWILIO_API_KEY_SID and settings.TWILIO_API_KEY_SECRET)
                    or (settings.TWILIO_AUTH_TOKEN and settings.TWILIO_AUTH_TOKEN != "your_token")
                )
                and settings.TWILIO_FROM_NUMBER
                and settings.TWILIO_FROM_NUMBER != "+1234567890"
            ),
            "from_number": settings.TWILIO_FROM_NUMBER if settings.TWILIO_ACCOUNT_SID else None,
        },
        "whatsapp": {
            "provider": "twilio" if settings.TWILIO_ACCOUNT_SID else "mock",
            "configured": bool(
                settings.TWILIO_ACCOUNT_SID
                and settings.TWILIO_ACCOUNT_SID.startswith("AC")
                and (
                    (settings.TWILIO_API_KEY_SID and settings.TWILIO_API_KEY_SECRET)
                    or (settings.TWILIO_AUTH_TOKEN and settings.TWILIO_AUTH_TOKEN != "your_token")
                )
            ),
            "from_number": (settings.TWILIO_WHATSAPP_FROM_NUMBER or settings.TWILIO_FROM_NUMBER or "+14155238886") if settings.TWILIO_ACCOUNT_SID else None,
            "sandbox_mode": not bool(settings.TWILIO_WHATSAPP_FROM_NUMBER or (settings.TWILIO_FROM_NUMBER and settings.TWILIO_FROM_NUMBER != "+1234567890")),
        },
        "email": {
            "provider": "smtp" if settings.SMTP_HOST else ("resend" if settings.RESEND_API_KEY else "mock"),
            "configured": bool(
                (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASS)
                or settings.RESEND_API_KEY
            ),
        },
        "payment": {
            "provider": settings.PAYMENT_GATEWAY,
            "configured": True,
        },
    }
