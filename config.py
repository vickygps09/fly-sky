"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LLM_PROVIDER: str = "gemini"

    # Database
    DATABASE_URL: str = "sqlite:///./airline_chatbot.db"

    # JWT
    SECRET_KEY: str = "change-this-to-a-random-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # App
    APP_NAME: str = "SkyBook AI"
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    # Payment
    PAYMENT_GATEWAY: str = "mock"
    PAYMENT_CURRENCY: str = "INR"

    # Notifications
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM_EMAIL: str = "noreply@skybook.ai"
    SMTP_FROM_NAME: str = "SkyBook AI"
    SMS_PROVIDER: str = "mock"

    # Resend (free tier — 3000 emails/month)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"

    # Redis
    REDIS_URL: str = ""

    # External APIs
    WEATHER_API_URL: str = "https://api.open-meteo.com/v1/forecast"
    EXCHANGE_RATE_API_URL: str = "https://open.er-api.com/v6/latest"

    # Twilio (SMS + WhatsApp) — Free trial: https://www.twilio.com/referral/RN8e7e
    # Auth method 1: Account SID + Auth Token (basic auth)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    # Auth method 2: API Key SID (SK...) + API Key Secret
    TWILIO_API_KEY_SID: str = ""
    TWILIO_API_KEY_SECRET: str = ""
    # Phone numbers
    TWILIO_FROM_NUMBER: str = ""
    TWILIO_WHATSAPP_FROM_NUMBER: str = ""
    # WhatsApp sandbox number (used when no dedicated WhatsApp number is set)
    TWILIO_WHATSAPP_SANDBOX_NUMBER: str = "+14155238886"
    # Trial mode: use predefined templates instead of custom message bodies
    TWILIO_TRIAL_MODE: bool = True
    # WhatsApp ContentSid for trial template (from Try out WhatsApp console page)
    TWILIO_WHATSAPP_CONTENT_SID: str = ""
    # Default SMS trial template name (used when no specific template matches)
    TWILIO_SMS_DEFAULT_TEMPLATE: str = "sms_order_confirmation"

    # Maps (OpenStreetMap Nominatim + OSRM — free, no key needed)
    MAPS_GEOCODING_URL: str = "https://nominatim.openstreetmap.org/search"
    MAPS_ROUTING_URL: str = "https://router.project-osrm.org/route/v1/driving"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
