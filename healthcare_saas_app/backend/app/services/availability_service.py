"""Default availability slot generation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutils import (
    DEFAULT_SLOT_DAYS,
    clinic_date,
    clinic_day_start,
    clinic_today,
    default_slot_times,
    same_wall_clock,
    to_utc,
    utc_now,
)
from ..models import Doctor, DoctorAvailability

logger = logging.getLogger(__name__)

# Rows per INSERT: asyncpg allows at most 32767 bound parameters per statement
_INSERT_BATCH = 1000


async def ensure_default_slots(
    db: AsyncSession,
    doctor: Doctor,
    tz: ZoneInfo,
    *,
    now: datetime | None = None,
    days: int = DEFAULT_SLOT_DAYS,
) -> int:
    """Create default office-hour slots for each of the next `days` days in clinic zone `tz` that has none.

    Keeps a rolling window of bookable days instead of waiting until a doctor has no slots left.
    A day that already has any slot (any status, past or future) is left untouched, so a doctor's
    own changes to that day are never overwritten. Inserts skip slots that already exist, so
    concurrent requests can't fail on the (doctor_id, slot_time) unique index.

    Returns the number of slots requested for insertion.
    """

    now = to_utc(now) if now is not None else utc_now()
    candidates = default_slot_times(tz, now, days)
    if not candidates:
        return 0

    today = clinic_today(tz, now)
    existing = (
        await db.execute(
            select(DoctorAvailability.slot_time).where(
                DoctorAvailability.doctor_id == doctor.id,
                DoctorAvailability.slot_time >= clinic_day_start(today, tz),
                DoctorAvailability.slot_time < clinic_day_start(today + timedelta(days=days), tz),
            )
        )
    ).scalars().all()
    covered_days = {clinic_date(slot, tz) for slot in existing}

    missing = [slot for slot in candidates if clinic_date(slot, tz) not in covered_days]
    if not missing:
        return 0

    stmt = (
        insert(DoctorAvailability)
        .values(
            [
                {"tenant_id": doctor.tenant_id, "doctor_id": doctor.id, "slot_time": slot, "status": "AVAILABLE"}
                for slot in missing
            ]
        )
        .on_conflict_do_nothing()
    )
    try:
        await db.execute(stmt)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("Failed to create default availability slots for doctor %s", doctor.id)
        return 0
    return len(missing)


async def keep_slot_hours_in_new_zone(
    db: AsyncSession,
    tenant_id: str,
    old_tz: ZoneInfo,
    new_tz: ZoneInfo,
    *,
    now: datetime | None = None,
) -> int:
    """After a clinic changes its time zone, keep each doctor's future schedule at the same local hours
    (a 9 AM slot becomes a 9 AM slot in the new zone).

    Open and blocked slots move. Booked slots stay put, since a patient holds that exact time, and the
    hour they occupied is reopened in the new zone so the doctor's working hours are unchanged. A slot
    that would land in the past, or on a time the doctor already has a slot for (such as a booked one),
    is dropped. The caller commits. Returns the number of slots placed at their new time.
    """

    now = to_utc(now) if now is not None else utc_now()
    rows = (
        await db.execute(
            select(DoctorAvailability).where(
                DoctorAvailability.tenant_id == tenant_id,
                DoctorAvailability.slot_time > now,
            )
        )
    ).scalars().all()
    if not rows:
        return 0

    booked = [row for row in rows if row.status == "BOOKED"]
    movable = [row for row in rows if row.status != "BOOKED"]
    moved = [
        {
            "tenant_id": row.tenant_id,
            "doctor_id": row.doctor_id,
            "slot_time": same_wall_clock(row.slot_time, old_tz, new_tz),
            "status": "AVAILABLE" if row.status == "BOOKED" else row.status,
            "block_reason": None if row.status == "BOOKED" else row.block_reason,
        }
        for row in movable + booked
    ]
    moved = [slot for slot in moved if slot["slot_time"] > now]
    if movable:
        await db.execute(
            delete(DoctorAvailability).where(DoctorAvailability.id.in_([row.id for row in movable])),
            execution_options={"synchronize_session": False},
        )
        for row in movable:
            db.expunge(row)
    placed = 0
    for start in range(0, len(moved), _INSERT_BATCH):
        result = await db.execute(
            insert(DoctorAvailability).values(moved[start:start + _INSERT_BATCH]).on_conflict_do_nothing()
        )
        placed += result.rowcount
    return placed
