"""Medical record routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, require_roles
from ...core.database import get_db
from ...models import Appointment, Doctor, MedicalRecord, Patient
from ...services.audit_service import write_access_log, write_audit_log

router = APIRouter()


class CreateMedicalRecordRequest(BaseModel):
    appointment_id: str
    patient_id: Optional[str] = None
    diagnosis: str = Field(min_length=3)
    notes: str = Field(min_length=5)
    lab_results: Optional[str] = None


async def _own_doctor_id(db: AsyncSession, identity: CurrentIdentity) -> str | None:
    return (
        await db.execute(
            select(Doctor.id).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


@router.post("/medical-records", status_code=status.HTTP_201_CREATED)
async def create_medical_record(
    payload: CreateMedicalRecordRequest,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record the consultation for one of the calling doctor's own appointments.

    The record is attached to the appointment being consulted, which must be CONFIRMED (or COMPLETED,
    so re-saving after a partial failure still finds it).
    """

    doctor_id = await _own_doctor_id(db, identity)
    if doctor_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctor profile not found.")

    conditions = [
        Appointment.id == payload.appointment_id,
        Appointment.tenant_id == identity.tenant_id,
        Appointment.doctor_id == doctor_id,
        Appointment.deleted_at.is_(None),
    ]
    if payload.patient_id:
        conditions.append(Appointment.patient_id == payload.patient_id)
    appointment = (await db.execute(select(Appointment).where(and_(*conditions)))).scalar_one_or_none()
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    if appointment.status not in {"CONFIRMED", "COMPLETED"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only confirmed appointments can be consulted.")

    record = MedicalRecord(
        tenant_id=identity.tenant_id,
        appointment_id=appointment.id,
        diagnosis=payload.diagnosis.strip(),
        symptoms=payload.notes.strip(),
        lab_results=payload.lab_results.strip() if payload.lab_results else None,
    )
    db.add(record)

    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Medical record already exists for appointment.") from exc

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="medical_records",
        record_id=record.id,
        action_type="INSERT",
        old_data=None,
        new_data={"appointment_id": record.appointment_id},
        performed_by=identity.user_id,
    )
    await db.commit()

    return {"id": record.id, "message": "Medical record saved."}


@router.get("/medical-records/{appointment_id}")
async def get_medical_record_by_appointment(
    appointment_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN", "DOCTOR", "PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """A patient may read records of their own appointments, a doctor of their own; admins any in the tenant.

    Records the caller may not read are reported as not found, without confirming they exist.
    """

    stmt = (
        select(MedicalRecord)
        .join(Appointment, Appointment.id == MedicalRecord.appointment_id)
        .where(
            MedicalRecord.appointment_id == appointment_id,
            MedicalRecord.tenant_id == identity.tenant_id,
            MedicalRecord.deleted_at.is_(None),
            Appointment.tenant_id == identity.tenant_id,
        )
    )
    role = (identity.role or "").upper()
    if role == "PATIENT":
        stmt = stmt.join(Patient, Patient.id == Appointment.patient_id).where(
            Patient.user_id == identity.user_id, Patient.deleted_at.is_(None)
        )
    elif role == "DOCTOR":
        stmt = stmt.where(Appointment.doctor_id == await _own_doctor_id(db, identity))

    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical record not found.")

    if role != "PATIENT":
        await write_access_log(db, identity, table_name="medical_records", record_id=row.id)
        await db.commit()

    return {
        "id": row.id,
        "appointment_id": row.appointment_id,
        "symptoms": row.symptoms,
        "diagnosis": row.diagnosis,
        "lab_results": row.lab_results,
    }
