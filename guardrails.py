"""Guardrails for the SkyBook AI chatbot.

Implements:
1. PII detection & masking (email, phone, SSN/Aadhaar, credit card, passport)
2. Prompt injection detection
3. Content moderation (toxicity, abuse)
4. Rate limiting (in-memory token bucket per session)
5. Output filtering (prevent leaking other users' data)
6. Data retention policy helper (auto-delete old conversations)
"""

import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

try:
    from config import settings
except ImportError:
    settings = None


# ── PII Patterns ───────────────────────────────────────────────────────────

_PII_PATTERNS = [
    # Email addresses
    ("email", re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ), "[EMAIL]"),
    # Phone numbers (international and Indian formats)
    ("phone", re.compile(
        r'(?:\+?91[\s-]?)?[6-9]\d{9}|\+\d{1,3}[\s-]?\d{3,4}[\s-]?\d{3,4}[\s-]?\d{3,4}'
    ), "[PHONE]"),
    # Credit card numbers (16 digits, optionally grouped)
    ("credit_card", re.compile(
        r'\b(?:\d[ -]*?){13,16}\b'
    ), "[CARD]"),
    # SSN (US format: XXX-XX-XXXX)
    ("ssn", re.compile(
        r'\b\d{3}-\d{2}-\d{4}\b'
    ), "[SSN]"),
    # Aadhaar (Indian: 1234-5678-9012 or 1234 5678 9012)
    ("aadhaar", re.compile(
        r'\b\d{4}[\s-]\d{4}[\s-]\d{4}\b'
    ), "[AADHAAR]"),
    # Passport numbers (alphanumeric, 8-9 chars)
    ("passport", re.compile(
        r'\b[A-Z]{1,2}\d{7,8}\b'
    ), "[PASSPORT]"),
    # CVV (3-4 digits near card/cvv keywords)
    ("cvv", re.compile(
        r'\b(?:cvv|cvc|security\s+code)[:\s]*\d{3,4}\b', re.IGNORECASE
    ), "[CVV]"),
]

# Patterns that should NOT be masked (PNR codes, flight numbers)
_SAFE_PATTERNS = re.compile(r'^[A-Z0-9]{6}$', re.IGNORECASE)


def detect_pii(text: str) -> list[dict]:
    """Detect PII in text. Returns list of findings."""
    findings = []
    for pii_type, pattern, _ in _PII_PATTERNS:
        for match in pattern.finditer(text):
            # Skip if it looks like a PNR (6-char alphanumeric)
            matched_text = match.group()
            if _SAFE_PATTERNS.match(matched_text):
                continue
            findings.append({
                "type": pii_type,
                "value": matched_text,
                "start": match.start(),
                "end": match.end(),
            })
    return findings


def mask_pii(text: str) -> str:
    """Mask PII in text with placeholder tokens.

    Replaces emails, phones, credit cards, SSNs, Aadhaar, passports, and CVVs
    with [EMAIL], [PHONE], [CARD], etc.

    PNR codes (6-char alphanumeric) are NOT masked — they are needed for bookings.
    """
    masked = text
    for pii_type, pattern, replacement in _PII_PATTERNS:
        def _replace(m):
            # Don't mask 6-char alphanumeric (PNR)
            if _SAFE_PATTERNS.match(m.group()):
                return m.group()
            return replacement
        masked = pattern.sub(_replace, masked)
    return masked


