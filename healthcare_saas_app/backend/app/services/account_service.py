"""Account lifecycle operations shared by the admin and users routes."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import CurrentIdentity
from ..models import Admin, Doctor, Patient, SupportStaff, User
from .audit_service import write_audit_log

# Profile table holding each role's details; soft delete marks both the user and this row.
PROFILE_MODELS = {"PATIENT": Patient, "DOCTOR": Doctor, "SUPPORT_STAFF": SupportStaff, "ADMIN": Admin}


EMAIL_TAKEN = "That email is already used by another account."


async def ensure_email_available(db: AsyncSession, email: str, tenant_id: str, *, exclude_user_id: str | None = None) -> None:
    """Raise 409 if `email` can't be given to a (new or existing) account in `tenant_id`.

    Login looks users up by email across all tenants, so an email must not belong to any active
    account anywhere - nor to any account, even a deleted one, in the same tenant, where
    (tenant_id, email) is unique.
    """

    stmt = select(User.id).where(
        User.email == email,
        or_(User.deleted_at.is_(None), User.tenant_id == tenant_id),
    )
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    if (await db.execute(stmt.limit(1))).scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=EMAIL_TAKEN)


async def restore_account(db: AsyncSession, identity: CurrentIdentity, user_id: str) -> User:
    """Undo a soft delete: the login can be used again and the person shows up in lists and searches.

    Restores the user row (deleted_at cleared, is_active back on) and their role profile. Refused if
    another active account - in any tenant, since login looks emails up across tenants - now has
    the same email.
    """

    user = (
        await db.execute(select(User).where(User.id == user_id, User.tenant_id == identity.tenant_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This account is not deleted.")

    try:
        await ensure_email_available(db, user.email, identity.tenant_id, exclude_user_id=user.id)
    except HTTPException as exc:
        exc.detail = "Another active account uses this email. Change one of the emails before restoring."
        raise

    user.deleted_at = None
    user.deleted_by = None
    user.is_active = True

    profile_model = PROFILE_MODELS.get(user.role)
    if profile_model is not None:
        profile = (await db.execute(select(profile_model).where(profile_model.user_id == user.id))).scalar_one_or_none()
        if profile is not None:
            profile.deleted_at = None
            profile.deleted_by = None

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="users",
        record_id=user.id,
        action_type="UPDATE",
        old_data={"deleted": True, "is_active": False},
        new_data={"deleted": False, "is_active": True},
        performed_by=identity.user_id,
    )
    await db.commit()
    return user
