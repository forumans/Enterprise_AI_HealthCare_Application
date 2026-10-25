"""Field rules shared by registration, admin user creation and profile updates.

The browser checks the same rules (frontend/src/utils, the registration and profile pages); the server
enforces them too, so a request that bypasses the UI can't store a malformed email, phone, gender or date
of birth. Each check raises ValueError, which Pydantic validators turn into the generic 422 response.
"""

from __future__ import annotations

import re
from datetime import date

from ..core.timeutils import utc_today as today

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9\-\s]{10,15}$")
GENDERS = {"MALE", "FEMALE", "OTHER", "PREFER_NOT_TO_SAY"}
MAX_AGE_YEARS = 120
MIN_DOCTOR_AGE_YEARS = 18


def optional_text(value, max_length: int) -> str | None:
    """A trimmed string (None when empty); ValueError for non-strings or values over max_length."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("expected text")
    value = value.strip()
    if len(value) > max_length:
        raise ValueError("value too long")
    return value or None


def valid_full_name(value) -> str | None:
    """Trimmed name of 3-255 characters; None when empty (the caller keeps the stored name)."""
    value = optional_text(value, 255)
    if value is not None and len(value) < 3:
        raise ValueError("name too short")
    return value


def valid_email(value: str) -> str:
    value = value.strip()
    if not EMAIL_PATTERN.match(value):
        raise ValueError("invalid email")
    return value


def valid_phone(value: str | None) -> str | None:
    """Empty means "not given"; anything else must be 10-15 digits, spaces or dashes, optional leading +."""
    value = (value or "").strip()
    if not value:
        return None
    if not PHONE_PATTERN.match(value):
        raise ValueError("invalid phone")
    return value


def valid_gender(value: str | None) -> str | None:
    """One of the gender_type values, any case ("Male" -> "MALE"); empty means not given."""
    value = (value or "").strip().upper().replace(" ", "_")
    if not value:
        return None
    if value not in GENDERS:
        raise ValueError("invalid gender")
    return value


def _age_on(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def valid_birth_date(value: date | None) -> date | None:
    """Not in the future and not more than 120 years ago."""
    if value is None:
        return None
    now = today()
    if value > now or _age_on(value, now) > MAX_AGE_YEARS:
        raise ValueError("invalid date of birth")
    return value


def valid_doctor_birth_date(value: date | None) -> date | None:
    """As valid_birth_date, and the doctor is at least 18 today."""
    value = valid_birth_date(value)
    if value is not None and _age_on(value, today()) < MIN_DOCTOR_AGE_YEARS:
        raise ValueError("doctor under 18")
    return value
