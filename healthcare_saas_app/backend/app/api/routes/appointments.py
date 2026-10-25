"""Appointment routes."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...core.timeutils import clinic_today, clinic_week_bounds, parse_client_datetime, utc_now
from ...models import Appointment, Patient, Doctor, DoctorAvailability
from ...services.appointment_service import book_appointment, reschedule_appointment
from ...services.audit_service import write_audit_log

router = APIRouter()


class CreateAppointmentRequest(BaseModel):
    doctor_id: str
    slot: str = Field(description="ISO datetime string for appointment_time")
    reason: str = Field(min_length=5)
    patient_id: str | None = Field(default=None, description="Required for support staff booking on behalf of a patient")


class UpdateAppointmentStatusRequest(BaseModel):
    status: str


class RescheduleAppointmentRequest(BaseModel):
    slot: str = Field(description="ISO datetime string for the new appointment_time")


class UpdateAppointmentRequest(BaseModel):
    reason: str = Field(min_length=5)


def _week_bounds(from_date: date | None, identity: CurrentIdentity) -> tuple[datetime, datetime]:
    return clinic_week_bounds(from_date or clinic_today(identity.clinic_tz), identity.clinic_tz)


async def _own_doctor_id(db: AsyncSession, identity: CurrentIdentity) -> str | None:
    """Doctor profile id of the logged-in doctor (None if they have none in this tenant)."""
    return (
        await db.execute(
            select(Doctor.id).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _own_patient_id(db: AsyncSession, identity: CurrentIdentity) -> str | None:
    """Patient profile id of the logged-in patient (None if they have none in this tenant)."""
    return (
        await db.execute(
            select(Patient.id).where(
                Patient.user_id == identity.user_id,
                Patient.tenant_id == identity.tenant_id,
                Patient.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


def _scope_to_caller(stmt, identity: CurrentIdentity, own_id: str | None):
    """Limit an appointment query to what the caller may see: patients their own, doctors their own,
    admins and support staff the whole tenant. Returns None when the caller has no profile to scope by."""
    role = (identity.role or "").upper()
    if role in ("ADMIN", "SUPPORT_STAFF"):
        return stmt
    if own_id is None:
        return None
    return stmt.where(Appointment.patient_id == own_id) if role == "PATIENT" else stmt.where(Appointment.doctor_id == own_id)


async def _caller_profile_id(db: AsyncSession, identity: CurrentIdentity) -> str | None:
    role = (identity.role or "").upper()
    if role == "PATIENT":
        return await _own_patient_id(db, identity)
    if role == "DOCTOR":
        return await _own_doctor_id(db, identity)
    return None


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: CreateAppointmentRequest,
    identity: CurrentIdentity = Depends(require_roles("PATIENT", "SUPPORT_STAFF")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if (identity.role or "").upper() == "SUPPORT_STAFF":
        # Booking on behalf of a patient of this clinic
        if not payload.patient_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="patient_id is required.")
        patient_condition = Patient.id == payload.patient_id
    else:
        patient_condition = Patient.user_id == identity.user_id
    patient_stmt = select(Patient).where(
        and_(
            patient_condition,
            Patient.tenant_id == identity.tenant_id,
            Patient.deleted_at.is_(None),
        )
    )
    patient = (await db.execute(patient_stmt)).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found.")

    try:
        appointment_time = parse_client_datetime(payload.slot)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid slot timestamp.") from exc
    if appointment_time <= utc_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot book a time in the past.")

    record = await book_appointment(
        db,
        tenant_id=identity.tenant_id,
        doctor_id=payload.doctor_id,
        patient_id=patient.id,
        appointment_time=appointment_time,
        notes=payload.reason,
    )

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="appointments",
        record_id=record.id,
        action_type="INSERT",
        old_data=None,
        new_data={"doctor_id": record.doctor_id, "patient_id": record.patient_id, "appointment_time": payload.slot},
        performed_by=identity.user_id,
    )
    await db.commit()

    return {"id": record.id, "status": record.status}


@router.get("/appointments")
async def list_appointments(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Active appointments the caller may see (own for patients/doctors, the tenant's for staff/admins)."""
    stmt = _scope_to_caller(
        select(Appointment).where(Appointment.tenant_id == identity.tenant_id, Appointment.deleted_at.is_(None)),
        identity,
        await _caller_profile_id(db, identity),
    )
    if stmt is None:
        return []
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": row.id,
            "doctor_id": row.doctor_id,
            "patient_id": row.patient_id,
            "appointment_time": row.appointment_time.isoformat(),
            "status": row.status,
        }
        for row in rows
    ]


