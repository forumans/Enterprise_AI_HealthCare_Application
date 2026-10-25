"""Doctor patient search with clinical history (GET /patients/search).

A single patient's full history is read through GET /patient/prescriptions-full?patient_id=.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, require_roles
from ...core.database import get_db
from ...models import Appointment, MedicalRecord, Patient, Prescription
from ...services.audit_service import write_access_log
from ..search_utils import is_wildcard, search_limit

router = APIRouter(prefix="/patients")


@router.get("/search")
async def search_patients(
    q: str,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = q.strip()
    if len(query) < 2 and not is_wildcard(query):
        return []
    # "*" lists every patient; otherwise match part of the name
    name_filter = true() if is_wildcard(query) else Patient.full_name.ilike(f"%{query}%")

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
            name_filter,
        )
        .order_by(Patient.full_name.asc(), Appointment.appointment_time.desc())
        .limit(search_limit(query))
    )
    rows = (await db.execute(stmt)).all()
    # Search results include clinical history: record which patients' data this staff member saw
    for viewed_id in dict.fromkeys(patient.id for patient, *_ in rows):
        await write_access_log(db, identity, table_name="patients", record_id=viewed_id)
    if rows:
        await db.commit()
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

