"""User CRUD and soft-delete routes.

Includes `/users/{id}/soft-delete` and `/users/{id}/restore` used by UI logic.
"""

from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...core.timeutils import utc_now
from ...core.security import hash_password
from ...models import Doctor, Patient, User
from ...services.account_service import ensure_email_available, restore_account
from ...services.audit_service import write_audit_log

router = APIRouter(prefix="/users")


class CreateUserRequest(BaseModel):
    full_name: str | None = None
    email: str
    phone: str | None = None
    password: str = Field(min_length=12)
    role: str
    specialty: str | None = None
    license_number: str | None = None
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    role = str(payload.role).upper().strip()
    if role not in {"ADMIN", "DOCTOR", "PATIENT"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be ADMIN, DOCTOR, or PATIENT.")

    await ensure_email_available(db, str(payload.email).lower(), identity.tenant_id)
    user = User(
        tenant_id=identity.tenant_id,
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with email already exists.") from exc

    if role == "PATIENT":
        full_name = (payload.full_name or "").strip()
        if len(full_name) < 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Full Name is required for PATIENT role.")

        patient = Patient(
            tenant_id=identity.tenant_id,
            user_id=user.id,
            full_name=full_name,
            phone=(payload.phone or "").strip() or None,
            insurance_provider=(payload.insurance_provider or "").strip() or None,
            insurance_policy_number=(payload.insurance_policy_number or "").strip() or None,
        )
        db.add(patient)

    if role == "DOCTOR":
        full_name = (payload.full_name or "").strip()
        if len(full_name) < 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Full Name is required for DOCTOR role.")

        doctor = Doctor(
            tenant_id=identity.tenant_id,
            user_id=user.id,
            full_name=full_name,
            specialty=(payload.specialty or "").strip() or None,
            license_number=(payload.license_number or "").strip() or None,
        )
        db.add(doctor)

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="users",
        record_id=user.id,
        action_type="INSERT",
        old_data=None,
        new_data={"email": user.email, "role": user.role},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"id": user.id}


@router.get("")
async def list_users(
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(User).where(User.tenant_id == identity.tenant_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": row.id, "email": row.email, "role": row.role, "is_deleted": bool(row.deleted_at)} for row in rows]


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = (await db.execute(select(User).where(User.id == user_id, User.tenant_id == identity.tenant_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return {"id": row.id, "email": row.email, "role": row.role, "is_deleted": bool(row.deleted_at)}


@router.patch("/{user_id}/soft-delete")
async def soft_delete_user(
    user_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = (
        await db.execute(
            select(User).where(
                and_(User.id == user_id, User.tenant_id == identity.tenant_id, User.deleted_at.is_(None))
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.deleted_at = utc_now()
    user.deleted_by = identity.user_id

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="users",
        record_id=user.id,
        action_type="DELETE",
        old_data={"deleted": False},
        new_data={"deleted": True},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"message": "User soft deleted."}


@router.patch("/{user_id}/restore")
async def restore_user(
    user_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Undo a soft delete: reactivates the login and restores the person's profile."""
    await restore_account(db, identity, user_id)
    return {"message": "User restored."}
