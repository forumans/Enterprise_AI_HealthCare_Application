"""Patients collection routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...models import Appointment, MedicalRecord, Patient, Prescription, User, Doctor
from ...services.audit_service import write_audit_log

router = APIRouter(prefix="/patients")


class CreatePatientRequest(BaseModel):
    user_id: str
    full_name: str = Field(min_length=3, max_length=255)
    phone: str | None = None
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: CreatePatientRequest,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = (
        await db.execute(
            select(User).where(
                User.id == payload.user_id,
                User.tenant_id == identity.tenant_id,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    patient = Patient(
        tenant_id=identity.tenant_id,
        user_id=payload.user_id,
        full_name=payload.full_name.strip(),
        phone=(payload.phone or "").strip() or None,
        insurance_provider=(payload.insurance_provider or "").strip() or None,
        insurance_policy_number=(payload.insurance_policy_number or "").strip() or None,
    )
    db.add(patient)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Patient profile already exists.") from exc

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="patients",
        record_id=patient.id,
        action_type="INSERT",
        old_data=None,
        new_data={"user_id": patient.user_id, "full_name": patient.full_name},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"id": patient.id}


@router.get("")
async def list_patients(
    identity: CurrentIdentity = Depends(require_roles("ADMIN", "DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(Patient).where(
        and_(
            Patient.tenant_id == identity.tenant_id,
            Patient.deleted_at.is_(None),
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": row.id, "user_id": row.user_id, "name": row.full_name, "phone": row.phone or ""} for row in rows]


@router.get("/search")
async def search_patients(
    q: str,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = q.strip()
    if len(query) < 2:
        return []

    stmt = (
        select(Patient, Appointment, MedicalRecord, Prescription)
        .join(
            Appointment,
            and_(
                Appointment.patient_id == Patient.id,
                Appointment.tenant_id == identity.tenant_id,
                Appointment.deleted_at.is_(None),
            ),
            isouter=True,
        )
        .join(
            MedicalRecord,
            and_(
                MedicalRecord.appointment_id == Appointment.id,
                MedicalRecord.tenant_id == identity.tenant_id,
                MedicalRecord.deleted_at.is_(None),
            ),
            isouter=True,
        )
        .join(
            Prescription,
            and_(
                Prescription.medical_record_id == MedicalRecord.id,
                Prescription.tenant_id == identity.tenant_id,
                Prescription.deleted_at.is_(None),
            ),
            isouter=True,
        )
        .where(
            Patient.tenant_id == identity.tenant_id,
            Patient.deleted_at.is_(None),
            Patient.full_name.ilike(f"%{query}%"),
        )
        .order_by(Patient.full_name.asc(), Appointment.appointment_time.desc())
        .limit(50)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(patient.id),
            "name": patient.full_name,
            "phone": patient.phone or "",
            "dob": patient.date_of_birth.isoformat() if patient.date_of_birth else "",
            "gender": patient.gender or "",
            "address": ", ".join(filter(None, [
                patient.address_line1,
                patient.address_line2,
                patient.city,
                patient.state,
                patient.postal_code,
                patient.country
            ])),
            "symptoms": medical_record.symptoms if medical_record else "",
            "diagnosis": medical_record.diagnosis if medical_record else "",
            "lab_results": medical_record.lab_results if medical_record else "",
            "medication": prescription.medication_details if prescription else "",
            "prescription_date": appointment.appointment_time.isoformat() if appointment else "",
        }
        for patient, appointment, medical_record, prescription in rows
    ]


@router.get("/{patient_id}/prescriptions")
async def get_all_patient_prescriptions(
    patient_id: str,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all prescriptions for a specific patient"""
    stmt = (
        select(Patient, Appointment, MedicalRecord, Prescription, Doctor)
        .join(
            Appointment,
            and_(
                Appointment.patient_id == Patient.id,
                Appointment.tenant_id == identity.tenant_id,
                Appointment.deleted_at.is_(None),
            ),
            isouter=True,
        )
        .join(
            MedicalRecord,
            and_(
                MedicalRecord.appointment_id == Appointment.id,
                MedicalRecord.tenant_id == identity.tenant_id,
                MedicalRecord.deleted_at.is_(None),
            ),
            isouter=True,
        )
        .join(
            Prescription,
            and_(
                Prescription.medical_record_id == MedicalRecord.id,
                Prescription.tenant_id == identity.tenant_id,
                Prescription.deleted_at.is_(None),
            ),
            isouter=True,
        )
        .join(
            Doctor,
            and_(
                Doctor.id == Appointment.doctor_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            ),
            isouter=True,
        )
        .where(
            Patient.tenant_id == identity.tenant_id,
            Patient.deleted_at.is_(None),
            Patient.id == patient_id,
        )
        .order_by(Appointment.appointment_time.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(patient.id),
            "name": patient.full_name,
            "symptoms": medical_record.symptoms if medical_record else "",
            "diagnosis": medical_record.diagnosis if medical_record else "",
            "lab_results": medical_record.lab_results if medical_record else "",
            "medication": prescription.medication_details if prescription else "",
            "prescription_date": appointment.appointment_time.isoformat() if appointment else "",
            "doctor_name": f"{doctor.full_name if doctor else ''} {doctor.specialty if doctor else ''}".strip() if doctor else "Unknown",
        }
        for patient, appointment, medical_record, prescription, doctor in rows
    ]
