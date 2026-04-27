"""Doctor-related routes required by patient and doctor UI screens."""

from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...models import Appointment, Doctor, DoctorAvailability, MedicalRecord, Patient, Prescription, User, Tenant
from ...core.security import hash_password
from ...services.audit_service import write_audit_log

router = APIRouter()


async def _ensure_default_tenant(db: AsyncSession) -> Tenant:
    """Get/create a default tenant for bootstrap flows.

    In production, tenant onboarding should be a dedicated admin flow.
    """

    existing = (await db.execute(select(Tenant).limit(1))).scalar_one_or_none()
    if existing:
        return existing

    tenant = Tenant(name="Default Tenant", domain="default.local")
    db.add(tenant)
    await db.flush()
    return tenant


class AdminRegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=5, max_length=255)


@router.post("/admin/register", status_code=status.HTTP_201_CREATED)
async def register_admin(
    payload: AdminRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public endpoint for first admin self-registration."""
    # Hash password
    password_hash = hash_password(payload.password)
    
    # Get or create default tenant
    tenant = await _ensure_default_tenant(db)
    
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
    
    await db.commit()
    return {"message": f"Admin registration successful for {payload.full_name}"}


class DoctorRegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=5, max_length=255)
    specialty: str | None = None
    license_number: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None


@router.post("/doctors/register", status_code=status.HTTP_201_CREATED)
async def register_doctor(
    payload: DoctorRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public endpoint for doctor self-registration."""
    # Hash password
    password_hash = hash_password(payload.password)
    
    # Get or create default tenant
    tenant = await _ensure_default_tenant(db)
    
    # Create user first
    user = User(
        tenant_id=tenant.id,
        email=payload.email.lower().strip(),
        password_hash=password_hash,
        role="DOCTOR",
        is_active=True,
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
    
    await db.commit()
    return {"message": f"Doctor registration successful for {payload.full_name}"}


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
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    # For now, return all non-deleted doctors across all tenants
    # In production, you may want to filter by tenant or add auth
    stmt = select(Doctor).where(Doctor.deleted_at.is_(None)).order_by(Doctor.full_name.asc())
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

    day_start = datetime.combine(day, time.min)
    day_end = datetime.combine(day, time.max)

    stmt = (
        select(DoctorAvailability)
        .where(
            and_(
                DoctorAvailability.tenant_id == identity.tenant_id,
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.slot_time >= day_start,
                DoctorAvailability.slot_time <= day_end,
                DoctorAvailability.status == "AVAILABLE",
                DoctorAvailability.deleted_at.is_(None),
            )
        )
        .order_by(DoctorAvailability.slot_time.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [{"slot": row.slot_time.isoformat()} for row in rows]


@router.get("/doctor/availability/{doctor_id}/ndays")
async def list_availability_next_30_days(
    doctor_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    now = datetime.now()  # Use local time instead of UTC
    end_date = now + timedelta(days=30)

    stmt = (
        select(DoctorAvailability.slot_time)
        .select_from(DoctorAvailability)
        .join(Doctor, Doctor.id == DoctorAvailability.doctor_id)
        .where(
            and_(
                Doctor.id == doctor_id,
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
    
    # If no availability exists, create some default slots for testing
    if not rows:
        # Get the doctor to ensure we have the correct tenant_id
        doctor = (
            await db.execute(
                select(Doctor).where(
                    and_(
                        Doctor.id == doctor_id,
                        Doctor.deleted_at.is_(None),
                    )
                )
            )
        ).scalar_one_or_none()
        
        if doctor:
            # Generate some default slots for the next 7 days and save them
            default_slots = []
            try:
                for days_ahead in range(7):
                    date = now + timedelta(days=days_ahead)
                    # Include weekends for 7-day availability
                    # Add slots from 8 AM to 4 PM (every hour)
                    for hour in range(8, 17):  # 8 AM to 4 PM (17 is exclusive)
                        slot_time = datetime.combine(date.date(), time(hour, 0, 0))
                        if slot_time > now:
                            # Create and save the availability record
                            availability = DoctorAvailability(
                                tenant_id=doctor.tenant_id,
                                doctor_id=doctor_id,
                                slot_time=slot_time,
                                status="AVAILABLE"
                            )
                            db.add(availability)
                            default_slots.append({"slot_time": slot_time.isoformat()})
                
                # Commit the default slots
                await db.commit()
            except Exception as e:
                await db.rollback()
                # Return empty list if we can't create default slots
                return []
            
            return default_slots[:20]  # Return first 20 slots
    
    return [{"slot_time": row.isoformat()} for row in rows]

            # ... (rest of the code remains the same)

@router.get("/doctor/availability/{doctor_id}/all")
async def list_all_availability(
    doctor_id: str,
    days: int = Query(default=30, description="Number of days from now to fetch"),
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all availability (both available and booked) for a doctor."""
    now = datetime.now()  # Use local time instead of UTC
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
    
    # If no availability exists, create some default slots for testing
    if not availability_rows:
        # Generate some default slots for the next 7 days and save them
        from itertools import product
        default_slots = []
        try:
            for days_ahead in range(7):
                date = now + timedelta(days=days_ahead)
                # Include weekends for 7-day availability
                # Add slots from 8 AM to 4 PM (every hour)
                for hour in range(8, 17):  # 8 AM to 4 PM (17 is exclusive)
                    slot_time = datetime.combine(date.date(), time(hour, 0, 0))
                    if slot_time > now:
                        # Create and save the availability record
                        availability = DoctorAvailability(
                            tenant_id=doctor.tenant_id,
                            doctor_id=doctor.id,
                            slot_time=slot_time,
                            status="AVAILABLE"
                        )
                        db.add(availability)
                        default_slots.append({
                            "slot_time": slot_time.isoformat(),
                            "status": "AVAILABLE"
                        })
            
            # Commit the default slots
            await db.commit()
            return default_slots[:20]  # Return first 20 slots
        except Exception as e:
            await db.rollback()
            # Return empty list if we can't create default slots
            return []
        
        return default_slots[:20]  # Return first 20 slots
    
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
        slot_time = datetime.fromisoformat(payload.slot_time)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid datetime format.") from exc

    # Verify the doctor belongs to the same tenant
    doctor = await db.execute(
        select(Doctor).where(
            and_(
                Doctor.id == doctor_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    )
    doctor = doctor.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")

    # Check if slot already exists
    existing = await db.execute(
        select(DoctorAvailability).where(
            and_(
                DoctorAvailability.doctor_id == doctor_id,
                DoctorAvailability.slot_time == slot_time,
                DoctorAvailability.deleted_at.is_(None),
            )
        )
    )
    existing = existing.scalar_one_or_none()

    if existing:
        # Update existing
        existing.status = "AVAILABLE" if payload.is_available else "BLOCKED"
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
        slot_time = datetime.fromisoformat(payload.slot_time)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid datetime format.") from exc

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

    await db.delete(availability)
    await db.commit()
    return {"message": "Availability deleted successfully"}


@router.get("/doctor/appointments/today")
async def doctor_appointments_today(
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    today = date.today()
    start = datetime.combine(today, time.min)
    end = datetime.combine(today, time.max)

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
                Appointment.appointment_time <= end,
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


@router.get("/doctor/appointments/all")
async def doctor_all_appointments(
    from_date: date | None = None,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all appointments for a given week without date restrictions."""
    print(f"DEBUG: doctor_all_appointments called - user_id: {identity.user_id}")
    
    anchor = from_date or date.today()
    
    doctor = (
        await db.execute(
            select(Doctor).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    
    print(f"DEBUG: doctor lookup result: {doctor}")
    if doctor is None:
        print("DEBUG: No doctor found, returning empty list")
        return []

    week_start = datetime.combine(anchor - timedelta(days=anchor.weekday()), time.min)
    week_end = week_start + timedelta(days=7)
    
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
    
    print(f"DEBUG: Found {len(rows)} appointments")
    
    result = [
        {
            "id": appointment.id,
            "time": appointment.appointment_time.isoformat(),
            "patient_name": patient.full_name,
            "symptoms": appointment.notes or "",
            "status": appointment.status,
        }
        for appointment, patient in rows
    ]
    
    print(f"DEBUG: Returning {len(result)} appointments")
    return result


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


@router.get("/doctor/appointments/today")
async def doctor_appointments_today(
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    today = date.today()
    start = datetime.combine(today, time.min)
    end = datetime.combine(today, time.max)

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
                Appointment.appointment_time <= end,
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


@router.get("/doctor/appointments/all")
async def doctor_all_appointments(
    from_date: date | None = None,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all appointments for a given week without date restrictions."""
    print(f"DEBUG: doctor_all_appointments called - user_id: {identity.user_id}")
    
    anchor = from_date or date.today()
    
    doctor = (
        await db.execute(
            select(Doctor).where(
                Doctor.user_id == identity.user_id,
                Doctor.tenant_id == identity.tenant_id,
                Doctor.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    
    print(f"DEBUG: doctor lookup result: {doctor}")
    if doctor is None:
        print("DEBUG: No doctor found, returning empty list")
        return []

    week_start = datetime.combine(anchor - timedelta(days=anchor.weekday()), time.min)
    week_end = week_start + timedelta(days=7)
    
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
    
    print(f"DEBUG: Found {len(rows)} appointments")
    
    result = [
        {
            "id": appointment.id,
            "time": appointment.appointment_time.isoformat(),
            "patient_name": patient.full_name,
            "symptoms": appointment.notes or "",
            "status": appointment.status,
        }
        for appointment, patient in rows
    ]
    
    print(f"DEBUG: Returning {len(result)} appointments")
    return result


@router.get("/doctor/appointments")
async def doctor_weekly_appointments(
    from_date: date | None = None,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    anchor = from_date or date.today()
    today = date.today()
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

    week_start = datetime.combine(anchor - timedelta(days=anchor.weekday()), time.min)
    week_end = week_start + timedelta(days=7)
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
    # Get the logged-in doctor
    doctor = (
        await db.execute(
            select(Doctor).where(
                and_(
                    Doctor.user_id == identity.user_id,
                    Doctor.deleted_at.is_(None),
                )
            )
        )
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found.")

    try:
        slot_time = datetime.fromisoformat(payload.slot.replace('Z', '+00:00'))
        # Normalise to UTC-naive for storage and comparison
        if slot_time.tzinfo is not None:
            slot_time = slot_time.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid slot timestamp.") from exc

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if slot_time < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update slots earlier than now.")
    if slot_time > now + timedelta(days=30):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot update slots beyond 30 days.")

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
            db.add(
                DoctorAvailability(
                    tenant_id=doctor.tenant_id,
                    doctor_id=doctor.id,
                    slot_time=slot_time,
                    status="AVAILABLE",
                    block_reason=None,
                )
            )
            await db.commit()
            return {"message": "Availability added successfully"}
        elif existing.status == "BOOKED":
            # If slot exists but is booked, don't allow change
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify a patient-booked slot.")
        elif existing.status == "BLOCKED":
            # Unblock the slot
            existing.status = "AVAILABLE"
            existing.block_reason = None
            await db.commit()
            return {"message": "Slot unblocked successfully"}
    else:
        if existing is None:
            # Create a blocked slot
            db.add(
                DoctorAvailability(
                    tenant_id=doctor.tenant_id,
                    doctor_id=doctor.id,
                    slot_time=slot_time,
                    status="BLOCKED",
                    block_reason=payload.block_reason,
                )
            )
            await db.commit()
            return {"message": "Slot blocked successfully"}
        else:
            # Mark existing slot as blocked (only if not booked)
            if existing.status == "BOOKED":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify a patient-booked slot.")
            existing.status = "BLOCKED"
            existing.block_reason = payload.block_reason
            await db.commit()
            return {"message": "Slot blocked successfully"}
    return {"message": "Availability updated."}


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
                Appointment.appointment_time >= datetime.utcnow(),
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


@router.get("/patients/search")
async def search_patients(
    q: str,
    identity: CurrentIdentity = Depends(require_roles("DOCTOR")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    # Write to debug file
    with open("debug_patients.log", "a") as f:
        f.write(f"DEBUG - search_patients called with query: '{q}'\n")
    
    query = q.strip()
    if len(query) < 2:
        with open("debug_patients.log", "a") as f:
            f.write("DEBUG - Query too short, returning empty\n")
        return []

    # Get patients matching the search
    stmt = select(Patient).where(
        Patient.tenant_id == identity.tenant_id,
        Patient.deleted_at.is_(None),
        Patient.full_name.ilike(f"%{query}%"),
    )
    patients = (await db.execute(stmt)).scalars().all()
    
    results = []
    for patient in patients:
        # Debug: Log raw patient data
        with open("debug_patients.log", "a") as f:
            f.write(f"DEBUG - Raw patient data from DB: {patient.full_name}\n")
            f.write(f"  - date_of_birth: {patient.date_of_birth} (type: {type(patient.date_of_birth)})\n")
            f.write(f"  - gender: {patient.gender} (type: {type(patient.gender)})\n")
        
        # Get the most recent appointment for this patient (optional)
        appointment_stmt = select(Appointment).where(
            and_(
                Appointment.patient_id == patient.id,
                Appointment.tenant_id == identity.tenant_id,
                Appointment.deleted_at.is_(None),
            )
        ).order_by(Appointment.appointment_time.desc()).limit(1)
        
        appointment = (await db.execute(appointment_stmt)).scalar_one_or_none()
        
        medical_record = None
        prescription = None
        
        if appointment:
            medical_record_stmt = select(MedicalRecord).where(
                and_(
                    MedicalRecord.appointment_id == appointment.id,
                    MedicalRecord.tenant_id == identity.tenant_id,
                    MedicalRecord.deleted_at.is_(None),
                )
            )
            medical_record = (await db.execute(medical_record_stmt)).scalar_one_or_none()
            
            if medical_record:
                prescription_stmt = select(Prescription).where(
                    and_(
                        Prescription.medical_record_id == medical_record.id,
                        Prescription.tenant_id == identity.tenant_id,
                        Prescription.deleted_at.is_(None),
                    )
                )
                prescription = (await db.execute(prescription_stmt)).scalar_one_or_none()
        
        # Construct address from patient fields
        address_parts = [
            patient.address_line1,
            patient.address_line2,
            patient.city,
            patient.state,
            patient.postal_code,
            patient.country
        ]
        address = ", ".join(filter(None, address_parts))
        
        # Extract DOB and Gender with explicit conversion
        dob_value = ""
        if patient.date_of_birth:
            dob_value = patient.date_of_birth.isoformat()
            with open("debug_patients.log", "a") as f:
                f.write(f"DEBUG - Converted DOB to: {dob_value}\n")
        
        gender_value = ""
        if patient.gender:
            gender_value = str(patient.gender)
            with open("debug_patients.log", "a") as f:
                f.write(f"DEBUG - Converted Gender to: {gender_value}\n")
        
        # Always return patient data, even if no appointments
        result = {
            "id": str(patient.id),  # Ensure UUID is converted to string
            "name": patient.full_name,
            "phone": patient.phone or "",
            "dob": dob_value,
            "gender": gender_value,
            "address": address,
            "symptoms": medical_record.symptoms if medical_record else "",
            "diagnosis": medical_record.diagnosis if medical_record else "",
            "lab_results": medical_record.lab_results if medical_record else "",
            "medication": prescription.medication_details if prescription else "",
            "prescription_date": appointment.appointment_time.isoformat() if appointment else "",
        }
        
        # Debug log
        with open("debug_patients.log", "a") as f:
            f.write(f"DEBUG - Backend returning patient {patient.full_name}: DOB='{result['dob']}', Gender='{result['gender']}'\n")
        
        results.append(result)
    
    return results


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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {str(e)}")


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
        
        # Save changes
        await db.commit()
        
        return {"message": "Profile updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")
