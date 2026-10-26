"""Support staff routes: own profile, patient search and appointment lookups on behalf of patients and doctors.

Booking, rescheduling, cancelling and slot blocking reuse the shared appointment/availability
endpoints, which accept the SUPPORT_STAFF role.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.dependencies import CurrentIdentity, require_roles
from ...core.timeutils import clinic_day_start, clinic_today, utc_now
from ...models import Appointment, Doctor, DoctorAvailability, Patient, ScheduleBlock, SupportStaff, User
from ...models.schedule_block import BLOCK_REASON_CATEGORIES
from ...services.audit_service import write_audit_log
from ...services.availability_service import LIVE_APPOINTMENT_STATUSES
from ..search_utils import name_phone_or_email_matches, search_limit

# Queue items this close are marked "Urgent"
URGENT_WITHIN = timedelta(hours=24)

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
    """Find doctors of this clinic by part of their name, email or phone number.

    Deactivated doctors (e.g. awaiting an admin's approval) are still listed, so staff can manage their
    existing appointments, but are flagged with `is_active: false` and can't be booked.
    """

    stmt = (
        select(Doctor, User.email, User.is_active)
        .join(User, User.id == Doctor.user_id)
        .where(Doctor.tenant_id == identity.tenant_id, Doctor.deleted_at.is_(None), name_phone_or_email_matches(q, Doctor, User.email))
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
            "is_active": bool(is_active),
        }
        for doctor, email, is_active in rows
    ]


@router.get("/patients")
async def support_search_patients(
    q: str = "",
    identity: CurrentIdentity = Depends(require_roles("SUPPORT_STAFF")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Find patients by part of their name, email or phone number (contact details only, no medical data).

    Phone matching ignores formatting, so "555-123" finds "(555) 123-4567".
    """

    stmt = (
        select(Patient, User.email)
        .join(User, User.id == Patient.user_id)
        .where(Patient.tenant_id == identity.tenant_id, Patient.deleted_at.is_(None), name_phone_or_email_matches(q, Patient, User.email))
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
            Appointment.appointment_time >= clinic_day_start(clinic_today(identity.clinic_tz), identity.clinic_tz),
            Patient.deleted_at.is_(None),
            Doctor.deleted_at.is_(None),
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


@router.get("/reschedule-queue")
async def reschedule_queue(
    doctor_id: str | None = None,
    identity: CurrentIdentity = Depends(require_roles("SUPPORT_STAFF", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Upcoming live appointments whose hour the doctor has blocked ("Needs reschedule"), soonest first.

    Derived from the slot (BOOKED with a block_id), so an appointment leaves the queue as soon as it is
    moved, cancelled or its hour unblocked. Those within 24 hours are marked urgent.
    """

    now = utc_now()
    stmt = (
        select(Appointment, Patient, User.email, Doctor, ScheduleBlock.reason_category)
        .join(
            DoctorAvailability,
            and_(
                DoctorAvailability.doctor_id == Appointment.doctor_id,
                DoctorAvailability.slot_time == Appointment.appointment_time,
            ),
        )
        .join(Patient, Patient.id == Appointment.patient_id)
        .outerjoin(User, User.id == Patient.user_id)
        .join(Doctor, Doctor.id == Appointment.doctor_id)
        .outerjoin(ScheduleBlock, ScheduleBlock.id == DoctorAvailability.block_id)
        .where(
            Appointment.tenant_id == identity.tenant_id,
            Appointment.deleted_at.is_(None),
            Appointment.status.in_(LIVE_APPOINTMENT_STATUSES),
            Appointment.appointment_time > now,
            DoctorAvailability.status == "BOOKED",
            DoctorAvailability.block_id.is_not(None),
            Patient.deleted_at.is_(None),
            Doctor.deleted_at.is_(None),
        )
        .order_by(Appointment.appointment_time.asc())
    )
    if doctor_id:
        try:
            UUID(doctor_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid doctor_id.")
        stmt = stmt.where(Appointment.doctor_id == doctor_id)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": appointment.id,
            "appointment_time": appointment.appointment_time.isoformat(),
            "status": appointment.status,
            "urgent": appointment.appointment_time - now <= URGENT_WITHIN,
            "doctor_id": doctor.id,
            "doctor_name": doctor.full_name,
            "patient_id": patient.id,
            "patient_name": patient.full_name,
            "patient_phone": patient.phone or "",
            "patient_email": email or "",
            "reason_category": category,
            "reason_label": BLOCK_REASON_CATEGORIES.get(category, category) if category else "",
        }
        for appointment, patient, email, doctor, category in rows
    ]
