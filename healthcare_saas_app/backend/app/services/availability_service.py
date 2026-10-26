"""Availability slots: default generation, the slot release rule, and range block/unblock."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutils import (
    DEFAULT_SLOT_DAYS,
    clinic_date,
    clinic_day_bounds,
    clinic_day_start,
    clinic_today,
    default_slot_times,
    office_hour_slots_in_range,
    same_wall_clock,
    to_utc,
    utc_now,
)
from ..models import Appointment, Doctor, DoctorAvailability, Patient, ScheduleBlock
from ..models.schedule_block import BLOCK_REASON_CATEGORIES
from .audit_service import write_audit_log

logger = logging.getLogger(__name__)

# Rows per INSERT: asyncpg allows at most 32767 bound parameters per statement
_INSERT_BATCH = 1000

# How far ahead a range block/unblock may reach (single-slot changes and booking stay at 30 days)
RANGE_HORIZON_DAYS = 180
# Blocks released (or ended) this long ago still show in the doctor's block list
RECENT_BLOCK_DAYS = 30
LIVE_APPOINTMENT_STATUSES = ("SCHEDULED", "CONFIRMED")
SCHEDULE_CHANGED = "The schedule changed. Review the changes again."


def released_status(block_id: str | None) -> str:
    """Release rule (BR-SLOT-19): a freed slot stays BLOCKED while a range block wants the hour blocked."""

    return "BLOCKED" if block_id else "AVAILABLE"


def release_slot(slot: DoctorAvailability) -> None:
    """Free a slot whose appointment was cancelled or moved away; same rule as the sync_doctor_availability trigger."""

    slot.status = released_status(slot.block_id)
    if not slot.block_id:
        slot.block_reason = None


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

    Open and blocked slots move, keeping their range block. Booked slots stay put, since a patient holds
    that exact time, and the hour they occupied is reopened in the new zone so the doctor's working hours
    are unchanged (BLOCKED if the booked slot was in a range block). Range blocks that still reach into the
    future move to the same local hours too, so "Unblock all" covers their slots. A slot
    that would land in the past, or on a time the doctor already has a slot for (such as a booked one),
    is dropped. The caller commits. Returns the number of slots placed at their new time.
    """

    now = to_utc(now) if now is not None else utc_now()
    blocks = (
        await db.execute(
            select(ScheduleBlock).where(
                ScheduleBlock.tenant_id == tenant_id,
                ScheduleBlock.end_time > now,
                ScheduleBlock.released_at.is_(None),
            )
        )
    ).scalars().all()
    for block in blocks:
        block.start_time = same_wall_clock(block.start_time, old_tz, new_tz)
        block.end_time = same_wall_clock(block.end_time, old_tz, new_tz)

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
            # A booked slot's reopened hour follows the release rule: still blocked if the doctor blocked it
            "status": released_status(row.block_id) if row.status == "BOOKED" else row.status,
            "block_reason": row.block_reason if row.status != "BOOKED" or row.block_id else None,
            "block_id": row.block_id,
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


# --- Range block / unblock (BR-SLOT-12..22) -----------------------------------------------------


def block_reason_text(category: str, note: str | None) -> str:
    """The reason copied onto each blocked slot, e.g. "Conference: Cardiology summit"."""

    label = BLOCK_REASON_CATEGORIES[category]
    return f"{label}: {note}" if note else label


def validate_block_reason(category: str | None, note: str | None) -> str | None:
    """Check a block's reason; returns the cleaned note (None when empty)."""

    if category not in BLOCK_REASON_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Please choose a reason.")
    note = (note or "").strip() or None
    if category == "OTHER" and not note:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Please describe the reason.")
    if note and len(note) > 500:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The note can be at most 500 characters.")
    return note


def normalize_range(start: datetime, end: datetime, *, now: datetime) -> tuple[datetime, datetime]:
    """Validate a half-open [start, end) range and move a past start forward to the next whole hour."""

    start, end, now = to_utc(start), to_utc(end), to_utc(now)
    if end <= start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End must be after start.")
    if end > now + timedelta(days=RANGE_HORIZON_DAYS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot change slots beyond {RANGE_HORIZON_DAYS} days.")
    next_hour = now.replace(minute=0, second=0, microsecond=0)
    if next_hour < now:
        next_hour += timedelta(hours=1)
    start = max(start, next_hour)
    if start >= end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Range is entirely in the past.")
    return start, end


async def lock_doctor_schedule(db: AsyncSession, doctor_id: str) -> None:
    """Serialize slot changes for one doctor until the transaction ends (bookings rely on their row lock)."""

    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('slots:' || :doctor_id))"), {"doctor_id": str(doctor_id)})


