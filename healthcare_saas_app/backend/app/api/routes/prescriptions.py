"""Prescription CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...models import Appointment, Doctor, MedicalRecord, Patient, Prescription, Pharmacy
from ...services.audit_service import write_audit_log

router = APIRouter(prefix="/prescriptions")


class CreatePrescriptionRequest(BaseModel):
    medical_record_id: str
    pharmacy_id: str | None = None
    medication_details: str = Field(min_length=1)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_prescription(
    payload: CreatePrescriptionRequest,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    medical_record = (
        await db.execute(
            select(MedicalRecord).where(
                MedicalRecord.id == payload.medical_record_id,
                MedicalRecord.tenant_id == identity.tenant_id,
                MedicalRecord.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if medical_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical record not found.")

    if (identity.role or "").upper() == "DOCTOR":
        # Only for a record of the calling doctor's own appointment
        owns_record = (
            await db.execute(
                select(Appointment.id)
                .join(Doctor, Doctor.id == Appointment.doctor_id)
                .where(
                    Appointment.id == medical_record.appointment_id,
                    Appointment.tenant_id == identity.tenant_id,
                    Doctor.user_id == identity.user_id,
                    Doctor.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if owns_record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical record not found.")

    if payload.pharmacy_id:
        pharmacy = (
            await db.execute(
                select(Pharmacy.id).where(
                    Pharmacy.id == payload.pharmacy_id,
                    Pharmacy.tenant_id == identity.tenant_id,
                    Pharmacy.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if pharmacy is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pharmacy not found.")

    prescription = Prescription(
        tenant_id=identity.tenant_id,
        medical_record_id=payload.medical_record_id,
        pharmacy_id=payload.pharmacy_id,
        medication_details=payload.medication_details.strip(),
    )
    db.add(prescription)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prescription already exists.") from exc

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="prescriptions",
        record_id=prescription.id,
        action_type="INSERT",
        old_data=None,
        new_data={"medical_record_id": prescription.medical_record_id},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"id": prescription.id}


@router.get("/pharmacies")
async def get_pharmacies(
    identity: CurrentIdentity = Depends(require_roles("DOCTOR", "ADMIN", "PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all pharmacies for the current tenant."""
    try:
        pharmacies = (
            await db.execute(
                select(Pharmacy).where(
                    and_(
                        Pharmacy.tenant_id == identity.tenant_id,
                        Pharmacy.deleted_at.is_(None),
                    )
                )
            )
        ).scalars().all()
        
        return [
            {
                "id": str(pharmacy.id),  # Convert UUID to string
                "name": pharmacy.name,
                "address": pharmacy.address or "",
                "phone": pharmacy.phone or "",
            }
            for pharmacy in pharmacies
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch pharmacies")


@router.get("/{prescription_id}")
async def get_prescription(
    prescription_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN", "DOCTOR", "PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Prescription).where(
        and_(
            Prescription.id == prescription_id,
            Prescription.tenant_id == identity.tenant_id,
            Prescription.deleted_at.is_(None),
        )
    )
    if (identity.role or "").upper() == "PATIENT":
        # Patients may read only prescriptions from their own appointments
        stmt = (
            stmt.join(MedicalRecord, MedicalRecord.id == Prescription.medical_record_id)
            .join(Appointment, Appointment.id == MedicalRecord.appointment_id)
            .join(Patient, Patient.id == Appointment.patient_id)
            .where(Patient.user_id == identity.user_id, Patient.tenant_id == identity.tenant_id)
        )
    prescription = (await db.execute(stmt)).scalar_one_or_none()
    if prescription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found.")

    return {
        "id": prescription.id,
        "medical_record_id": prescription.medical_record_id,
        "pharmacy_id": prescription.pharmacy_id,
        "medication_details": prescription.medication_details,
    }
