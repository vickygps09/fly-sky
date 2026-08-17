"""LLM helper — picks between free-tier providers (Google Gemini or Groq)."""

from config import settings
from langchain_core.language_models import BaseChatModel


def get_llm(temperature: float = 0.7) -> BaseChatModel:
    """Return a chat LLM based on the configured provider.

    Both Google Gemini and Groq offer free tiers:
    - Gemini: https://aistudio.google.com/apikey (free tier: 15 RPM, 1500 RPD)
    - Groq:   https://console.groq.com/keys    (free tier: 30 RPM, 14400 RPD)
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "groq":
        from langchain_groq import ChatGroq
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set. Get a free key from https://console.groq.com/keys")
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=temperature,
            groq_api_key=settings.GROQ_API_KEY,
        )

    # Default: Gemini
    from langchain_google_genai import ChatGoogleGenerativeAI
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set. Get a free key from https://aistudio.google.com/apikey")
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=temperature,
        google_api_key=settings.GEMINI_API_KEY,
    )
