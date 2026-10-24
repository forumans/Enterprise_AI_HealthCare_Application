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


class UpdateAppointmentStatusRequest(BaseModel):
    status: str


class RescheduleAppointmentRequest(BaseModel):
    slot: str = Field(description="ISO datetime string for the new appointment_time")


def _week_bounds(from_date: date | None) -> tuple[datetime, datetime]:
    return clinic_week_bounds(from_date or clinic_today())


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: CreateAppointmentRequest,
    identity: CurrentIdentity = Depends(require_roles("PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    patient_stmt = select(Patient).where(
        and_(
            Patient.user_id == identity.user_id,
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
    stmt = select(Appointment).where(
        Appointment.tenant_id == identity.tenant_id,
        Appointment.deleted_at.is_(None),
    )
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


@router.get("/appointments/all")
async def list_all_appointments(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all appointments for the current user without date filtering."""
    stmt = select(Appointment).where(
        Appointment.tenant_id == identity.tenant_id,
        Appointment.deleted_at.is_(None),
    )

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
        if patient is None:
            return []
        stmt = stmt.where(Appointment.patient_id == patient.id)

    rows = (await db.execute(stmt.order_by(Appointment.appointment_time.asc()))).scalars().all()
    
    # Fetch doctor names and notes for all appointments
    result = []
    for row in rows:
        doctor = (
            await db.execute(
                select(Doctor).where(
                    Doctor.id == row.doctor_id,
                    Doctor.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        
        result.append({
            "id": row.id,
            "doctor_id": row.doctor_id,
            "patient_id": row.patient_id,
            "slot_id": row.slot_id,
            "appointment_time": row.appointment_time.isoformat(),
            "status": row.status,
            "notes": row.notes,
            "doctor_name": doctor.full_name if doctor else "Unknown Doctor",
        })
    
    return result


@router.get("/appointments/week")
async def list_weekly_appointments(
    from_date: date | None = None,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    start, end = _week_bounds(from_date)
    stmt = select(Appointment).where(
        Appointment.tenant_id == identity.tenant_id,
        Appointment.appointment_time >= start,
        Appointment.appointment_time < end,
        Appointment.deleted_at.is_(None),
    )

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
        if patient is None:
            return []
        stmt = stmt.where(Appointment.patient_id == patient.id)

    rows = (await db.execute(stmt.order_by(Appointment.appointment_time.asc()))).scalars().all()
    
    # Fetch doctor names and notes for all appointments
    result = []
    for row in rows:
        doctor = (
            await db.execute(
                select(Doctor).where(
                    Doctor.id == row.doctor_id,
                    Doctor.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        
        result.append({
            "id": row.id,
            "doctor_id": row.doctor_id,
            "patient_id": row.patient_id,
            "slot_id": row.slot_id,
            "appointment_time": row.appointment_time.isoformat(),
            "status": row.status,
            "doctor_name": doctor.full_name if doctor else None,
            "notes": row.notes,
        })
    
    return result


@router.patch("/appointments/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: str,
    payload: UpdateAppointmentStatusRequest,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> dict:
    next_status = payload.status.upper().strip()
    if next_status not in {"SCHEDULED", "CONFIRMED", "CANCELLED", "COMPLETED"}:
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
    identity: CurrentIdentity = Depends(require_roles("PATIENT", "DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Move an appointment to a different slot with the same doctor; reason, patient and status are kept."""

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

    if (identity.role or "").upper() == "PATIENT":
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


