"""Timezone helpers shared by routes and services.

All timestamp columns are TIMESTAMPTZ (see migrations/003_convert_timestamps_to_timestamptz.sql),
so every datetime passed to or read from the database must be timezone-aware. asyncpg silently
interprets a *naive* datetime bound to a TIMESTAMPTZ column as the Python process's local time,
so never build naive datetimes for queries - use these helpers instead.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc

# Clinic's local timezone - office hours are defined in this zone, and DST is handled by the
# IANA rules (e.g. 8 AM stays 8 AM local across the spring/fall clock changes).
# Override with the CLINIC_TIMEZONE environment variable if the clinic is not in US Eastern.
CLINIC_TZ = ZoneInfo(os.environ.get("CLINIC_TIMEZONE", "America/New_York"))

# Hourly slots run from 8 AM through the 11 PM slot (last slot starts at 11 PM), clinic local time.
WORKDAY_FIRST_SLOT_HOUR = 8
WORKDAY_LAST_SLOT_HOUR = 23

# How many days of default slots to pre-populate when a doctor has none.
DEFAULT_SLOT_DAYS = 7


def utc_now() -> datetime:
    """Current time as an aware UTC datetime."""

    return datetime.now(UTC)


def to_utc(value: datetime) -> datetime:
    """Normalize to aware UTC. Naive values are treated as UTC (the API's long-standing contract)."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_client_datetime(value: str) -> datetime:
    """Parse an ISO-8601 string from a client (with or without offset/'Z') into aware UTC.

    Raises ValueError on malformed input.
    """

    return to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def utc_day_start(day: date) -> datetime:
    """Midnight UTC at the start of the given calendar day."""

    return datetime.combine(day, time.min, tzinfo=UTC)


def utc_today() -> date:
    """Today's date in UTC (independent of the server's local timezone)."""

    return utc_now().date()


def default_slot_times(now: datetime | None = None, days: int = DEFAULT_SLOT_DAYS) -> list[datetime]:
    """Hourly office-hour slots in clinic local time for the next `days` days, as aware UTC.

    Only slots strictly after `now` are returned.
    """

    now_utc = to_utc(now) if now is not None else utc_now()
    local_today = now_utc.astimezone(CLINIC_TZ).date()
    slots: list[datetime] = []
    for days_ahead in range(days):
        local_date = local_today + timedelta(days=days_ahead)
        for hour in range(WORKDAY_FIRST_SLOT_HOUR, WORKDAY_LAST_SLOT_HOUR + 1):
            slot = datetime(local_date.year, local_date.month, local_date.day, hour, tzinfo=CLINIC_TZ).astimezone(UTC)
            if slot > now_utc:
                slots.append(slot)
    return slots
