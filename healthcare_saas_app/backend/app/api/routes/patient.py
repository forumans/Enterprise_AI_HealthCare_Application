"""Patient-facing routes used by UI patient dashboard."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...core.timeutils import utc_now
from ...core.storage import read_validated_upload, safe_filename, store_document
from ...models import Appointment, Doctor, MedicalRecord, Patient, PatientDocument, Pharmacy, Prescription, User
from ...services.audit_service import write_access_log, write_audit_log

router = APIRouter(prefix="/patient")
logger = logging.getLogger(__name__)


class UpdateProfileRequest(BaseModel):
    """Name and phone only: the login email is changed by an admin, who checks it isn't taken."""

    full_name: str = Field(min_length=3, max_length=255)
    phone: str = Field(pattern=r"^\+?[0-9\-\s]{10,15}$")


PROFILE_FAILED = "Your profile couldn't be loaded or saved. Please try again."


async def _current_patient(identity: CurrentIdentity, db: AsyncSession) -> Patient:
    stmt = select(Patient).where(
        and_(
            Patient.user_id == identity.user_id,
            Patient.tenant_id == identity.tenant_id,
            Patient.deleted_at.is_(None),
        )
    )
    patient = (await db.execute(stmt)).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found.")
    return patient


@router.get("/me")
async def get_current_patient(
    identity: CurrentIdentity = Depends(require_roles("PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the current logged-in patient's information."""
    patient = await _current_patient(identity, db)
    
    # Fetch user to get email
    user = (
        await db.execute(
            select(User).where(
                User.id == patient.user_id,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    
    return {
        "id": patient.id,
        "name": patient.full_name,
        "email": user.email if user else None,
        "phone": patient.phone,
        "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        "insurance_provider": patient.insurance_provider,
        "insurance_policy_number": patient.insurance_policy_number,
        "address": f"{patient.address_line1 or ''} {patient.address_line2 or ''} {patient.city or ''} {patient.state or ''} {patient.postal_code or ''} {patient.country or ''}".strip(),
        "emergency_contact": None,  # Not in patient model
        "emergency_phone": None,  # Not in patient model
    }


@router.get("/appointments/upcoming")
async def patient_upcoming_appointments(
    identity: CurrentIdentity = Depends(require_roles("PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    patient = await _current_patient(identity, db)
    stmt = (
        select(Appointment)
        .where(
            and_(
                Appointment.tenant_id == identity.tenant_id,
                Appointment.patient_id == patient.id,
                Appointment.deleted_at.is_(None),
            )
        )
        .order_by(Appointment.appointment_time.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": row.id,
            "date": row.appointment_time.isoformat(),
            "doctor": row.doctor_id,
            "status": row.status,
        }
        for row in rows
    ]


@router.get("/medical-history")
async def patient_medical_history(
    identity: CurrentIdentity = Depends(require_roles("PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    patient = await _current_patient(identity, db)
    stmt = (
        select(MedicalRecord, Appointment)
        .join(Appointment, Appointment.id == MedicalRecord.appointment_id)
        .where(
            and_(
                MedicalRecord.tenant_id == identity.tenant_id,
                Appointment.patient_id == patient.id,
                MedicalRecord.deleted_at.is_(None),
                Appointment.deleted_at.is_(None),
            )
        )
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "date": appointment.appointment_time.isoformat(),
            "doctor": appointment.doctor_id,
            "diagnosis": record.diagnosis or "",
            "notes": record.symptoms or "",
        }
        for record, appointment in rows
    ]


@router.get("/prescriptions-full")
async def patient_prescriptions_full(
    patient_id: str | None = None,
    identity: CurrentIdentity = Depends(require_roles("PATIENT", "DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get complete patient prescription data using custom SQL query
    
    For PATIENT role: Returns their own prescriptions
    For DOCTOR role: Returns prescriptions for specified patient_id
    """
    
    if identity.role == "PATIENT":
        # Patients can only access their own data
        patient = await _current_patient(identity, db)
    elif identity.role == "DOCTOR":
        # Doctors can access any patient's data if patient_id is provided
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required for doctors")
        
        from ...models import Patient
        patient = (
            await db.execute(
                select(Patient).where(
                    and_(
                        Patient.id == patient_id,
                        Patient.tenant_id == identity.tenant_id,
                        Patient.deleted_at.is_(None),
                    )
                )
            )
        ).scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        await write_access_log(db, identity, table_name="patients", record_id=patient.id)
        await db.commit()
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    
    # Execute the complete SQL query with all JOINs
    query = text("""
        SELECT
            a.appointment_time,
            d.full_name as doctor_name,
            a.status as appointment_status,
            a.notes as appointment_note,
            mr.symptoms,
            mr.diagnosis,
            mr.lab_results,
            pr.medication_details,
            ph.name as pharmacy_name,
            a.created_at as appointment_created_at
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        LEFT JOIN medical_records mr ON mr.appointment_id = a.id AND mr.deleted_at IS NULL
        LEFT JOIN prescriptions pr ON pr.medical_record_id = mr.id AND pr.deleted_at IS NULL
        LEFT JOIN pharmacies ph ON pr.pharmacy_id = ph.id AND ph.deleted_at IS NULL
        WHERE p.id = :patient_id
        AND a.status = 'COMPLETED'
        AND a.deleted_at IS NULL
        ORDER BY a.appointment_time DESC
    """)
    
    result = await db.execute(query, {"patient_id": patient.id})
    
    prescriptions = []
    for row in result:
        prescriptions.append({
            "appointment_time": row.appointment_time.isoformat() if row.appointment_time else None,
            "doctor_name": row.doctor_name or "",
            "appointment_status": row.appointment_status,
            "appointment_note": row.appointment_note or "",
            "symptoms": row.symptoms or "",
            "diagnosis": row.diagnosis or "",
            "lab_results": row.lab_results or "",
            "medication_details": row.medication_details or "",
            "pharmacy_name": row.pharmacy_name or "",
            "appointment_created_at": row.appointment_created_at.isoformat() if row.appointment_created_at else None
        })

    return prescriptions


@router.patch("/profile")
async def update_patient_profile(
    payload: UpdateProfileRequest,
    identity: CurrentIdentity = Depends(require_roles("PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    patient = await _current_patient(identity, db)
    old_patient = {"full_name": patient.full_name, "phone": patient.phone}

    patient.full_name = payload.full_name.strip()
    patient.phone = payload.phone.strip()

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="patients",
        record_id=patient.id,
        action_type="UPDATE",
        old_data=old_patient,
        new_data={"full_name": patient.full_name, "phone": patient.phone},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"message": "Profile updated"}


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_patient_document(
    file: UploadFile = File(...),
    identity: CurrentIdentity = Depends(require_roles("PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    patient = await _current_patient(identity, db)

    content = await read_validated_upload(file)
    timestamp = utc_now().strftime("%Y%m%d%H%M%S")
    s3_key = f"documents/{identity.tenant_id}/{patient.id}/{timestamp}_{identity.user_id}_{safe_filename(file.filename)}"
    store_document(content, s3_key, file.content_type)

    record = PatientDocument(
        tenant_id=identity.tenant_id,
        patient_id=patient.id,
        document_name=safe_filename(file.filename),
        document_type=file.content_type,
        file_path=s3_key,
    )
    db.add(record)
    await db.flush()

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="patient_documents",
        record_id=record.id,
        action_type="INSERT",
        old_data=None,
        new_data={"document_name": record.document_name, "file_path": record.file_path},
        performed_by=identity.user_id,
    )
    await db.commit()

    return {"message": "Document uploaded"}


PATIENT_PROFILE_FIELDS = (
    "full_name", "phone", "date_of_birth", "gender", "address_line1", "address_line2", "city", "state",
    "postal_code", "country", "insurance_provider", "insurance_policy_number",
)


def _json_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


@router.get("/patient/profile")
async def get_patient_profile(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db)
):
    """Get current patient's profile information"""
    if identity.role != "PATIENT":
        raise HTTPException(status_code=403, detail="Only patients can access their profile")
    
    try:
        # Get patient information (same as /patients/me endpoint)
        patient = (
            await db.execute(
                select(Patient).where(
                    and_(
                        Patient.user_id == identity.user_id,
                        Patient.tenant_id == identity.tenant_id,
                        Patient.deleted_at.is_(None),
                    )
                )
            )
        ).scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Return all profile fields from the Patient model
        return {
            "id": patient.id,
            "full_name": patient.full_name,
            "email": "",  # Email is in users table, not patients table
            "phone": patient.phone,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "gender": patient.gender,
            "address_line1": patient.address_line1,
            "address_line2": patient.address_line2,
            "city": patient.city,
            "state": patient.state,
            "postal_code": patient.postal_code,
            "country": patient.country,
            "insurance_provider": patient.insurance_provider,
            "insurance_policy_number": patient.insurance_policy_number,
            "deleted_at": patient.deleted_at.isoformat() if patient.deleted_at else None
        }
        
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to load patient profile.")
        raise HTTPException(status_code=500, detail=PROFILE_FAILED)


@router.put("/patient/profile")
async def update_patient_profile(
    payload: dict,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db)
):
    """Update current patient's profile information"""
    if identity.role != "PATIENT":
        raise HTTPException(status_code=403, detail="Only patients can update their profile")
    
    try:
        # Get patient record (same as /patients/me endpoint)
        patient = (
            await db.execute(
                select(Patient).where(
                    and_(
                        Patient.user_id == identity.user_id,
                        Patient.tenant_id == identity.tenant_id,
                        Patient.deleted_at.is_(None),
                    )
                )
            )
        ).scalar_one_or_none()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        old_data = {field: _json_value(getattr(patient, field)) for field in PATIENT_PROFILE_FIELDS}

        # Update allowed fields (from the Patient model)
        if "fullName" in payload and payload["fullName"]:
            patient.full_name = payload["fullName"]
        if "phone" in payload and payload["phone"]:
            patient.phone = payload["phone"]
        if "dateOfBirth" in payload and payload["dateOfBirth"]:
            patient.date_of_birth = datetime.fromisoformat(payload["dateOfBirth"]).date()
        if "gender" in payload:
            patient.gender = payload["gender"]
        if "addressLine1" in payload:
            patient.address_line1 = payload["addressLine1"]
        if "addressLine2" in payload:
            patient.address_line2 = payload["addressLine2"]
        if "city" in payload:
            patient.city = payload["city"]
        if "state" in payload:
            patient.state = payload["state"]
        if "postalCode" in payload:
            patient.postal_code = payload["postalCode"]
        if "country" in payload:
            patient.country = payload["country"]
        if "insuranceProvider" in payload:
            patient.insurance_provider = payload["insuranceProvider"]
        if "insurancePolicyNumber" in payload:
            patient.insurance_policy_number = payload["insurancePolicyNumber"]
        # Note: Email is in users table, not patients table

        new_data = {field: _json_value(getattr(patient, field)) for field in old_data}
        changed = {field for field in old_data if old_data[field] != new_data[field]}
        if changed:
            await write_audit_log(
                db,
                tenant_id=identity.tenant_id,
                table_name="patients",
                record_id=patient.id,
                action_type="UPDATE",
                old_data={field: old_data[field] for field in changed},
                new_data={field: new_data[field] for field in changed},
                performed_by=identity.user_id,
            )
        await db.commit()

        return {"message": "Profile updated successfully"}

    except HTTPException:
        raise
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=422, detail="Invalid request format. Please check your input and try again.")
    except Exception:
        await db.rollback()
        logger.exception("Failed to update patient profile.")
        raise HTTPException(status_code=500, detail=PROFILE_FAILED)
