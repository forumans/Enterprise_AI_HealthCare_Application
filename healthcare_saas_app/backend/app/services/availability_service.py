"""Default availability slot generation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutils import (
    DEFAULT_SLOT_DAYS,
    clinic_date,
    clinic_day_start,
    clinic_today,
    default_slot_times,
    to_utc,
    utc_now,
)
from ..models import Doctor, DoctorAvailability

logger = logging.getLogger(__name__)


async def ensure_default_slots(
    db: AsyncSession,
    doctor: Doctor,
    *,
    now: datetime | None = None,
    days: int = DEFAULT_SLOT_DAYS,
) -> int:
    """Create default office-hour slots for each of the next `days` clinic-local days that has none.

    Keeps a rolling window of bookable days instead of waiting until a doctor has no slots left.
    A day that already has any slot (any status, past or future) is left untouched, so a doctor's
    own changes to that day are never overwritten. Inserts skip slots that already exist, so
    concurrent requests can't fail on the (doctor_id, slot_time) unique index.

    Returns the number of slots requested for insertion.
    """

    now = to_utc(now) if now is not None else utc_now()
    candidates = default_slot_times(now, days)
    if not candidates:
        return 0

    today = clinic_today(now)
    existing = (
        await db.execute(
            select(DoctorAvailability.slot_time).where(
                DoctorAvailability.doctor_id == doctor.id,
                DoctorAvailability.slot_time >= clinic_day_start(today),
                DoctorAvailability.slot_time < clinic_day_start(today + timedelta(days=days)),
            )
        )
    ).scalars().all()
    covered_days = {clinic_date(slot) for slot in existing}

    missing = [slot for slot in candidates if clinic_date(slot) not in covered_days]
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
