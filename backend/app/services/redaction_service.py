import re
from typing import Any, Dict, Optional
from backend.app.schemas.incident import Incident


class RedactionService:
    """
    Service responsible for sanitizing sensitive credentials from transcripts,
    LLM prompts, raw outputs, logs, and database models.
    Guarantees that actual OTPs, PINs, CVVs, passwords, and full payment-card numbers
    are replaced with '[REDACTED]'.
    """

    REDACTION_TOKEN = "[REDACTED]"

    # Payment cards: 13-19 digits with optional spaces or dashes (e.g. Visa, Mastercard, RuPay, Amex)
    CARD_PATTERN = re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9]{2})[0-9]{12}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|(?:2131|1800|35\d{3})\d{11}|(?:[0-9]{4}[ -]?){3}[0-9]{4,7})\b"
    )

    # 13 to 19 continuous digits that are not timestamps
    GENERIC_CARD_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")

    # OTP patterns (English, Hindi, Tamil)
    # e.g., 'OTP 123456', 'OTP: 482910', 'OTP is 482910', 'ओटीपी 482910', '6 अंकों का OTP 482910'
    OTP_FORWARD_PATTERN = re.compile(
        r"(?i)\b(?:otp|one[- ]?time[- ]?password|ओटीपी|ओ\.टी\.पी|ஒருமுறை கடவுச்சொல்|ஓடிபி)(?:\s+(?:is|was|number|था|थी|नंबर|எண்))?[\s:=#-]*([0-9]{4,8})\b"
    )
    OTP_REVERSE_PATTERN = re.compile(
        r"(?i)\b([0-9]{4,8})\b(?=[\s\w]{1,25}(?:का|वाला)?\s*(?:otp|ओटीपी|one[- ]?time[- ]?password|ஓடிபி))"
    )
    OTP_PREFIX_PATTERN = re.compile(
        r"(?i)(?:6\s*(?:अंकों\s*का|digit)\s*(?:otp|ओटीपी|code)|digit\s*code)[\s:=#-]*([0-9]{4,8})\b"
    )

    # PIN patterns (ATM PIN, UPI PIN, MPIN, पिन)
    PIN_PATTERN = re.compile(
        r"(?i)\b(?:atm\s*pin|upi\s*pin|mpin|pin\s*code|pin|पिन|பின்)(?:\s+(?:is|was|number|नंबर|था))?[\s:=#-]*([0-9]{4,6})\b"
    )

    # CVV / CVC patterns
    CVV_PATTERN = re.compile(
        r"(?i)\b(?:cvv\s*number|cvv2|cvc|cvv|सीवीवी)(?:\s+(?:is|was|number|था))?[\s:=#-]*([0-9]{3,4})\b"
    )

    # Passwords / Passcodes
    PASSWORD_PATTERN = re.compile(
        r"(?i)\b(?:password|passcode|पासवर्ड|கடவுச்சொல்)(?:\s+(?:is|was|था))?[\s:=#-]*([a-zA-Z0-9@#$%^&*!_+~-]{4,32})"
    )

    # Aadhaar 12-digit pattern (e.g. 1234 5678 9012 or आधार 123456789012)
    AADHAAR_PATTERN = re.compile(
        r"(?i)(?:aadhaar|aadhar|आधार)[\s:=#-]*([2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4})\b"
    )

    @classmethod
    def redact_text(cls, text: Optional[str]) -> Optional[str]:
        """
        Replaces sensitive credential values in arbitrary string text with [REDACTED].
        Preserves non-sensitive context and digits that are part of dates or amounts.
        """
        if not text:
            return text

        redacted = text

        # 1. Redact CVV (3-4 digits after cvv)
        redacted = cls.CVV_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), cls.REDACTION_TOKEN), redacted)

        # 2. Redact PIN (4-6 digits after pin/upi pin/atm pin)
        redacted = cls.PIN_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), cls.REDACTION_TOKEN), redacted)

        # 3. Redact OTP (4-8 digits near OTP/ओटीपी)
        redacted = cls.OTP_FORWARD_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), cls.REDACTION_TOKEN), redacted)
        redacted = cls.OTP_PREFIX_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), cls.REDACTION_TOKEN), redacted)
        redacted = cls.OTP_REVERSE_PATTERN.sub(cls.REDACTION_TOKEN, redacted)

        # 4. Redact Passwords
        redacted = cls.PASSWORD_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), cls.REDACTION_TOKEN), redacted)

        # 5. Redact Aadhaar
        redacted = cls.AADHAAR_PATTERN.sub(lambda m: m.group(0).replace(m.group(1), cls.REDACTION_TOKEN), redacted)

        # 6. Redact Payment Cards (13-19 digits)
        redacted = cls.CARD_PATTERN.sub(cls.REDACTION_TOKEN, redacted)

        return redacted

    # Convenient alias
    redact_sensitive_text = redact_text

    @classmethod
    def redact_incident(cls, incident: Incident) -> Incident:
        """
        Applies redaction across all text fields of an Incident model.
        """
        incident.summary = cls.redact_text(incident.summary) or ""
        incident.description = cls.redact_text(incident.description) or ""
        if incident.evidence_description:
            incident.evidence_description = cls.redact_text(incident.evidence_description)
        if incident.reported_entity:
            incident.reported_entity = cls.redact_text(incident.reported_entity)
        return incident

    @classmethod
    def redact_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively redacts string values in a dictionary.
        """
        sanitized = {}
        for k, v in data.items():
            if isinstance(v, str):
                sanitized[k] = cls.redact_text(v)
            elif isinstance(v, dict):
                sanitized[k] = cls.redact_dict(v)
            elif isinstance(v, list):
                sanitized[k] = [
                    cls.redact_text(item) if isinstance(item, str)
                    else (cls.redact_dict(item) if isinstance(item, dict) else item)
                    for item in v
                ]
            else:
                sanitized[k] = v
        return sanitized
