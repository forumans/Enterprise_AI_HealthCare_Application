"""Appointment booking service with transaction-safe constraints."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Appointment, Doctor, DoctorAvailability, User
from .availability_service import release_slot


async def book_appointment(
    db: AsyncSession,
    *,
    tenant_id: str,
    doctor_id: str,
    patient_id: str,
    appointment_time: datetime,
    notes: str | None,
) -> Appointment:
    """Book an appointment and mark corresponding availability as booked.

    Enforces no-double-booking constraints from DB unique indexes and performs
    availability check before insert. The doctor must be in the tenant with a usable login: a doctor
    awaiting an admin's approval (or deactivated, or deleted) can't be booked.
    """

    doctor_login_active = (
        await db.execute(
            select(User.is_active)
            .join(Doctor, Doctor.user_id == User.id)
            .where(
                Doctor.id == doctor_id,
                Doctor.tenant_id == tenant_id,
                Doctor.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if doctor_login_active is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
    if not doctor_login_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This doctor isn't accepting appointments.")

    availability_stmt = (
        select(DoctorAvailability)
        .where(
            and_(
                DoctorAvailability.tenant_id == tenant_id,
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.slot_time == appointment_time,
            )
        )
        .with_for_update()
    )
    availability = (await db.execute(availability_stmt)).scalar_one_or_none()
    
    if availability is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested slot is not available.")
    
    if availability.status != "AVAILABLE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested slot is not available.")

    record = Appointment(
        tenant_id=tenant_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        slot_id=availability.id,  # Use the availability record's id as slot_id
        appointment_time=appointment_time,
        notes=notes,
    )
    db.add(record)
    availability.status = "BOOKED"

    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Appointment conflicts with existing booking.") from exc

    return record


async def reschedule_appointment(
    db: AsyncSession,
    *,
    appointment: Appointment,
    new_time: datetime,
) -> datetime:
    """Move an appointment to another slot of the same doctor, keeping every other detail.

    The sync_doctor_availability trigger only reacts to inserts, deletes and cancellations, so a
    time change has to free the old slot (by the release rule) and book the new one here. Only an
    AVAILABLE slot can be the target, so an appointment can't move into a blocked hour. Returns the
    previous time.
    """

    if new_time == appointment.appointment_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment is already at that time.")

    new_slot = (
        await db.execute(
            select(DoctorAvailability)
            .where(
                and_(
                    DoctorAvailability.tenant_id == appointment.tenant_id,
                    DoctorAvailability.doctor_id == appointment.doctor_id,
                    DoctorAvailability.slot_time == new_time,
                )
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if new_slot is None or new_slot.status != "AVAILABLE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested slot is not available.")

    old_slot = (
        await db.execute(
            select(DoctorAvailability)
            .where(
                and_(
                    DoctorAvailability.doctor_id == appointment.doctor_id,
                    DoctorAvailability.slot_time == appointment.appointment_time,
                )
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    old_time = appointment.appointment_time
    appointment.appointment_time = new_time
    appointment.slot_id = new_slot.id
    new_slot.status = "BOOKED"
    if old_slot is not None and old_slot.status == "BOOKED":
        release_slot(old_slot)  # stays BLOCKED if a range block wants the old hour

    try:
        await db.flush()
    except IntegrityError as exc:
        # unique_patient_time: the patient already has another appointment at the new time.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Appointment conflicts with existing booking.") from exc

    return old_time
