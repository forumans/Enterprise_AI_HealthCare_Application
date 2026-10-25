"""Admin routes used by admin dashboard UI."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, require_roles
from ...core.database import get_db
from ...core.timeutils import clinic_day_start, clinic_today, utc_now
from ...models import Admin, Appointment, Doctor, MedicalRecord, Patient, SupportStaff, User
from ...services.account_service import ensure_can_remove, ensure_email_available, restore_account
from ...services.audit_service import write_audit_log

router = APIRouter(prefix="/admin")


def _appointment_window_starts(now: datetime, tz: ZoneInfo) -> dict[str, datetime]:
    """Return dashboard window starts: clinic-local midnights, as UTC instants."""

    today = clinic_today(tz, now)
    return {
        "today": clinic_day_start(today, tz),
        "week": clinic_day_start(today - timedelta(days=today.weekday()), tz),
        "month": clinic_day_start(today.replace(day=1), tz),
        "year": clinic_day_start(today.replace(month=1, day=1), tz),
    }


@router.get("/users")
async def admin_list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=500),
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    offset = (page - 1) * page_size
    # One query: each user with the name from whichever profile table matches their role
    profile_name = func.coalesce(Patient.full_name, Doctor.full_name, Admin.full_name, SupportStaff.full_name)
    stmt = (
        select(User, profile_name.label("full_name"))
        .outerjoin(Patient, and_(Patient.user_id == User.id, User.role == "PATIENT"))
        .outerjoin(Doctor, and_(Doctor.user_id == User.id, User.role == "DOCTOR"))
        .outerjoin(Admin, and_(Admin.user_id == User.id, User.role == "ADMIN"))
        .outerjoin(SupportStaff, and_(SupportStaff.user_id == User.id, User.role == "SUPPORT_STAFF"))
        .where(User.tenant_id == identity.tenant_id, User.deleted_at.is_(None))
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": user.id,
            "name": full_name or user.email,  # Fallback to email if there's no profile name
            "email": user.email,
            "role": user.role,
            "is_deleted": bool(user.deleted_at),
            "is_active": bool(user.is_active),
        }
        for user, full_name in rows
    ]


@router.get("/appointments")
async def admin_list_appointments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=500),
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Paged appointments, newest first, with names. Cancelled visits are included and labelled by status
    ("CANCELLED") and `is_cancelled`, so the list is a complete history."""
    offset = (page - 1) * page_size
    stmt = (
        select(Appointment, Doctor.full_name, Patient.full_name)
        .join(Doctor, and_(Doctor.id == Appointment.doctor_id, Doctor.tenant_id == identity.tenant_id))
        .join(Patient, and_(Patient.id == Appointment.patient_id, Patient.tenant_id == identity.tenant_id))
        .where(Appointment.tenant_id == identity.tenant_id)
        .order_by(Appointment.appointment_time.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": row.id,
            "date": row.appointment_time.isoformat(),
            "doctor": row.doctor_id,
            "doctor_name": doctor_name,
            "patient": row.patient_id,
            "patient_name": patient_name,
            "status": row.status,
            "is_cancelled": row.status == "CANCELLED" or row.deleted_at is not None,
        }
        for row, doctor_name, patient_name in rows
    ]


