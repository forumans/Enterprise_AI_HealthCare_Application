"""Admin account management routes: find a user, then reset their password, change their login email,
or deactivate/activate their account.

The Admin "Reset Password / Email" screen searches with GET /admin/users/search and then acts on
the picked user's id. The older email-based endpoints (/admin/reset-password, /admin/change-email)
share the same logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, validator

from ...core.database import get_db
from ...core.dependencies import CurrentIdentity, require_roles
from ...core.security import hash_password
from ...models import Admin, Doctor, Patient, SupportStaff, User
from ...services.audit_service import write_audit_log
from ..search_utils import name_phone_or_email_matches, search_limit

EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
MIN_PASSWORD_LENGTH = 8


def _normalized_email(v: str) -> str:
    import re
    v = v.strip()
    if not re.match(EMAIL_PATTERN, v):
        raise ValueError('Invalid email format')
    return v.lower()


class PasswordResetRequest(BaseModel):
    email: str
    role: str
    new_password: str

    @validator('email')
    def validate_email(cls, v):
        return _normalized_email(v)


class ChangeEmailRequest(BaseModel):
    email: str
    role: str
    new_email: str

    @validator('email', 'new_email')
    def validate_emails(cls, v):
        return _normalized_email(v)


class NewPasswordRequest(BaseModel):
    new_password: str


class NewEmailRequest(BaseModel):
    new_email: str

    @validator('new_email')
    def validate_new_email(cls, v):
        return _normalized_email(v)


router = APIRouter()

# Roles whose accounts an admin can manage, as (value, label) for the Reset Password / Email screen
RESETTABLE_ROLES = [
    ("PATIENT", "Patients"),
    ("DOCTOR", "Doctors"),
    ("SUPPORT_STAFF", "Support Staff"),
    ("ADMIN", "Admin"),
]

# Profile table holding each role's name and phone
PROFILE_MODELS = {"PATIENT": Patient, "DOCTOR": Doctor, "SUPPORT_STAFF": SupportStaff, "ADMIN": Admin}


def _require_valid_role(role: str) -> None:
    valid_roles = [value for value, _ in RESETTABLE_ROLES]
    if role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )


async def _user_by_email(db: AsyncSession, identity: CurrentIdentity, email: str, role: str) -> User:
    _require_valid_role(role)
    user = (
        await db.execute(
            select(User).where(
                and_(
                    User.email == email,
                    User.role == role,
                    User.tenant_id == identity.tenant_id,
                    User.deleted_at.is_(None),
                )
            )
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found with the provided email and role combination"
        )
    return user


async def _user_by_id(db: AsyncSession, identity: CurrentIdentity, user_id: str) -> User:
    user = (
        await db.execute(
            select(User).where(User.id == user_id, User.tenant_id == identity.tenant_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


async def _set_password(db: AsyncSession, identity: CurrentIdentity, user: User, new_password: str) -> None:
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
        )
    user.password_hash = hash_password(new_password)
    await write_audit_log(  # never log the password itself
        db,
        tenant_id=identity.tenant_id,
        table_name="users",
        record_id=user.id,
        action_type="UPDATE",
        old_data=None,
        new_data={"password_reset": True},
        performed_by=identity.user_id,
    )
    await db.commit()


async def _set_email(db: AsyncSession, identity: CurrentIdentity, user: User, new_email: str) -> str:
    """Change `user`'s login email; returns the old one."""

    old_email = user.email
    if new_email == old_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"The new email ({new_email}) is the same as the current one.")

    # Login looks users up by email across all tenants, so the new email must not belong to any
    # active account anywhere, nor to any account (even deleted) here - (tenant_id, email) is unique.
    taken = (
        await db.execute(
            select(User.id).where(
                User.email == new_email,
                or_(User.deleted_at.is_(None), User.tenant_id == identity.tenant_id),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if taken:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That email is already used by another account.")

    user.email = new_email
    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="users",
        record_id=user.id,
        action_type="UPDATE",
        old_data={"email": old_email},
        new_data={"email": new_email},
        performed_by=identity.user_id,
    )
    try:
        await db.commit()
    except IntegrityError as exc:  # someone took the email between the check and the commit
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That email is already used by another account.") from exc
    return old_email


@router.get("/users/search")
async def search_users(
    role: str = Query(...),
    q: str = "",
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Find active users of one role in this clinic by part of their name, email or phone number."""

    _require_valid_role(role)
    profile = PROFILE_MODELS[role]
    stmt = (
        select(User, profile)
        .join(profile, profile.user_id == User.id)
        .where(
            User.tenant_id == identity.tenant_id,
            User.role == role,
            User.deleted_at.is_(None),
            profile.deleted_at.is_(None),
            name_phone_or_email_matches(q, profile, User.email),
        )
        .order_by(profile.full_name.asc())
        .limit(search_limit(q))
    )
    rows = (await db.execute(stmt)).all()
    results = []
    for user, person in rows:
        address = ""
        if role == "PATIENT":
            address = ", ".join(filter(None, [
                person.address_line1, person.address_line2, person.city, person.state, person.postal_code, person.country,
            ]))
        results.append({
            "user_id": user.id,
            "role": user.role,
            "name": person.full_name or user.email,
            "email": user.email,
            "phone": person.phone or "",
            "address": address,
            "date_of_birth": person.date_of_birth.isoformat() if getattr(person, "date_of_birth", None) else "",
            "specialty": getattr(person, "specialty", None) or "",
            "is_active": bool(user.is_active),
            "is_self": user.id == identity.user_id,
        })
    return results


async def _active_admin_ids(db: AsyncSession, tenant_id: str) -> list[str]:
    """Ids of this clinic's active admins, row-locked so concurrent (de)activations are serialized."""

    return list(
        (
            await db.execute(
                select(User.id)
                .where(User.tenant_id == tenant_id, User.role == "ADMIN", User.is_active.is_(True), User.deleted_at.is_(None))
                .order_by(User.id)
                .with_for_update()
            )
        ).scalars()
    )


async def _set_active(db: AsyncSession, identity: CurrentIdentity, user_id: str, active: bool) -> dict:
    # Lock the active admins first: two admins deactivating each other at once must not leave none,
    # and an admin who was just deactivated must not act with a still-valid token.
    active_admins = await _active_admin_ids(db, identity.tenant_id)
    if identity.user_id not in active_admins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your admin account is deactivated.")

    user = await _user_by_id(db, identity, user_id)
    if bool(user.is_active) == active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"This account is already {'active' if active else 'deactivated'}.")
    if not active:
        if user.id == identity.user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can't deactivate your own account.")
        if user.role == "ADMIN" and [a for a in active_admins if a != user.id] == []:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one admin must stay active.")

    user.is_active = active
    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="users",
        record_id=user.id,
        action_type="UPDATE",
        old_data={"is_active": not active},
        new_data={"is_active": active},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {
        "message": f"Account {'activated' if active else 'deactivated'} successfully",
        "user_id": user.id,
        "user_email": user.email,
        "user_role": user.role,
        "is_active": active,
    }


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deactivate an account so it can no longer log in. Admins can't deactivate themselves or the last active admin."""

    return await _set_active(db, identity, user_id, False)


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-activate a deactivated account so it can log in again."""

    return await _set_active(db, identity, user_id, True)


@router.post("/users/{user_id}/reset-password")
async def reset_password_by_id(
    user_id: str,
    request: NewPasswordRequest,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset the password of the user picked on the admin screen."""

    user = await _user_by_id(db, identity, user_id)
    await _set_password(db, identity, user, request.new_password)
    return {"message": "Password reset successfully", "user_id": user.id, "user_email": user.email, "user_role": user.role}


@router.post("/users/{user_id}/change-email")
async def change_email_by_id(
    user_id: str,
    request: NewEmailRequest,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change the login email of the user picked on the admin screen; the password is kept."""

    user = await _user_by_id(db, identity, user_id)
    old_email = await _set_email(db, identity, user, request.new_email)
    return {"message": "Email changed successfully", "user_id": user.id, "old_email": old_email, "new_email": user.email, "user_role": user.role}


@router.post("/reset-password")
async def reset_user_password(
    request: PasswordResetRequest,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset password for a user by email and role"""

    user = await _user_by_email(db, identity, request.email, request.role)
    await _set_password(db, identity, user, request.new_password)
    return {
        "message": "Password reset successfully",
        "user_email": request.email,
        "user_role": request.role,
        "reset_by": identity.user_id
    }


@router.post("/change-email")
async def change_user_email(
    request: ChangeEmailRequest,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change a user's login email, found by their current email and role."""

    _require_valid_role(request.role)
    if request.new_email == request.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The new email is the same as the current one.")
    user = await _user_by_email(db, identity, request.email, request.role)
    await _set_email(db, identity, user, request.new_email)
    return {
        "message": "Email changed successfully",
        "old_email": request.email,
        "new_email": request.new_email,
        "user_role": request.role,
    }


@router.get("/roles")
async def get_available_roles(
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
) -> list[dict]:
    """Get available user roles for password reset"""
    return [{"value": value, "label": label} for value, label in RESETTABLE_ROLES]
