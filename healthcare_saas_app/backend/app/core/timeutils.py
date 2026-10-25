"""Timezone helpers shared by routes and services.

All timestamp columns are TIMESTAMPTZ (see migrations/003_convert_timestamps_to_timestamptz.sql),
so every datetime passed to or read from the database must be timezone-aware. asyncpg silently
interprets a *naive* datetime bound to a TIMESTAMPTZ column as the Python process's local time,
so never build naive datetimes for queries - use these helpers instead.

Each clinic (tenant) has its own IANA time zone (`tenants.timezone`, migration 008). The clinic-calendar
helpers take that zone explicitly; routes get it from `CurrentIdentity.clinic_tz`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, available_timezones

UTC = timezone.utc

# Zone given to a clinic created without one (the first clinic of a new deployment, or a tenant row
# inserted by the operator without a timezone). Each clinic's own zone lives in tenants.timezone.
DEFAULT_CLINIC_TIMEZONE = os.environ.get("CLINIC_TIMEZONE", "America/New_York")

# Hourly slots run from 8 AM through the 11 PM slot (last slot starts at 11 PM), clinic local time.
WORKDAY_FIRST_SLOT_HOUR = 8
WORKDAY_LAST_SLOT_HOUR = 23

# How many days of default slots to pre-populate when a doctor has none.
DEFAULT_SLOT_DAYS = 7


@lru_cache(maxsize=1)
def _known_timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_valid_timezone(name: str) -> bool:
    """Whether `name` is an IANA zone this server knows (e.g. "America/Chicago", "Asia/Kolkata")."""

    return name in _known_timezones()


@lru_cache(maxsize=256)
def clinic_zone(name: str | None) -> ZoneInfo:
    """The ZoneInfo for a clinic's stored zone name; unknown or empty names fall back to the default zone."""

    return ZoneInfo(name if name and is_valid_timezone(name) else DEFAULT_CLINIC_TIMEZONE)


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


def clinic_today(tz: ZoneInfo, now: datetime | None = None) -> date:
    """Today's calendar date in the clinic's timezone."""

    return (to_utc(now) if now is not None else utc_now()).astimezone(tz).date()


def clinic_date(value: datetime, tz: ZoneInfo) -> date:
    """The clinic-local calendar date of an instant."""

    return to_utc(value).astimezone(tz).date()


def clinic_day_start(day: date, tz: ZoneInfo) -> datetime:
    """The UTC instant of local midnight at the start of `day` in the clinic's timezone."""

    return datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(UTC)


def clinic_day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[start, end) UTC range covering clinic-local `day` (23 or 25 hours on DST change days)."""

    return clinic_day_start(day, tz), clinic_day_start(day + timedelta(days=1), tz)


def clinic_week_bounds(anchor: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[start, end) UTC range of the clinic-local Monday-to-Sunday week containing `anchor`."""

    monday = anchor - timedelta(days=anchor.weekday())
    return clinic_day_start(monday, tz), clinic_day_start(monday + timedelta(days=7), tz)


def same_wall_clock(value: datetime, old_tz: ZoneInfo, new_tz: ZoneInfo) -> datetime:
    """The instant showing the same local date and time in `new_tz` as `value` shows in `old_tz` (as aware UTC).

    Used when a clinic changes its zone: a 9 AM slot stays a 9 AM slot.
    """

    local = to_utc(value).astimezone(old_tz)
    return local.replace(tzinfo=new_tz).astimezone(UTC)


def default_slot_times(tz: ZoneInfo, now: datetime | None = None, days: int = DEFAULT_SLOT_DAYS) -> list[datetime]:
    """Hourly office-hour slots in clinic local time for the next `days` days, as aware UTC.

    Only slots strictly after `now` are returned.
    """

    now_utc = to_utc(now) if now is not None else utc_now()
    local_today = now_utc.astimezone(tz).date()
    slots: list[datetime] = []
    for days_ahead in range(days):
        local_date = local_today + timedelta(days=days_ahead)
        for hour in range(WORKDAY_FIRST_SLOT_HOUR, WORKDAY_LAST_SLOT_HOUR + 1):
            slot = datetime(local_date.year, local_date.month, local_date.day, hour, tzinfo=tz).astimezone(UTC)
            if slot > now_utc:
                slots.append(slot)
    return slots
