"""Patient-facing routes used by UI patient dashboard."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...models import Appointment, Doctor, MedicalRecord, Patient, PatientDocument, Pharmacy, Prescription, User
from ...services.audit_service import write_audit_log

router = APIRouter(prefix="/patient")


class UpdateProfileRequest(BaseModel):
    full_name: str
    email: str
    phone: str


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


@router.get("/prescriptions")
async def patient_prescriptions(
    identity: CurrentIdentity = Depends(require_roles("PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    patient = await _current_patient(identity, db)
    
    # Simplified query to debug the issue
    stmt = (
        select(Appointment)
        .where(
            and_(
                Appointment.tenant_id == identity.tenant_id,
                Appointment.patient_id == patient.id,
                Appointment.status == "COMPLETED",
                Appointment.deleted_at.is_(None)
            )
        )
        .order_by(Appointment.appointment_time.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    
    return [
        {
            "appointment_time": appointment.appointment_time.isoformat() if appointment.appointment_time else None,
            "patient_name": "Debug Patient",
            "doctor_name": "Debug Doctor",
            "appointment_status": appointment.status,
            "appointment_note": appointment.notes,
            "symptoms": "Debug symptoms",
            "diagnosis": "Debug diagnosis",
            "lab_results": "Debug lab results",
            "medication_details": "Debug medication",
            "pharmacy_name": "Debug pharmacy",
            "appointment_created_at": appointment.created_at.isoformat() if appointment.created_at else None,
            "status": "ACTIVE"
        }
        for appointment in rows
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
    print(f"DEBUG: prescriptions-full called - role: {identity.role}, patient_id: {patient_id}")
    
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
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    print(f"DEBUG: Found patient: {patient.id} - {patient.full_name}")
    
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
    print(f"DEBUG: SQL query returned {result.rowcount} rows")
    
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
    
    if prescriptions:
        print(f"DEBUG: First prescription doctor_name: '{prescriptions[0]['doctor_name']}'")
        print(f"DEBUG: First prescription data: {prescriptions[0]}")
    
    return prescriptions


@router.patch("/profile")
async def update_patient_profile(
    payload: UpdateProfileRequest,
    identity: CurrentIdentity = Depends(require_roles("PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    patient = await _current_patient(identity, db)
    user = (await db.execute(select(User).where(User.id == identity.user_id, User.deleted_at.is_(None)))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    old_patient = {"full_name": patient.full_name, "phone": patient.phone}
    old_user = {"email": user.email}

    patient.full_name = payload.full_name.strip()
    patient.phone = payload.phone.strip()
    user.email = str(payload.email).lower().strip()

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
    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="users",
        record_id=user.id,
        action_type="UPDATE",
        old_data=old_user,
        new_data={"email": user.email},
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
    uploads_dir = Path("backend/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = (file.filename or "document.bin").replace("/", "_").replace("\\", "_")
    destination = uploads_dir / f"{timestamp}_{identity.user_id}_{safe_name}"

    content = await file.read()
    destination.write_bytes(content)

    record = PatientDocument(
        tenant_id=identity.tenant_id,
        patient_id=patient.id,
        document_name=file.filename,
        document_type=file.content_type,
        file_path=str(destination),
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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {str(e)}")


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
        
        # Save changes
        await db.commit()
        
        return {"message": "Profile updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")
