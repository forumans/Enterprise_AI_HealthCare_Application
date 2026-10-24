"""Support staff routes: own profile, patient search and appointment lookups on behalf of patients and doctors.

Booking, rescheduling, cancelling and slot blocking reuse the shared appointment/availability
endpoints, which accept the SUPPORT_STAFF role.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.dependencies import CurrentIdentity, require_roles
from ...core.timeutils import clinic_day_start, clinic_today
from ...models import Appointment, Doctor, Patient, SupportStaff, User
from ...services.audit_service import write_audit_log
from ..search_utils import name_phone_or_email_matches, search_limit

router = APIRouter(prefix="/support")


class UpdateSupportProfileRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    phone: str = Field(pattern=r"^\+?[0-9\-\s]{10,15}$")


async def _current_staff(db: AsyncSession, identity: CurrentIdentity) -> tuple[SupportStaff, str]:
    row = (
        await db.execute(
            select(SupportStaff, User.email)
            .join(User, User.id == SupportStaff.user_id)
            .where(
                SupportStaff.user_id == identity.user_id,
                SupportStaff.tenant_id == identity.tenant_id,
                SupportStaff.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support staff profile not found.")
    return row[0], row[1]


def _profile(staff: SupportStaff, email: str) -> dict:
    return {"id": staff.id, "full_name": staff.full_name, "phone": staff.phone or "", "email": email}


@router.get("/profile")
async def get_support_profile(
    identity: CurrentIdentity = Depends(require_roles("SUPPORT_STAFF")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The logged-in support staff member's profile."""

    return _profile(*await _current_staff(db, identity))


@router.put("/profile")
async def update_support_profile(
    payload: UpdateSupportProfileRequest,
    identity: CurrentIdentity = Depends(require_roles("SUPPORT_STAFF")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update the logged-in support staff member's name and phone (email is the login and stays as is)."""

    staff, email = await _current_staff(db, identity)
    old_data = {"full_name": staff.full_name, "phone": staff.phone}
    staff.full_name = payload.full_name.strip()
    staff.phone = payload.phone.strip()
    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="support_staff",
        record_id=staff.id,
        action_type="UPDATE",
        old_data=old_data,
        new_data={"full_name": staff.full_name, "phone": staff.phone},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"message": "Profile updated successfully", **_profile(staff, email)}


@router.get("/doctors")
async def support_search_doctors(
    q: str = "",
    identity: CurrentIdentity = Depends(require_roles("SUPPORT_STAFF")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Find doctors of this clinic by part of their name or phone number."""

    stmt = (
        select(Doctor, User.email)
        .join(User, User.id == Doctor.user_id)
        .where(Doctor.tenant_id == identity.tenant_id, Doctor.deleted_at.is_(None), name_phone_or_email_matches(q, Doctor))
        .order_by(Doctor.full_name.asc())
        .limit(search_limit(q))
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": doctor.id,
            "name": doctor.full_name,
            "phone": doctor.phone or "",
            "email": email,
            "specialty": doctor.specialty or "",
            "license_number": doctor.license_number or "",
        }
        for doctor, email in rows
    ]


@router.get("/patients")
async def support_search_patients(
    q: str = "",
    identity: CurrentIdentity = Depends(require_roles("SUPPORT_STAFF")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Find patients by part of their name or phone number (contact details only, no medical data).

    Phone matching ignores formatting, so "555-123" finds "(555) 123-4567".
    """

    stmt = (
        select(Patient, User.email)
        .join(User, User.id == Patient.user_id)
        .where(Patient.tenant_id == identity.tenant_id, Patient.deleted_at.is_(None), name_phone_or_email_matches(q, Patient))
        .order_by(Patient.full_name.asc())
        .limit(search_limit(q))
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": patient.id,
            "name": patient.full_name,
            "phone": patient.phone or "",
            "email": email,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else "",
            "gender": patient.gender or "",
            "insurance_provider": patient.insurance_provider or "",
            "city": patient.city or "",
            "state": patient.state or "",
        }
        for patient, email in rows
    ]


@router.get("/appointments")
async def support_list_appointments(
    patient_id: str | None = None,
    doctor_id: str | None = None,
    identity: CurrentIdentity = Depends(require_roles("SUPPORT_STAFF")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Active appointments from the start of today (clinic time) for one patient or one doctor."""

    if bool(patient_id) == bool(doctor_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide exactly one of patient_id or doctor_id.")

    stmt = (
        select(Appointment, Patient, Doctor)
        .join(Patient, Patient.id == Appointment.patient_id)
        .join(Doctor, Doctor.id == Appointment.doctor_id)
        .where(
            Appointment.tenant_id == identity.tenant_id,
            Appointment.deleted_at.is_(None),
            Appointment.appointment_time >= clinic_day_start(clinic_today()),
            Patient.deleted_at.is_(None),
        )
        .order_by(Appointment.appointment_time.asc())
    )
    stmt = stmt.where(Appointment.patient_id == patient_id) if patient_id else stmt.where(Appointment.doctor_id == doctor_id)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": appointment.id,
            "appointment_time": appointment.appointment_time.isoformat(),
            "status": appointment.status,
            "reason": appointment.notes or "",
            "patient_id": patient.id,
            "patient_name": patient.full_name,
            "doctor_id": doctor.id,
            "doctor_name": doctor.full_name,
        }
        for appointment, patient, doctor in rows
    ]