@dataclass
class RangePlan:
    """What a range block or unblock would do. Nothing is written until it is applied."""

    mode: str  # "block" or "unblock"
    start: datetime  # after moving a past start to the next whole hour
    end: datetime
    new_slots: list[dict]  # rows to insert: {"slot_time", "status"}
    open_slots: list[DoctorAvailability]  # AVAILABLE in range
    blocked_slots: list[DoctorAvailability]  # BLOCKED in range
    booked_slots: list[DoctorAvailability]  # BOOKED in range
    appointments: list[dict]  # live appointments in range (doctor/staff responses only)
    days_to_fill: int
    fingerprint: str

    @property
    def to_flag(self) -> list[DoctorAvailability]:
        return [row for row in self.booked_slots if not row.block_id]

    @property
    def flagged(self) -> list[DoctorAvailability]:
        return [row for row in self.booked_slots if row.block_id]

    def counts(self) -> dict:
        block = self.mode == "block"
        return {
            "slots_to_create": len(self.new_slots),
            "created_blocked": sum(1 for slot in self.new_slots if slot["status"] == "BLOCKED"),
            "to_block": len(self.open_slots) if block else 0,
            "already_blocked": len(self.blocked_slots) if block else 0,
            "to_flag": len(self.to_flag) if block else 0,
            "already_flagged": len(self.flagged) if block else 0,
            "to_open": 0 if block else len(self.blocked_slots),
            "already_open": 0 if block else len(self.open_slots),
            "to_unflag": 0 if block else len(self.flagged),
            "days_to_fill": self.days_to_fill,
        }

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            **self.counts(),
            "appointments": self.appointments,
            "fingerprint": self.fingerprint,
        }


async def plan_range_change(
    db: AsyncSession,
    doctor: Doctor,
    tz: ZoneInfo,
    start: datetime,
    end: datetime,
    mode: str,
    *,
    now: datetime | None = None,
    lock: bool = False,
) -> RangePlan:
    """Work out a range block/unblock of `doctor`'s office hours in [start, end), clinic zone `tz`.

    A clinic day in the range with no slot at all first gets its full default office-hour day (future hours
    only), so a partial-day block never leaves the rest of that day empty. A block also creates missing
    in-range hours (as BLOCKED) on days that have slots; an unblock never re-creates hours the doctor deleted.
    With lock=True the in-range rows are locked FOR UPDATE (take lock_doctor_schedule first).
    """

    now = to_utc(now) if now is not None else utc_now()
    start, end = normalize_range(start, end, now=now)
    hours = office_hour_slots_in_range(start, end, tz)
    hour_set = set(hours)
    days = sorted({clinic_date(hour, tz) for hour in hours})

    in_range = (
        select(DoctorAvailability)
        .where(
            DoctorAvailability.doctor_id == doctor.id,
            DoctorAvailability.slot_time >= start,
            DoctorAvailability.slot_time < end,
        )
        .order_by(DoctorAvailability.slot_time)
    )
    if lock:
        in_range = in_range.with_for_update()
    rows = [row for row in (await db.execute(in_range)).scalars().all() if row.slot_time in hour_set]

    covered_days: set[date] = set()
    if days:
        day_slots = (
            await db.execute(
                select(DoctorAvailability.slot_time).where(
                    DoctorAvailability.doctor_id == doctor.id,
                    DoctorAvailability.slot_time >= clinic_day_start(days[0], tz),
                    DoctorAvailability.slot_time < clinic_day_start(days[-1] + timedelta(days=1), tz),
                )
            )
        ).scalars().all()
        covered_days = {clinic_date(slot, tz) for slot in day_slots}

    blocking = mode == "block"
    empty_days = [day for day in days if day not in covered_days]
    new_slots = [
        {"slot_time": slot, "status": "BLOCKED" if blocking and slot in hour_set else "AVAILABLE"}
        for day in empty_days
        for slot in office_hour_slots_in_range(*clinic_day_bounds(day, tz), tz)
        if slot > now
    ]
    if blocking:
        existing = {row.slot_time for row in rows}
        new_slots += [
            {"slot_time": hour, "status": "BLOCKED"}
            for hour in hours
            if clinic_date(hour, tz) in covered_days and hour not in existing
        ]

    appointment_rows = (
        await db.execute(
            select(Appointment, Patient.full_name)
            .join(Patient, Patient.id == Appointment.patient_id)
            .where(
                Appointment.doctor_id == doctor.id,
                Appointment.tenant_id == doctor.tenant_id,
                Appointment.appointment_time >= start,
                Appointment.appointment_time < end,
                Appointment.status.in_(LIVE_APPOINTMENT_STATUSES),
                Appointment.deleted_at.is_(None),
            )
            .order_by(Appointment.appointment_time)
        )
    ).all()
    booked_by_time = {row.slot_time: row for row in rows if row.status == "BOOKED"}
    appointments = []
    for appointment, patient_name in appointment_rows:
        if appointment.appointment_time not in hour_set:
            continue
        slot = booked_by_time.get(appointment.appointment_time)
        appointments.append(
            {
                "appointment_id": appointment.id,
                "appointment_time": appointment.appointment_time.isoformat(),
                "patient_name": patient_name,
                "status": appointment.status,
                "needs_reschedule": bool(slot is not None and slot.block_id),
            }
        )

    digest = hashlib.sha256(f"{mode}|{start.isoformat()}|{end.isoformat()}".encode())
    for day in sorted(covered_days):
        digest.update(f"|d{day.isoformat()}".encode())
    for row in rows:
        digest.update(f"|s{row.slot_time.isoformat()},{row.status},{row.block_id or ''}".encode())
    for appointment_id in sorted(str(item["appointment_id"]) for item in appointments):
        digest.update(f"|a{appointment_id}".encode())

    return RangePlan(
        mode=mode,
        start=start,
        end=end,
        new_slots=new_slots,
        open_slots=[row for row in rows if row.status == "AVAILABLE"],
        blocked_slots=[row for row in rows if row.status == "BLOCKED"],
        booked_slots=list(booked_by_time.values()),
        appointments=appointments,
        days_to_fill=len(empty_days),
        fingerprint=digest.hexdigest(),
    )