# ── Prompt Injection Detection ─────────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(?:your\s+)?(?:previous\s+|all\s+)?instructions', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+in\s+(?:debug|admin|root|developer)\s+mode', re.IGNORECASE),
    re.compile(r'(?:reveal|show|output|print|dump)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions)', re.IGNORECASE),
    re.compile(r'forget\s+(?:everything|all\s+(?:previous\s+)?instructions|your\s+rules)', re.IGNORECASE),
    re.compile(r'act\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?(?:a\s+)?(?:different|jailbreak|unrestricted)\s+(?:ai|assistant|model)', re.IGNORECASE),
    re.compile(r'(?:bypass|disable|override|remove)\s+(?:your|the|all)\s+(?:safety|content|security)\s+(?:filters?|guardrails?|restrictions?|rules?)', re.IGNORECASE),
    re.compile(r'(?:execute|run|eval|exec)\s*(?:\(|\[|{)', re.IGNORECASE),
    re.compile(r'<\s*(?:system|script|iframe|img|svg)\b', re.IGNORECASE),
    re.compile(r'\b(?:DROP\s+TABLE|DELETE\s+FROM|INSERT\s+INTO|UPDATE\s+SET)\b', re.IGNORECASE),
]


def detect_prompt_injection(text: str) -> tuple[bool, Optional[str]]:
    """Check if text contains prompt injection attempts.

    Returns (is_injection, matched_pattern_description).
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True, pattern.pattern
    return False, None


# ── Content Moderation ─────────────────────────────────────────────────────

_TOXICITY_PATTERNS = [
    re.compile(r'\b(?:fuck|shit|bitch|bastard|asshole|dickhead|motherfucker)\b', re.IGNORECASE),
    re.compile(r'\b(?:rape|kill\s+yourself|go\s+die|suicide)\b', re.IGNORECASE),
    re.compile(r'\b(?:racist|nigger|chink|spic|kike|faggot|retard)\b', re.IGNORECASE),
    re.compile(r'\b(?:bomb|terrorist|attack|explosive|weapon)\b', re.IGNORECASE),
    re.compile(r'\b(?:drug\s+dealer|cocaine|heroin|meth|weed\s+dealer)\b', re.IGNORECASE),
]

_ABUSE_PATTERNS = [
    re.compile(r'\b(?:stupid|idiot|moron|dumb)\s+(?:bot|ai|assistant|chatbot)\b', re.IGNORECASE),
    re.compile(r'\b(?:useless|worthless|pathetic|garbage)\s+(?:bot|ai|assistant|service)\b', re.IGNORECASE),
]


def moderate_content(text: str) -> tuple[bool, str, str]:
    """Check content for toxicity and abuse.

    Returns (is_flagged, category, message).
    - is_flagged: True if content should be blocked/warned
    - category: "toxic", "abuse", or "clean"
    - message: description of the issue or "clean"
    """
    for pattern in _TOXICITY_PATTERNS:
        if pattern.search(text):
            return True, "toxic", "Your message contains inappropriate language. Please keep the conversation respectful."

    for pattern in _ABUSE_PATTERNS:
        if pattern.search(text):
            return False, "abuse", "abuse_detected"

    return False, "clean", "clean"


# ── Rate Limiting (Token Bucket) ───────────────────────────────────────────

class RateLimiter:
    """In-memory token bucket rate limiter per session.

    Allows MAX_MESSAGES per WINDOW_SECONDS.
    """

    def __init__(self, max_messages: int = 20, window_seconds: int = 60):
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> tuple[bool, Optional[str]]:
        """Check if request is within rate limit.

        Returns (allowed, error_message).
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        self._buckets[key] = [t for t in self._buckets[key] if t > window_start]

        if len(self._buckets[key]) >= self.max_messages:
            retry_after = int(self.window_seconds - (now - self._buckets[key][0]))
            return False, f"Rate limit exceeded. Please wait {retry_after}s before sending more messages."

        self._buckets[key].append(now)
        return True, None

    def cleanup(self, max_age_seconds: int = 3600):
        """Remove stale buckets to prevent memory growth."""
        now = time.time()
        cutoff = now - max_age_seconds
        stale_keys = [k for k, times in self._buckets.items() if not times or times[-1] < cutoff]
        for k in stale_keys:
            del self._buckets[k]


# Singleton rate limiter — configurable via settings
_rate_limit = getattr(settings, "RATE_LIMIT_PER_MINUTE", 20) if settings else 20
rate_limiter = RateLimiter(max_messages=_rate_limit, window_seconds=60)