async def _appointments_with_doctor_names(db: AsyncSession, identity: CurrentIdentity, *conditions, unknown_doctor: str | None) -> list[dict]:
    """The caller's visible appointments (see _scope_to_caller) with doctor names, in one joined query."""

    stmt = (
        select(Appointment, Doctor.full_name)
        .outerjoin(
            Doctor,
            and_(Doctor.id == Appointment.doctor_id, Doctor.tenant_id == identity.tenant_id, Doctor.deleted_at.is_(None)),
        )
        .where(Appointment.tenant_id == identity.tenant_id, Appointment.deleted_at.is_(None), *conditions)
    )
    # Patients and doctors see only their own appointments; admins and support staff the tenant's
    stmt = _scope_to_caller(stmt, identity, await _caller_profile_id(db, identity))
    if stmt is None:
        return []

    rows = (await db.execute(stmt.order_by(Appointment.appointment_time.asc()))).all()
    return [
        {
            "id": row.id,
            "doctor_id": row.doctor_id,
            "patient_id": row.patient_id,
            "slot_id": row.slot_id,
            "appointment_time": row.appointment_time.isoformat(),
            "status": row.status,
            "notes": row.notes,
            "doctor_name": doctor_name or unknown_doctor,
        }
        for row, doctor_name in rows
    ]