async def _locked_plan(
    db: AsyncSession, doctor: Doctor, tz: ZoneInfo, start: datetime, end: datetime, mode: str, fingerprint: str | None, now: datetime
) -> RangePlan:
    """The plan recomputed under the doctor's lock; 409 unless it is exactly what the user previewed."""

    await lock_doctor_schedule(db, doctor.id)
    plan = await plan_range_change(db, doctor, tz, start, end, mode, now=now, lock=True)
    if not fingerprint or plan.fingerprint != fingerprint:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=SCHEDULE_CHANGED)
    return plan


async def _insert_slots(db: AsyncSession, doctor: Doctor, slots: list[dict]) -> list[str]:
    """Insert new slots in batches, skipping any that appeared meanwhile. Returns the new ids."""

    ids: list[str] = []
    for first in range(0, len(slots), _INSERT_BATCH):
        values = [{"tenant_id": doctor.tenant_id, "doctor_id": doctor.id, **slot} for slot in slots[first:first + _INSERT_BATCH]]
        result = await db.execute(
            insert(DoctorAvailability).values(values).on_conflict_do_nothing().returning(DoctorAvailability.id)
        )
        ids += [str(slot_id) for slot_id in result.scalars().all()]
    return ids


async def _update_slots(db: AsyncSession, rows: list[DoctorAvailability], **values) -> None:
    if rows:
        await db.execute(
            update(DoctorAvailability).where(DoctorAvailability.id.in_([row.id for row in rows])).values(**values),
            execution_options={"synchronize_session": False},
        )


async def _audit_flags(
    db: AsyncSession, doctor: Doctor, plan: RangePlan, rows: list[DoctorAvailability], block_id: str | None, flagged: bool, actor: str | None
) -> list[str]:
    """One audit entry per appointment whose "Needs reschedule" flag changed (ids only, no patient details)."""

    blocks_by_time = {row.slot_time: block_id or row.block_id for row in rows}
    changed = []
    for item in plan.appointments:
        slot_time = datetime.fromisoformat(item["appointment_time"])
        if slot_time not in blocks_by_time:
            continue
        changed.append(str(item["appointment_id"]))
        await write_audit_log(
            db,
            tenant_id=doctor.tenant_id,
            table_name="appointments",
            record_id=item["appointment_id"],
            action_type="UPDATE",
            old_data={"needs_reschedule": not flagged},
            new_data={"needs_reschedule": flagged, "block_id": blocks_by_time[slot_time]},
            performed_by=actor,
        )
    return changed