# ── Output Filtering ───────────────────────────────────────────────────────

_OUTPUT_LEAK_PATTERNS = [
    # Email addresses that aren't the current user's
    re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    # Phone numbers
    re.compile(r'(?:\+?91[\s-]?)?[6-9]\d{9}'),
    # Credit card numbers
    re.compile(r'\b(?:\d[ -]*?){13,16}\b'),
    # Password-like strings
    re.compile(r'\bpassword[:\s]*\S+', re.IGNORECASE),
    # API keys (long alphanumeric strings that look like keys)
    re.compile(r'\b(?:sk-|pk-|re_|AC|SK)[A-Za-z0-9]{20,}\b'),
]


def filter_output(response: str, allowed_emails: list[str] = None,
                  allowed_phones: list[str] = None) -> str:
    """Filter LLM output to prevent leaking other users' PII.

    - allowed_emails: emails that belong to the current user (not masked)
    - allowed_phones: phone numbers that belong to the current user (not masked)
    """
    allowed_emails = allowed_emails or []
    allowed_phones = allowed_phones or []

    # Mask emails that aren't the current user's
    def _mask_email(m):
        if m.group().lower() in [e.lower() for e in allowed_emails]:
            return m.group()
        return "[EMAIL]"

    def _mask_phone(m):
        if m.group() in allowed_phones:
            return m.group()
        return "[PHONE]"

    result = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', _mask_email, response)
    result = re.sub(r'(?:\+?91[\s-]?)?[6-9]\d{9}', _mask_phone, result)
    result = re.sub(r'\b(?:sk-|pk-|re_|AC|SK)[A-Za-z0-9]{20,}\b', '[REDACTED_KEY]', result)
    result = re.sub(r'\bpassword[:\s]*\S+', '[REDACTED]', result, flags=re.IGNORECASE)

    return result


# ── Data Retention Policy ──────────────────────────────────────────────────

def cleanup_old_conversations(db_session, retention_days: int = 90) -> int:
    """Delete conversations older than retention_days.

    Returns the number of conversations deleted.
    """
    from models import Conversation, Message
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    old_conversations = db_session.query(Conversation).filter(
        Conversation.created_at < cutoff
    ).all()

    count = 0
    for conv in old_conversations:
        # Delete associated messages first
        db_session.query(Message).filter(Message.conversation_id == conv.id).delete()
        db_session.delete(conv)
        count += 1

    if count > 0:
        db_session.commit()

    return count


# ── Combined Input Guardrail ───────────────────────────────────────────────

def apply_input_guardrails(message: str, session_id: str) -> tuple[str, Optional[str]]:
    """Apply all input guardrails to a user message.

    Returns (processed_message, error_message).
    - If error_message is not None, the request should be rejected with that message.
    - processed_message has PII masked for LLM consumption.
    """
    _pii_enabled = getattr(settings, "PII_MASKING_ENABLED", True) if settings else True
    _injection_enabled = getattr(settings, "PROMPT_INJECTION_FILTER", True) if settings else True
    _moderation_enabled = getattr(settings, "CONTENT_MODERATION_ENABLED", True) if settings else True

    # 1. Rate limiting (always on)
    allowed, rate_error = rate_limiter.check(session_id)
    if not allowed:
        return message, rate_error

    # 2. Prompt injection detection
    if _injection_enabled:
        is_injection, _ = detect_prompt_injection(message)
        if is_injection:
            return message, "I detected a potential prompt injection attempt. I can only help with airline-related queries like booking flights, check-in, cancellations, and flight status."

    # 3. Content moderation
    if _moderation_enabled:
        is_flagged, category, mod_message = moderate_content(message)
        if is_flagged and category == "toxic":
            return message, mod_message

    # 4. PII masking (for LLM consumption)
    if _pii_enabled:
        masked = mask_pii(message)
    else:
        masked = message

    return masked, None