@router.get("/appointments/all")
async def list_all_appointments(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all appointments for the current user without date filtering."""
    return await _appointments_with_doctor_names(db, identity, unknown_doctor="Unknown Doctor")


@router.get("/appointments/week")
async def list_weekly_appointments(
    from_date: date | None = None,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    start, end = _week_bounds(from_date, identity)
    return await _appointments_with_doctor_names(
        db, identity, Appointment.appointment_time >= start, Appointment.appointment_time < end, unknown_doctor=None,
    )


@router.patch("/appointments/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: str,
    payload: UpdateAppointmentStatusRequest,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Set an appointment's status (e.g. COMPLETED after a consultation).

    Doctors may change only their own appointments; admins any in the tenant. Cancelling goes
    through DELETE /appointments/{id}, which also soft-deletes the record and frees the slot.
    """
    next_status = payload.status.upper().strip()
    if next_status == "CANCELLED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use DELETE /appointments/{id} to cancel an appointment.")
    if next_status not in {"SCHEDULED", "CONFIRMED", "COMPLETED"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid appointment status.")

    row = (
        await db.execute(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.tenant_id == identity.tenant_id,
                Appointment.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    if (identity.role or "").upper() == "DOCTOR" and await _own_doctor_id(db, identity) != row.doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to change this appointment.")

    old_status = row.status
    row.status = next_status
    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="appointments",
        record_id=row.id,
        action_type="UPDATE",
        old_data={"status": old_status},
        new_data={"status": next_status},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"message": "Appointment status updated."}


@router.delete("/appointments/{appointment_id}")
async def delete_appointment(
    appointment_id: str,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = (
        await db.execute(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.tenant_id == identity.tenant_id,
                Appointment.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    role = (identity.role or "").upper()
    if role == "PATIENT":
        patient = (
            await db.execute(
                select(Patient).where(
                    Patient.user_id == identity.user_id,
                    Patient.tenant_id == identity.tenant_id,
                    Patient.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if patient is None or row.patient_id != patient.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to cancel this appointment.")
    elif role == "DOCTOR":
        doctor_id = (
            await db.execute(
                select(Doctor.id).where(
                    Doctor.user_id == identity.user_id,
                    Doctor.tenant_id == identity.tenant_id,
                    Doctor.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if doctor_id != row.doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to cancel this appointment.")

    old_status = row.status
    row.deleted_at = utc_now()
    row.deleted_by = identity.user_id
    row.status = "CANCELLED"

    # Note: With the new partial unique indexes, cancelled appointments
    # are automatically excluded from uniqueness constraints, so we can
    # keep the record (soft delete) instead of hard deleting it

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="appointments",
        record_id=row.id,
        action_type="DELETE",
        old_data={"status": old_status},
        new_data={"status": "CANCELLED"},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"message": "Appointment cancelled."}


@router.post("/appointments/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: str,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Confirm an appointment (change status to CONFIRMED)."""
    
    # Find the appointment
    stmt = select(Appointment).where(
        and_(
            Appointment.id == appointment_id,
            Appointment.tenant_id == identity.tenant_id,
            Appointment.deleted_at.is_(None),
        )
    )
    appointment = (await db.execute(stmt)).scalar_one_or_none()
    
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    
    # Only allow confirming scheduled appointments
    if appointment.status != "SCHEDULED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only scheduled appointments can be confirmed.")
    
    # Update the appointment status to CONFIRMED
    appointment.status = "CONFIRMED"
    
    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="appointments",
        record_id=appointment.id,
        action_type="UPDATE",
        old_data={"status": "SCHEDULED"},
        new_data={"status": "CONFIRMED"},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"message": "Appointment confirmed successfully."}


@router.post("/appointments/{appointment_id}/reschedule")
async def reschedule_appointment_route(
    appointment_id: str,
    payload: RescheduleAppointmentRequest,
    identity: CurrentIdentity = Depends(require_roles("PATIENT", "DOCTOR", "SUPPORT_STAFF")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Move an appointment to a different slot with the same doctor; reason, patient and status are kept.

    Patients and doctors may move only their own appointments; support staff any in the tenant.
    """

    try:
        new_time = parse_client_datetime(payload.slot)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid slot timestamp.") from exc
    if new_time <= utc_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot reschedule to a time in the past.")

    appointment = (
        await db.execute(
            select(Appointment)
            .where(
                Appointment.id == appointment_id,
                Appointment.tenant_id == identity.tenant_id,
                Appointment.deleted_at.is_(None),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    role = (identity.role or "").upper()
    if role != "SUPPORT_STAFF":
        if role == "PATIENT":
            owner = select(Patient.id).where(
                Patient.user_id == identity.user_id,
                Patient.tenant_id == identity.tenant_id,
                Patient.deleted_at.is_(None),
            )
            expected_owner = appointment.patient_id
        else:
            owner = select(Doctor.id).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
            expected_owner = appointment.doctor_id
        if (await db.execute(owner)).scalar_one_or_none() != expected_owner:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to reschedule this appointment.")

    if appointment.status not in {"SCHEDULED", "CONFIRMED"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only scheduled or confirmed appointments can be rescheduled.")

    old_time = await reschedule_appointment(db, appointment=appointment, new_time=new_time)

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="appointments",
        record_id=appointment.id,
        action_type="UPDATE",
        old_data={"appointment_time": old_time.isoformat()},
        new_data={"appointment_time": new_time.isoformat()},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"id": appointment.id, "appointment_time": new_time.isoformat(), "status": appointment.status}


@router.patch("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: str,
    payload: UpdateAppointmentRequest,
    identity: CurrentIdentity = Depends(require_roles("SUPPORT_STAFF")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update an appointment's reason on behalf of the patient (support staff). Time changes go through /reschedule."""

    appointment = (
        await db.execute(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.tenant_id == identity.tenant_id,
                Appointment.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    if appointment.status not in {"SCHEDULED", "CONFIRMED"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only scheduled or confirmed appointments can be updated.")

    old_reason = appointment.notes
    appointment.notes = payload.reason.strip()
    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="appointments",
        record_id=appointment.id,
        action_type="UPDATE",
        old_data={"notes": old_reason},
        new_data={"notes": appointment.notes},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"id": appointment.id, "reason": appointment.notes, "status": appointment.status}