async def release_finished_blocks(db: AsyncSession, block_ids: set[str], actor: str | None, *, now: datetime | None = None) -> list[str]:
    """Mark blocks that no future slot references any more as released. Returns their ids."""

    if not block_ids:
        return []
    now = to_utc(now) if now is not None else utc_now()
    remaining = {
        str(block_id)
        for block_id in (
            await db.execute(
                select(DoctorAvailability.block_id)
                .where(DoctorAvailability.block_id.in_(block_ids), DoctorAvailability.slot_time > now)
                .distinct()
            )
        ).scalars().all()
    }
    finished = sorted(str(block_id) for block_id in block_ids if str(block_id) not in remaining)
    if finished:
        await db.execute(
            update(ScheduleBlock)
            .where(ScheduleBlock.id.in_(finished), ScheduleBlock.released_at.is_(None))
            .values(released_at=now, released_by=actor),
            execution_options={"synchronize_session": False},
        )
    return finished


async def apply_block(
    db: AsyncSession,
    doctor: Doctor,
    tz: ZoneInfo,
    start: datetime,
    end: datetime,
    *,
    category: str,
    note: str | None,
    fingerprint: str | None,
    actor: str | None,
    now: datetime | None = None,
) -> dict:
    """Block [start, end) exactly as previewed. Open slots become BLOCKED; booked slots stay BOOKED but carry
    the block (their appointments need rescheduling); already-blocked slots keep their block and reason. No
    appointment is changed. 409 if the schedule changed since the preview. The caller commits.
    """

    note = validate_block_reason(category, note)
    now = to_utc(now) if now is not None else utc_now()
    plan = await _locked_plan(db, doctor, tz, start, end, "block", fingerprint, now)
    reason = block_reason_text(category, note)
    to_flag = plan.to_flag
    created_blocked = [slot for slot in plan.new_slots if slot["status"] == "BLOCKED"]

    block = None
    if plan.open_slots or to_flag or created_blocked:
        block = ScheduleBlock(
            tenant_id=doctor.tenant_id,
            doctor_id=doctor.id,
            start_time=plan.start,
            end_time=plan.end,
            reason_category=category,
            reason_note=note,
            created_by=actor,
        )
        db.add(block)
        await db.flush()

    blocked_values = {"block_id": block.id if block is not None else None, "block_reason": reason}
    new_ids = await _insert_slots(
        db,
        doctor,
        [{**slot, **blocked_values} if slot["status"] == "BLOCKED" else {**slot, "block_id": None, "block_reason": None} for slot in plan.new_slots],
    )
    if block is None:
        return {"message": "Nothing new to block in this range.", "block_id": None, **plan.counts(), "needs_reschedule": len(plan.appointments)}

    await _update_slots(db, plan.open_slots, status="BLOCKED", **blocked_values)
    await _update_slots(db, to_flag, **blocked_values)
    flagged_ids = await _audit_flags(db, doctor, plan, to_flag, block.id, True, actor)
    await write_audit_log(
        db,
        tenant_id=doctor.tenant_id,
        table_name="schedule_blocks",
        record_id=block.id,
        action_type="INSERT",
        old_data=None,
        new_data={
            "doctor_id": doctor.id,
            "start": plan.start.isoformat(),
            "end": plan.end.isoformat(),
            "reason_category": category,
            **plan.counts(),
            "slot_ids": new_ids + [str(row.id) for row in plan.open_slots + to_flag],
            "flagged_appointment_ids": flagged_ids,
        },
        performed_by=actor,
    )
    return {"message": "Range blocked.", "block_id": block.id, **plan.counts(), "needs_reschedule": len(plan.appointments)}