@router.get("/reports")
async def admin_reports(
    date_from: str = "",
    date_to: str = "",
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = (date_from, date_to)

    monthly_patient_count = (
        await db.execute(
            select(func.count(Patient.id)).where(Patient.tenant_id == identity.tenant_id, Patient.deleted_at.is_(None))
        )
    ).scalar_one()
    diagnosis_frequency = (
        await db.execute(
            select(func.count(MedicalRecord.id)).where(
                MedicalRecord.tenant_id == identity.tenant_id,
                MedicalRecord.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    doctor_count = (
        await db.execute(
            select(func.count(Doctor.id)).where(Doctor.tenant_id == identity.tenant_id, Doctor.deleted_at.is_(None))
        )
    ).scalar_one()
    completed_appointments = (
        await db.execute(
            select(func.count(Appointment.id)).where(
                Appointment.tenant_id == identity.tenant_id,
                Appointment.status == "COMPLETED",
                Appointment.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    utilization = 0 if doctor_count == 0 else round(float(completed_appointments) / float(doctor_count), 2)

    async def active_people(profile) -> int:
        """Profiles whose login is usable: neither the profile nor the user is deleted, and the user is active."""
        return int((
            await db.execute(
                select(func.count(profile.id))
                .join(User, User.id == profile.user_id)
                .where(
                    profile.tenant_id == identity.tenant_id,
                    profile.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                    User.is_active.is_(True),
                )
            )
        ).scalar_one() or 0)

    return {
        "doctor_count": await active_people(Doctor),
        "patient_count": await active_people(Patient),
        "monthly_patient_count": int(monthly_patient_count or 0),
        "diagnosis_frequency": int(diagnosis_frequency or 0),
        "doctor_utilization_rate": utilization,
    }


@router.get("/appointment-metrics")
async def admin_appointment_metrics(
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return aggregate appointment totals for dashboard time ranges."""

    now = utc_now()
    windows = _appointment_window_starts(now, identity.clinic_tz)

    stmt = select(
        func.count(Appointment.id).label("total_appointments_to_date"),
        func.sum(
            case((Appointment.appointment_time >= windows["year"], 1), else_=0)
        ).label("total_appointments_year_to_date"),
        func.sum(
            case((Appointment.appointment_time >= windows["month"], 1), else_=0)
        ).label("total_appointments_this_month"),
        func.sum(
            case((Appointment.appointment_time >= windows["week"], 1), else_=0)
        ).label("total_appointments_this_week"),
        func.sum(
            case((Appointment.appointment_time >= windows["today"], 1), else_=0)
        ).label("total_appointments_today"),
    ).where(
        Appointment.tenant_id == identity.tenant_id,
        Appointment.deleted_at.is_(None),
        Appointment.appointment_time <= now,
    )

    result = (await db.execute(stmt)).mappings().one()
    return {
        "total_appointments_to_date": int(result.get("total_appointments_to_date") or 0),
        "total_appointments_year_to_date": int(result.get("total_appointments_year_to_date") or 0),
        "total_appointments_this_month": int(result.get("total_appointments_this_month") or 0),
        "total_appointments_this_week": int(result.get("total_appointments_this_week") or 0),
        "total_appointments_today": int(result.get("total_appointments_today") or 0),
    }


class AdminCreateUserRequest(BaseModel):
    role: str = Field(pattern="^(PATIENT|DOCTOR|ADMIN|SUPPORT_STAFF)$")
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    phone: str = Field(default="", max_length=50)
    specialty: str = Field(default="", max_length=255)
    license_number: str = Field(default="", max_length=100)
    insurance_provider: str = Field(default="", max_length=255)
    insurance_policy_number: str = Field(default="", max_length=255)
    date_of_birth: date | None = None
    gender: str | None = None
    address_line1: str = Field(default="", max_length=255)
    address_line2: str = Field(default="", max_length=255)
    city: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=100)
    postal_code: str = Field(default="", max_length=20)
    country: str = Field(default="USA", max_length=100)


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    request: Request,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin endpoint to create new users."""
    from ...core.security import hash_password
    
    # Manually parse JSON body
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=422, detail="Invalid JSON in request body")
    
    # Validate and create model
    try:
        payload = AdminCreateUserRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail="Invalid request format. Please check your input and try again.")
    
    # Hash password
    password_hash = hash_password(payload.password)
    
    # Create user (the email must be free across tenants - login is cross-tenant)
    await ensure_email_available(db, payload.email.lower().strip(), identity.tenant_id)
    user = User(
        tenant_id=identity.tenant_id,
        email=payload.email.lower().strip(),
        password_hash=password_hash,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")
    except DBAPIError as exc:
        if payload.role == "SUPPORT_STAFF":
            # The user_role enum lacks SUPPORT_STAFF until migrations/005_add_support_staff_role.sql is applied
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Support staff accounts aren't available yet: the database needs migration 005_add_support_staff_role.sql.",
            ) from exc
        raise

    # Create role-specific record
    if payload.role == "PATIENT":
        patient = Patient(
            tenant_id=identity.tenant_id,
            user_id=user.id,
            full_name=payload.full_name,
            phone=payload.phone or None,
            insurance_provider=payload.insurance_provider or None,
            insurance_policy_number=payload.insurance_policy_number or None,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            address_line1=payload.address_line1 or None,
            address_line2=payload.address_line2 or None,
            city=payload.city or None,
            state=payload.state or None,
            postal_code=payload.postal_code or None,
            country=payload.country or None,
        )
        db.add(patient)
    elif payload.role == "DOCTOR":
        doctor = Doctor(
            tenant_id=identity.tenant_id,
            user_id=user.id,
            full_name=payload.full_name,
            specialty=payload.specialty,
            license_number=payload.license_number,
            phone=payload.phone or None,
            date_of_birth=payload.date_of_birth,
        )
        db.add(doctor)
    elif payload.role == "ADMIN":
        admin = Admin(
            tenant_id=identity.tenant_id,
            user_id=user.id,
            full_name=payload.full_name,
            phone=payload.phone,
        )
        db.add(admin)
    elif payload.role == "SUPPORT_STAFF":
        db.add(
            SupportStaff(
                tenant_id=identity.tenant_id,
                user_id=user.id,
                full_name=payload.full_name,
                phone=payload.phone or None,
            )
        )
    
    await db.commit()
    return {"id": str(user.id)}


@router.patch("/users/{user_id}/soft-delete")
async def soft_delete_user(
    user_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # First get the user to determine their role
    user = (
        await db.execute(
            select(User).where(User.id == user_id, User.tenant_id == identity.tenant_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    await ensure_can_remove(db, identity, user)

    # Based on the user's role, delete from the appropriate table
    if user.role == "PATIENT":
        # Find and soft delete the patient record
        patient = (
            await db.execute(
                select(Patient).where(Patient.user_id == user_id, Patient.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if patient:
            # First, get the user_uuid from the patient record
            user_uuid_to_update = patient.user_id
            patient_uuid = patient.id
            
            # Update the users table with is_active = FALSE and deleted_at = NOW()
            await db.execute(
                update(User)
                .where(User.id == user_uuid_to_update)
                .values(is_active=False, deleted_at=utc_now())
            )
            
            # Then update the patients table with deleted_at = NOW()
            old_data = {"deleted_at": patient.deleted_at.isoformat() if patient.deleted_at else None}
            patient.deleted_at = utc_now()
            patient.deleted_by = identity.user_id
            
            await write_audit_log(
                db,
                tenant_id=identity.tenant_id,
                table_name="patients",
                record_id=patient_uuid,
                action_type="DELETE",
                old_data=old_data,
                new_data={"deleted_at": patient.deleted_at.isoformat(), "deleted_by": identity.user_id},
                performed_by=identity.user_id,
            )
            
            await write_audit_log(
                db,
                tenant_id=identity.tenant_id,
                table_name="users",
                record_id=user_uuid_to_update,
                action_type="DELETE",
                old_data={"is_active": True, "deleted_at": None},
                new_data={"is_active": False, "deleted_at": utc_now().isoformat()},
                performed_by=identity.user_id,
            )
    elif user.role == "DOCTOR":
        # Find and soft delete the doctor record
        doctor = (
            await db.execute(
                select(Doctor).where(Doctor.user_id == user_id, Doctor.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if doctor:
            old_data = {"deleted_at": doctor.deleted_at.isoformat() if doctor.deleted_at else None}
            doctor.deleted_at = utc_now()
            doctor.deleted_by = identity.user_id
            
            await write_audit_log(
                db,
                tenant_id=identity.tenant_id,
                table_name="doctors",
                record_id=doctor.id,
                action_type="DELETE",
                old_data=old_data,
                new_data={"deleted_at": doctor.deleted_at.isoformat(), "deleted_by": identity.user_id},
                performed_by=identity.user_id,
            )
            
            # Also soft delete the user record for doctors
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(is_active=False, deleted_at=utc_now())
            )
            
            await write_audit_log(
                db,
                tenant_id=identity.tenant_id,
                table_name="users",
                record_id=user_id,
                action_type="DELETE",
                old_data={"is_active": True, "deleted_at": None},
                new_data={"is_active": False, "deleted_at": utc_now().isoformat()},
                performed_by=identity.user_id,
            )
    elif user.role in ("ADMIN", "SUPPORT_STAFF"):
        # Find and soft delete the admin / support staff record
        profile_model, table_name = (Admin, "admins") if user.role == "ADMIN" else (SupportStaff, "support_staff")
        profile = (
            await db.execute(
                select(profile_model).where(profile_model.user_id == user_id, profile_model.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if profile:
            old_data = {"deleted_at": profile.deleted_at.isoformat() if profile.deleted_at else None}
            profile.deleted_at = utc_now()
            profile.deleted_by = identity.user_id
            
            await write_audit_log(
                db,
                tenant_id=identity.tenant_id,
                table_name=table_name,
                record_id=profile.id,
                action_type="DELETE",
                old_data=old_data,
                new_data={"deleted_at": profile.deleted_at.isoformat(), "deleted_by": identity.user_id},
                performed_by=identity.user_id,
            )
        
        # Also soft delete the user record for admins / support staff
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_active=False, deleted_at=utc_now())
        )
        
        await write_audit_log(
            db,
            tenant_id=identity.tenant_id,
            table_name="users",
            record_id=user_id,
            action_type="DELETE",
            old_data={"is_active": True, "deleted_at": None},
            new_data={"is_active": False, "deleted_at": utc_now().isoformat()},
            performed_by=identity.user_id,
        )
    
    await db.commit()
    return {"message": f"{user.role} soft deleted successfully."}


@router.patch("/users/{user_id}/restore")
async def restore_user(
    user_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Undo a soft delete: reactivates the login and restores the person's profile."""
    await restore_account(db, identity, user_id)
    return {"message": "User restored."}
