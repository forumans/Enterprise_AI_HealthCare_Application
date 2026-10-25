"""Doctor-related routes required by patient and doctor UI screens."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core import cross_tenant, rate_limit
from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...models import Admin, Appointment, Doctor, DoctorAvailability, MedicalRecord, Patient, Prescription, User
from ...core.security import hash_password
from ...core.timeutils import clinic_day_bounds, clinic_today, clinic_week_bounds, is_valid_timezone, parse_client_datetime, utc_now
from ...services.availability_service import ensure_default_slots
from ...services.account_service import ensure_email_available
from ...services.audit_service import write_audit_log
from ...services.tenant_service import resolve_registration_tenant, set_clinic_timezone

router = APIRouter()
logger = logging.getLogger(__name__)

PROFILE_FAILED = "Your profile couldn't be loaded or saved. Please try again."


def _check_slot_window(slot_time: datetime) -> None:
    """Slots can be changed only from now up to 30 days ahead (same rule for every availability endpoint)."""

    now = utc_now()
    if slot_time < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update slots earlier than now.")
    if slot_time > now + timedelta(days=30):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update slots beyond 30 days.")


async def _audit_slot(db: AsyncSession, identity: CurrentIdentity, slot: DoctorAvailability, action: str, old_status: str | None) -> None:
    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="doctor_availability",
        record_id=slot.id,
        action_type=action,
        old_data={"status": old_status} if old_status else None,
        new_data=None if action == "DELETE" else {"status": slot.status, "slot_time": slot.slot_time.isoformat()},
        performed_by=identity.user_id,
    )


ADMIN_ALREADY_SET_UP = "An administrator already exists. Ask an administrator to create your account."


class AdminRegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    # The clinic's IANA time zone (the setup page sends the browser's); omitted keeps the current one
    timezone: str | None = Field(default=None, max_length=64)


@router.get("/admin/setup-status")
async def admin_setup_status(db: AsyncSession = Depends(get_db)) -> dict:
    """Public: whether this deployment still needs its first admin (drives the first-time setup link)."""

    return {"setup_required": not await cross_tenant.any_active_admin(db)}


@router.post("/admin/register", status_code=status.HTTP_201_CREATED)
async def register_admin(
    payload: AdminRegisterRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public bootstrap endpoint: creates the very first admin of a new deployment.

    Refused as soon as any clinic has an active admin. Admins of further clinics are created by the
    platform operator, and further admins of a clinic by its admins (POST /admin/users), so this public
    endpoint can't be used to take over a running clinic or claim a newly created one.
    """
    rate_limit.hit("register-ip", rate_limit.client_ip(http_request))
    if await cross_tenant.any_active_admin(db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ADMIN_ALREADY_SET_UP)
    timezone = (payload.timezone or "").strip()
    if timezone and not is_valid_timezone(timezone):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown time zone.")
    password_hash = hash_password(payload.password)

    tenant = await resolve_registration_tenant(db, http_request)
    await ensure_email_available(db, payload.email.lower().strip(), tenant.id)
    if timezone:
        await set_clinic_timezone(db, tenant, timezone)

    # Create user first
    user = User(
        tenant_id=tenant.id,
        email=payload.email.lower().strip(),
        password_hash=password_hash,
        role="ADMIN",
        is_active=True,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.") from exc

    db.add(Admin(tenant_id=tenant.id, user_id=user.id, full_name=payload.full_name.strip()))
    await write_audit_log(
        db,
        tenant_id=tenant.id,
        table_name="users",
        record_id=user.id,
        action_type="INSERT",
        old_data=None,
        new_data={"role": "ADMIN", "via": "bootstrap"},
        performed_by=user.id,
    )
    await db.commit()
    return {"message": f"Admin registration successful for {payload.full_name}"}


class DoctorRegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    specialty: str | None = None
    license_number: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None


@router.post("/doctors/register", status_code=status.HTTP_201_CREATED)
async def register_doctor(
    payload: DoctorRegisterRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public endpoint for doctor self-registration.

    The account starts deactivated: an admin must activate it (Admin > Deactivate) before the doctor
    can sign in, so nobody can pose as a clinic doctor just by registering.
    """
    rate_limit.hit("register-ip", rate_limit.client_ip(http_request))
    password_hash = hash_password(payload.password)

    tenant = await resolve_registration_tenant(db, http_request)
    await ensure_email_available(db, payload.email.lower().strip(), tenant.id)

    user = User(
        tenant_id=tenant.id,
        email=payload.email.lower().strip(),
        password_hash=password_hash,
        role="DOCTOR",
        is_active=False,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.") from exc
    
    # Create doctor profile
    doctor = Doctor(
        tenant_id=user.tenant_id,
        user_id=user.id,
        full_name=payload.full_name.strip(),
        specialty=(payload.specialty or "").strip() or None,
        license_number=(payload.license_number or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
        date_of_birth=payload.date_of_birth,
    )
    db.add(doctor)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Doctor profile already exists.") from exc

    await write_audit_log(
        db,
        tenant_id=tenant.id,
        table_name="users",
        record_id=user.id,
        action_type="INSERT",
        old_data=None,
        new_data={"role": "DOCTOR", "is_active": False, "via": "self_registration"},
        performed_by=user.id,
    )
    await db.commit()
    return {
        "message": "Registration received. An administrator must activate your account before you can sign in."
    }


class CreateDoctorRequest(BaseModel):
    user_id: str
    full_name: str = Field(min_length=3, max_length=255)
    specialty: str | None = None
    license_number: str | None = None
    phone: str | None = None


class UpsertDoctorAvailabilityRequest(BaseModel):
    slot: str = Field(description="ISO datetime string for slot_time")
    is_available: bool = True
    block_reason: str | None = None
    doctor_id: str | None = Field(default=None, description="Required for support staff acting on behalf of a doctor")


async def _doctor_for_slot_change(db: AsyncSession, identity: CurrentIdentity, doctor_id: str | None) -> Doctor:
    """Doctor whose slots the caller may change: a doctor only their own, support staff any in the tenant."""

    role = (identity.role or "").upper()
    if role == "DOCTOR":
        condition = Doctor.user_id == identity.user_id
    elif role == "SUPPORT_STAFF":
        if not doctor_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="doctor_id is required.")
        condition = Doctor.id == doctor_id
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for this role.")

    doctor = (
        await db.execute(
            select(Doctor).where(condition, Doctor.tenant_id == identity.tenant_id, Doctor.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")
    if doctor_id and doctor.id != doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to change another doctor's availability.")
    return doctor


@router.post("/doctors", status_code=status.HTTP_201_CREATED)
async def create_doctor(
    payload: CreateDoctorRequest,
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

    doctor = Doctor(
        tenant_id=identity.tenant_id,
        user_id=payload.user_id,
        full_name=payload.full_name.strip(),
        specialty=(payload.specialty or "").strip() or None,
        license_number=(payload.license_number or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
    )
    db.add(doctor)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Doctor profile already exists.") from exc

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="doctors",
        record_id=doctor.id,
        action_type="INSERT",
        old_data=None,
        new_data={"user_id": doctor.user_id, "full_name": doctor.full_name},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"id": doctor.id}


@router.get("/doctors/me")
async def get_current_doctor(
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the current logged-in doctor's information."""
    doctor = (
        await db.execute(
            select(Doctor).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    return {
        "id": doctor.id,
        "name": doctor.full_name,
        "specialty": doctor.specialty,
        "license_number": doctor.license_number
    }


@router.get("/doctors")
async def list_doctors(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Active doctors of the caller's clinic (tenant) only."""
    stmt = (
        select(Doctor)
        .where(Doctor.tenant_id == identity.tenant_id, Doctor.deleted_at.is_(None))
        .order_by(Doctor.full_name.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": row.id, "name": row.full_name, "specialty": row.specialty, "license_number": row.license_number} for row in rows]


@router.get("/availability/{doctor_id}")
async def list_availability(
    doctor_id: str,
    date: str = Query(...),
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    try:
        day = datetime.fromisoformat(date).date()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date format.") from exc

    day_start, day_end = clinic_day_bounds(day, identity.clinic_tz)

    stmt = (
        select(DoctorAvailability)
        .where(
            and_(
                DoctorAvailability.tenant_id == identity.tenant_id,
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.slot_time >= day_start,
                DoctorAvailability.slot_time < day_end,
                DoctorAvailability.status == "AVAILABLE",
            )
        )
        .order_by(DoctorAvailability.slot_time.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [{"slot": row.slot_time.isoformat()} for row in rows]


@router.get("/doctor/availability/{doctor_id}/ndays")
async def list_availability_next_30_days(
    doctor_id: str,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    # Read-only listing: default slots are generated only by /doctor/availability/{doctor_id}/all.
    # (main.py lists this path as auth-excluded, but exclusions match exact paths and the
    # "{doctor_id}" template never matches a real URL, so this endpoint does require auth.)
    now = utc_now()
    end_date = now + timedelta(days=30)

    stmt = (
        select(DoctorAvailability.slot_time)
        .select_from(DoctorAvailability)
        .join(Doctor, Doctor.id == DoctorAvailability.doctor_id)
        .where(
            and_(
                Doctor.id == doctor_id,
                Doctor.tenant_id == identity.tenant_id,
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.status == "AVAILABLE",
                DoctorAvailability.slot_time >= now,
                DoctorAvailability.slot_time <= end_date,
                Doctor.deleted_at.is_(None),
            )
        )
        .order_by(DoctorAvailability.slot_time.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [{"slot_time": row.isoformat()} for row in rows]


@router.get("/doctor/availability/{doctor_id}/all")
async def list_all_availability(
    doctor_id: str,
    days: int = Query(default=30, description="Number of days from now to fetch"),
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all availability (both available and booked) for a doctor."""
    now = utc_now()
    end_date = now + timedelta(days=days)

    # First check if doctor exists
    doctor = (
        await db.execute(
            select(Doctor).where(
                and_(
                    Doctor.id == doctor_id,
                    Doctor.tenant_id == identity.tenant_id,
                    Doctor.deleted_at.is_(None),
                )
            )
        )
    ).scalar_one_or_none()
    
    if not doctor:
        # Doctor doesn't exist, return empty array
        return []

    # Top up default office-hour slots (8 AM–11 PM clinic local time) for the next 7 days.
    await ensure_default_slots(db, doctor, identity.clinic_tz, now=now)

    # Get all availability slots
    stmt = (
        select(DoctorAvailability)
        .where(
            and_(
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.tenant_id == identity.tenant_id,
                DoctorAvailability.slot_time >= now,
                DoctorAvailability.slot_time <= end_date,
            )
        )
        .order_by(DoctorAvailability.slot_time.asc())
    )
    availability_rows = (await db.execute(stmt)).scalars().all()

    # Get active appointments for these slots (only non-cancelled ones)
    slot_times = [row.slot_time for row in availability_rows]
    appointment_stmt = (
        select(Appointment)
        .where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_time.in_(slot_times),
                Appointment.status.notin_(["CANCELLED"]),  # Exclude cancelled appointments
                Appointment.deleted_at.is_(None),
            )
        )
    )
    appointment_rows = (await db.execute(appointment_stmt)).scalars().all()
    
    # Create a map of slot_time to appointment
    appointment_map = {apt.appointment_time: apt for apt in appointment_rows}
    
    # Build response with status information
    result = []
    for row in availability_rows:
        # Check if there's an active appointment for this slot
        if row.slot_time in appointment_map:
            result.append({
                "slot_time": row.slot_time.isoformat(), 
                "status": "BOOKED"  # Slot is booked by an active appointment
            })
        else:
            result.append({
                "slot_time": row.slot_time.isoformat(), 
                "status": row.status  # Use the availability status (AVAILABLE or BLOCKED)
            })
    
    return result


class UpsertAvailabilityRequest(BaseModel):
    slot_time: str = Field(description="ISO datetime string for slot_time")
    is_available: bool = True


@router.post("/doctor/availability/{doctor_id}")
async def upsert_availability(
    doctor_id: str,
    payload: UpsertAvailabilityRequest,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add or update availability for a doctor."""
    try:
        slot_time = parse_client_datetime(payload.slot_time)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid datetime format.") from exc

    await _doctor_for_slot_change(db, identity, doctor_id)
    _check_slot_window(slot_time)

    # Check if slot already exists
    existing = await db.execute(
        select(DoctorAvailability).where(
            and_(
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.slot_time == slot_time,
            )
        )
    )
    existing = existing.scalar_one_or_none()

    if existing:
        if existing.status == "BOOKED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify a patient-booked slot.")
        # Update existing
        old_status = existing.status
        existing.status = "AVAILABLE" if payload.is_available else "BLOCKED"
        await _audit_slot(db, identity, existing, "UPDATE", old_status)
        await db.commit()
        return {"message": "Availability updated successfully"}
    else:
        # Create new
        availability = DoctorAvailability(
            tenant_id=identity.tenant_id,
            doctor_id=doctor_id,
            slot_time=slot_time,
            status="AVAILABLE" if payload.is_available else "BLOCKED",
        )
        db.add(availability)
        await db.flush()
        await _audit_slot(db, identity, availability, "INSERT", None)
        await db.commit()
        return {"message": "Availability added successfully"}


class DeleteAvailabilityRequest(BaseModel):
    slot_time: str = Field(description="ISO datetime string for slot_time")


@router.delete("/doctor/availability/{doctor_id}")
async def delete_availability(
    doctor_id: str,
    payload: DeleteAvailabilityRequest,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete availability for a doctor."""
    try:
        slot_time = parse_client_datetime(payload.slot_time)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid datetime format.") from exc

    await _doctor_for_slot_change(db, identity, doctor_id)
    _check_slot_window(slot_time)

    # Find and delete the availability
    availability = await db.execute(
        select(DoctorAvailability).where(
            and_(
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.slot_time == slot_time,
            )
        )
    )
    availability = availability.scalar_one_or_none()

    if not availability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Availability slot not found.")
    if availability.status == "BOOKED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify a patient-booked slot.")

    await _audit_slot(db, identity, availability, "DELETE", availability.status)
    await db.delete(availability)
    await db.commit()
    return {"message": "Availability deleted successfully"}


@router.get("/doctor/appointments/today")
async def doctor_appointments_today(
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    start, end = clinic_day_bounds(clinic_today(identity.clinic_tz), identity.clinic_tz)

    doctor = (
        await db.execute(
            select(Doctor).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if doctor is None:
        return []

    stmt = (
        select(Appointment, Patient)
        .join(Patient, Patient.id == Appointment.patient_id)
        .where(
            and_(
                Appointment.tenant_id == identity.tenant_id,
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_time >= start,
                Appointment.appointment_time < end,
                Appointment.deleted_at.is_(None),
                Patient.deleted_at.is_(None),
            )
        )
        .order_by(Appointment.appointment_time.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": appointment.id,
            "doctor_id": appointment.doctor_id,
            "time": appointment.appointment_time.isoformat(),
            "patient_name": patient.full_name,
            "reason": appointment.notes or "",
            "status": appointment.status,
            "urgent": "",
        }
        for appointment, patient in rows
    ]


@router.get("/doctor/appointments/all")
async def doctor_all_appointments(
    from_date: date | None = None,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all appointments for a given week without date restrictions."""
    
    anchor = from_date or clinic_today(identity.clinic_tz)
    
    doctor = (
        await db.execute(
            select(Doctor).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    
    if doctor is None:
        return []

    week_start, week_end = clinic_week_bounds(anchor, identity.clinic_tz)
    
    stmt = (
        select(Appointment, Patient)
        .join(Patient, Patient.id == Appointment.patient_id)
        .where(
            and_(
                Appointment.tenant_id == identity.tenant_id,
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_time >= week_start,
                Appointment.appointment_time < week_end,
                Appointment.deleted_at.is_(None),
                Patient.deleted_at.is_(None),
            )
        )
        .order_by(Appointment.appointment_time.asc())
    )
    rows = (await db.execute(stmt)).all()
    
    
    result = [
        {
            "id": appointment.id,
            "doctor_id": appointment.doctor_id,
            "time": appointment.appointment_time.isoformat(),
            "patient_name": patient.full_name,
            "symptoms": appointment.notes or "",
            "status": appointment.status,
        }
        for appointment, patient in rows
    ]
    
    return result


@router.get("/doctor/appointments/upcoming")
async def doctor_appointments_upcoming(
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    doctor = (
        await db.execute(
            select(Doctor).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if doctor is None:
        return []

    stmt = (
        select(Appointment, Patient)
        .join(Patient, Patient.id == Appointment.patient_id)
        .where(
            and_(
                Appointment.tenant_id == identity.tenant_id,
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_time >= utc_now(),
                Appointment.deleted_at.is_(None),
                Patient.deleted_at.is_(None),
            )
        )
        .order_by(Appointment.appointment_time.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": appointment.id,
            "time": appointment.appointment_time.isoformat(),
            "patient_name": patient.full_name,
            "status": appointment.status,
            "urgent": "",
        }
        for appointment, patient in rows
    ]


@router.get("/doctor/appointments/{appointment_id}")
async def doctor_get_appointment_details(
    appointment_id: str,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Validate appointment_id to prevent invalid values like 'all'
    # Only validate if it's supposed to be a UUID (not for other endpoints)
    if appointment_id == 'all' or len(appointment_id) < 32:
        raise HTTPException(status_code=400, detail="Invalid appointment ID")
    
    doctor = (
        await db.execute(
            select(Doctor).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")

    stmt = (
        select(Appointment, Patient)
        .join(Patient, Patient.id == Appointment.patient_id)
        .where(
            and_(
                Appointment.tenant_id == identity.tenant_id,
                Appointment.doctor_id == doctor.id,
                Appointment.id == appointment_id,
                Appointment.deleted_at.is_(None),
                Patient.deleted_at.is_(None),
            )
        )
    )
    result = (await db.execute(stmt)).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appointment, patient = result
    
    return {
        "id": appointment.id,
        "time": appointment.appointment_time.isoformat(),
        "patient_id": patient.id,
        "patient_name": patient.full_name,
        "status": appointment.status,
        "notes": appointment.notes,
    }


@router.get("/doctor/appointments")
async def doctor_weekly_appointments(
    from_date: date | None = None,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    today = clinic_today(identity.clinic_tz)
    anchor = from_date or today
    if anchor < today:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot request appointments earlier than today.")
    if anchor > today + timedelta(days=30):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot request appointments beyond 30 days.")

    doctor = (
        await db.execute(
            select(Doctor).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if doctor is None:
        return []

    week_start, week_end = clinic_week_bounds(anchor, identity.clinic_tz)
    stmt = (
        select(Appointment, Patient)
        .join(Patient, Patient.id == Appointment.patient_id)
        .where(
            and_(
                Appointment.tenant_id == identity.tenant_id,
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_time >= week_start,
                Appointment.appointment_time < week_end,
                Appointment.deleted_at.is_(None),
                Patient.deleted_at.is_(None),
            )
        )
        .order_by(Appointment.appointment_time.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": appointment.id,
            "time": appointment.appointment_time.isoformat(),
            "patient_name": patient.full_name,
            "symptoms": appointment.notes or "",
        }
        for appointment, patient in rows
    ]


@router.post("/doctor/availability")
async def upsert_doctor_availability(
    payload: UpsertDoctorAvailabilityRequest,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # The logged-in doctor, or the doctor support staff is acting for
    doctor = await _doctor_for_slot_change(db, identity, payload.doctor_id)

    try:
        slot_time = parse_client_datetime(payload.slot)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid slot timestamp.") from exc

    _check_slot_window(slot_time)

    existing = (
        await db.execute(
            select(DoctorAvailability).where(
                DoctorAvailability.doctor_id == doctor.id,
                DoctorAvailability.slot_time == slot_time,
            )
        )
    ).scalar_one_or_none()

    if payload.is_available:
        if existing is None:
            slot = DoctorAvailability(
                tenant_id=doctor.tenant_id,
                doctor_id=doctor.id,
                slot_time=slot_time,
                status="AVAILABLE",
                block_reason=None,
            )
            db.add(slot)
            await db.flush()
            await _audit_slot(db, identity, slot, "INSERT", None)
            await db.commit()
            return {"message": "Availability added successfully"}
        elif existing.status == "BOOKED":
            # If slot exists but is booked, don't allow change
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify a patient-booked slot.")
        elif existing.status == "BLOCKED":
            # Unblock the slot
            existing.status = "AVAILABLE"
            existing.block_reason = None
            await _audit_slot(db, identity, existing, "UPDATE", "BLOCKED")
            await db.commit()
            return {"message": "Slot unblocked successfully"}
    else:
        if existing is None:
            # Create a blocked slot
            slot = DoctorAvailability(
                tenant_id=doctor.tenant_id,
                doctor_id=doctor.id,
                slot_time=slot_time,
                status="BLOCKED",
                block_reason=payload.block_reason,
            )
            db.add(slot)
            await db.flush()
            await _audit_slot(db, identity, slot, "INSERT", None)
            await db.commit()
            return {"message": "Slot blocked successfully"}
        else:
            # Mark existing slot as blocked (only if not booked)
            if existing.status == "BOOKED":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify a patient-booked slot.")
            old_status = existing.status
            existing.status = "BLOCKED"
            existing.block_reason = payload.block_reason
            await _audit_slot(db, identity, existing, "UPDATE", old_status)
            await db.commit()
            return {"message": "Slot blocked successfully"}
    return {"message": "Availability updated."}


@router.get("/doctor/profile")
async def get_doctor_profile(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db)
):
    """Get current doctor's profile information"""
    if identity.role != "DOCTOR":
        raise HTTPException(status_code=403, detail="Only doctors can access their profile")
    
    try:
        # Get doctor information (exact same as /doctors/me endpoint)
        doctor = (
            await db.execute(
                select(Doctor).where(
                    Doctor.user_id == identity.user_id,
                    Doctor.tenant_id == identity.tenant_id,
                    Doctor.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        # Return all profile fields (original Doctor model until database is updated)
        return {
            "id": doctor.id,
            "full_name": doctor.full_name,
            "email": "",  # Email is in users table, not doctors table
            "phone": doctor.phone,
            "specialty": doctor.specialty,
            "license_number": doctor.license_number,
            "date_of_birth": None,  # Not in database yet
            "gender": None,  # Not in database yet
            "address_line1": None,  # Not in database yet
            "address_line2": None,  # Not in database yet
            "city": None,  # Not in database yet
            "state": None,  # Not in database yet
            "postal_code": None,  # Not in database yet
            "country": None,  # Not in database yet
            "insurance_provider": None,  # Not in Doctor model
            "insurance_policy_id": None,  # Not in Doctor model
            "deleted_at": doctor.deleted_at.isoformat() if doctor.deleted_at else None
        }
        
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to load doctor profile.")
        raise HTTPException(status_code=500, detail=PROFILE_FAILED)


@router.put("/doctor/profile")
async def update_doctor_profile(
    payload: dict,
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db)
):
    """Update current doctor's profile information"""
    if identity.role != "DOCTOR":
        raise HTTPException(status_code=403, detail="Only doctors can update their profile")
    
    try:
        # Get doctor record (exact same as /doctors/me endpoint)
        doctor = (
            await db.execute(
                select(Doctor).where(
                    Doctor.user_id == identity.user_id,
                    Doctor.tenant_id == identity.tenant_id,
                    Doctor.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        old_data = {"full_name": doctor.full_name, "phone": doctor.phone, "specialty": doctor.specialty, "license_number": doctor.license_number}

        # Update allowed fields (original Doctor model until database is updated)
        if "fullName" in payload and payload["fullName"]:
            doctor.full_name = payload["fullName"]
        if "phone" in payload and payload["phone"]:
            doctor.phone = payload["phone"]
        if "specialty" in payload:
            doctor.specialty = payload["specialty"]
        if "licenseNumber" in payload:
            doctor.license_number = payload["licenseNumber"]
        # Note: Extended fields (DOB, gender, address) not in database yet
        # Note: Email is in users table, not doctors table
        # Note: Insurance fields are not in Doctor model

        new_data = {"full_name": doctor.full_name, "phone": doctor.phone, "specialty": doctor.specialty, "license_number": doctor.license_number}
        changed = [field for field in old_data if old_data[field] != new_data[field]]
        if changed:
            await write_audit_log(
                db,
                tenant_id=identity.tenant_id,
                table_name="doctors",
                record_id=doctor.id,
                action_type="UPDATE",
                old_data={field: old_data[field] for field in changed},
                new_data={field: new_data[field] for field in changed},
                performed_by=identity.user_id,
            )
        await db.commit()

        return {"message": "Profile updated successfully"}

    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Failed to update doctor profile.")
        raise HTTPException(status_code=500, detail=PROFILE_FAILED)