async def apply_unblock(
    db: AsyncSession,
    doctor: Doctor,
    tz: ZoneInfo,
    start: datetime,
    end: datetime,
    *,
    fingerprint: str | None,
    actor: str | None,
    now: datetime | None = None,
) -> dict:
    """Unblock [start, end) exactly as previewed. Blocked slots become AVAILABLE (whatever blocked them);
    booked slots lose their block, so their appointments no longer need rescheduling, and are otherwise
    unchanged. Empty days get default slots; deleted hours are not re-created. The caller commits.
    """

    now = to_utc(now) if now is not None else utc_now()
    plan = await _locked_plan(db, doctor, tz, start, end, "unblock", fingerprint, now)
    to_unflag = plan.flagged
    touched_blocks = {str(row.block_id) for row in plan.blocked_slots + to_unflag if row.block_id}

    unflagged_ids = await _audit_flags(db, doctor, plan, to_unflag, None, False, actor)
    new_ids = await _insert_slots(db, doctor, [{**slot, "block_id": None, "block_reason": None} for slot in plan.new_slots])
    await _update_slots(db, plan.blocked_slots, status="AVAILABLE", block_id=None, block_reason=None)
    await _update_slots(db, to_unflag, block_id=None, block_reason=None)
    released = await release_finished_blocks(db, touched_blocks, actor, now=now)

    if plan.blocked_slots or to_unflag or new_ids:
        # An unblock may span several blocks (or single-slot blocks with none), so the entry names the doctor
        await write_audit_log(
            db,
            tenant_id=doctor.tenant_id,
            table_name="schedule_blocks",
            record_id=doctor.id,
            action_type="UPDATE",
            old_data=None,
            new_data={
                "doctor_id": doctor.id,
                "start": plan.start.isoformat(),
                "end": plan.end.isoformat(),
                **plan.counts(),
                "block_ids": sorted(touched_blocks),
                "released_block_ids": released,
                "slot_ids": new_ids + [str(row.id) for row in plan.blocked_slots + to_unflag],
                "unflagged_appointment_ids": unflagged_ids,
            },
            performed_by=actor,
        )
    return {"message": "Range unblocked.", **plan.counts(), "released_block_ids": released}


async def list_blocks(db: AsyncSession, doctor: Doctor, *, now: datetime | None = None) -> list[dict]:
    """The doctor's active and partially released blocks, plus those released (or ended) in the last 30 days.

    State comes from the slots: Released when no future slot references the block; Partially released when
    some future hour in its range has been opened (AVAILABLE, or booked without a block); otherwise Active.
    """

    now = to_utc(now) if now is not None else utc_now()
    blocks = (
        await db.execute(
            select(ScheduleBlock)
            .where(
                ScheduleBlock.doctor_id == doctor.id,
                ScheduleBlock.tenant_id == doctor.tenant_id,
                func.coalesce(ScheduleBlock.released_at, ScheduleBlock.end_time) > now - timedelta(days=RECENT_BLOCK_DAYS),
            )
            .order_by(ScheduleBlock.start_time)
        )
    ).scalars().all()
    if not blocks:
        return []

    referenced = {
        (str(block_id), slot_status): count
        for block_id, slot_status, count in (
            await db.execute(
                select(DoctorAvailability.block_id, DoctorAvailability.status, func.count())
                .where(DoctorAvailability.block_id.in_([block.id for block in blocks]), DoctorAvailability.slot_time > now)
                .group_by(DoctorAvailability.block_id, DoctorAvailability.status)
            )
        ).all()
    }

    result = []
    for block in blocks:
        blocked = referenced.get((str(block.id), "BLOCKED"), 0)
        flagged = referenced.get((str(block.id), "BOOKED"), 0)
        opened = 0
        if block.released_at is None and blocked + flagged:
            opened = (
                await db.execute(
                    select(func.count()).select_from(DoctorAvailability).where(
                        DoctorAvailability.doctor_id == doctor.id,
                        DoctorAvailability.slot_time >= max(block.start_time, now),
                        DoctorAvailability.slot_time < block.end_time,
                        or_(
                            DoctorAvailability.status == "AVAILABLE",
                            (DoctorAvailability.status == "BOOKED") & DoctorAvailability.block_id.is_(None),
                        ),
                    )
                )
            ).scalar_one()
        if block.released_at is not None or not blocked + flagged:
            state = "RELEASED"
        elif opened:
            state = "PARTIALLY_RELEASED"
        else:
            state = "ACTIVE"
        result.append(
            {
                "id": block.id,
                "start": block.start_time.isoformat(),
                "end": block.end_time.isoformat(),
                "reason_category": block.reason_category,
                "reason_label": BLOCK_REASON_CATEGORIES.get(block.reason_category, block.reason_category),
                "reason_note": block.reason_note,
                "created_at": block.created_at.isoformat(),
                "released_at": block.released_at.isoformat() if block.released_at else None,
                "state": state,
                "blocked_hours": blocked,
                "needs_reschedule": flagged,
                "opened_hours": opened,
            }
        )
    return result
