"""Authentication routes used by Gradio UI screens.

Implements:
- POST /auth/register
- POST /auth/login
- POST /auth/forgot-password  (emails a single-use, time-limited reset link)
- POST /auth/reset-password   (sets a new password from that link)
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.security import (
    create_access_token,
    create_password_reset_token,
    hash_password,
    password_reset_token_matches,
    read_password_reset_token,
    verify_password,
)
from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...models import Patient, Tenant, User
from ...services.account_service import ensure_email_available
from ...services.audit_service import write_audit_log
from ...services.email_service import send_email

router = APIRouter(prefix="/auth")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str
    phone: str | None = None
    password: str = Field(min_length=5)
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


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


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> dict:
    tenant = await _ensure_default_tenant(db)
    await ensure_email_available(db, str(request.email).lower(), tenant.id)

    user = User(
        tenant_id=tenant.id,
        email=str(request.email).lower(),
        password_hash=hash_password(request.password),
        role="PATIENT",
        is_active=True,
    )
    db.add(user)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists in tenant.") from exc

    patient = Patient(
        tenant_id=tenant.id,
        user_id=user.id,
        full_name=request.full_name.strip(),
        phone=(request.phone or "").strip() or None,
        insurance_provider=(request.insurance_provider or "").strip() or None,
        insurance_policy_number=(request.insurance_policy_number or "").strip() or None,
        date_of_birth=request.date_of_birth,
        gender=request.gender,
        address_line1=(request.address_line1 or "").strip() or None,
        address_line2=(request.address_line2 or "").strip() or None,
        city=(request.city or "").strip() or None,
        state=(request.state or "").strip() or None,
        postal_code=(request.postal_code or "").strip() or None,
        country=(request.country or "").strip() or None,
    )
    db.add(patient)

    await write_audit_log(
        db,
        tenant_id=tenant.id,
        table_name="users",
        record_id=user.id,
        action_type="INSERT",
        old_data=None,
        new_data={"email": user.email, "role": user.role},
        performed_by=user.id,
    )
    await db.commit()

    return {"message": "Registration successful"}


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(User).where(User.email == str(request.email).lower(), User.deleted_at.is_(None), User.is_active.is_(True))
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")
    
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")

    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role)

    # Fetch patient details if role is PATIENT
    patient_name = None
    insurance_provider = None
    insurance_policy_id = None
    if user.role == "PATIENT":
        patient_stmt = select(Patient).where(
            Patient.user_id == user.id,
            Patient.tenant_id == user.tenant_id,
            Patient.deleted_at.is_(None)
        )
        patient = (await db.execute(patient_stmt)).scalar_one_or_none()
        if patient:
            patient_name = patient.full_name
            insurance_provider = patient.insurance_provider
            insurance_policy_id = patient.insurance_policy_number

    return {
        "access_token": token,
        "refresh_token": "",
        "role": user.role,
        "tenant_id": user.tenant_id,
        "user_name": patient_name,
        "insurance_provider": insurance_provider,
        "insurance_policy_id": insurance_policy_id,
    }


FORGOT_PASSWORD_REPLY = {"message": "If an account exists for that email, a password reset link has been sent."}
INVALID_RESET_LINK = "This password reset link is invalid or has expired. Please request a new one."
PASSWORD_RESET_EMAIL = """We received a request to reset your password.

Open this link within {minutes} minutes to choose a new password:
{link}

The link works once. If you didn't ask for this, you can ignore this email; your password stays the same.
"""


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Email a single-use, time-limited reset link to an active account.

    The reply is identical whether or not the email belongs to an account (and whether email could
    be sent), so it can't be used to discover which emails are registered.
    """

    email = str(request.email).strip().lower()
    user = (
        await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None), User.is_active.is_(True)))
    ).scalar_one_or_none()
    if user is not None:
        token = create_password_reset_token(user_id=user.id, password_hash=user.password_hash)
        link = f"{settings.frontend_url}/reset-password?token={token}"
        await send_email(
            user.email,
            "Reset your password",
            PASSWORD_RESET_EMAIL.format(minutes=settings.password_reset_minutes, link=link),
        )
        await write_audit_log(
            db,
            tenant_id=user.tenant_id,
            table_name="users",
            record_id=user.id,
            action_type="UPDATE",
            old_data=None,
            new_data={"password_reset_requested": True},
            performed_by=user.id,
        )
        await db.commit()
    return FORGOT_PASSWORD_REPLY


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Set a new password using the token from a reset email."""

    claims = read_password_reset_token(request.token)
    if claims is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_LINK)
    user_id, fingerprint = claims
    user = (
        await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None), User.is_active.is_(True)))
    ).scalar_one_or_none()
    if user is None or not password_reset_token_matches(fingerprint, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_LINK)

    user.password_hash = hash_password(request.new_password)
    await write_audit_log(  # never log the password itself
        db,
        tenant_id=user.tenant_id,
        table_name="users",
        record_id=user.id,
        action_type="UPDATE",
        old_data=None,
        new_data={"password_reset": True, "via": "email_link"},
        performed_by=user.id,
    )
    await db.commit()
    return {"message": "Your password has been reset. You can now sign in with your new password."}
