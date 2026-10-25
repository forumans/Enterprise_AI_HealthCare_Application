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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core import cross_tenant, rate_limit
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
from ...core.database import get_db, set_db_tenant
from ...core.timeutils import clinic_zone
from ...models import Patient, Tenant, User
from ...services.account_service import PROFILE_MODELS, ensure_email_available
from ...services.audit_service import write_audit_log
from ...services.email_service import send_email
from ...services.tenant_service import resolve_registration_tenant
from ..validators import valid_birth_date, valid_email, valid_gender, valid_phone

router = APIRouter(prefix="/auth")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str
    phone: str | None = None
    password: str = Field(min_length=8, max_length=255)
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

    # Same rules as the registration form: the browser checks are a convenience only
    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str) -> str:
        return valid_email(value)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        return valid_phone(value)

    @field_validator("gender")
    @classmethod
    def _check_gender(cls, value: str | None) -> str | None:
        return valid_gender(value)

    @field_validator("date_of_birth")
    @classmethod
    def _check_date_of_birth(cls, value: date | None) -> date | None:
        return valid_birth_date(value)


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=255)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, http_request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    await rate_limit.hit(db, "register-ip", rate_limit.client_ip(http_request))
    tenant = await resolve_registration_tenant(db, http_request)
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
async def login(request: LoginRequest, http_request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    email = str(request.email).strip().lower()
    ip = rate_limit.client_ip(http_request)
    # Only failed attempts count, so a user who signs in correctly is never throttled
    await rate_limit.check(db, "login-email", email)
    await rate_limit.check(db, "login-ip", ip)

    # Login isn't tenant-qualified, so the account is found through the narrow cross-tenant lookup
    user = await cross_tenant.login_lookup(db, email)

    if not user or not verify_password(request.password, user.password_hash):
        await rate_limit.record(db, "login-email", email)
        await rate_limit.record(db, "login-ip", ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")
    await rate_limit.clear(db, "login-email", email)
    await set_db_tenant(db, user.tenant_id, user.id)

    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
    clinic_timezone = (await db.execute(select(Tenant.timezone).where(Tenant.id == user.tenant_id))).scalar_one_or_none()

    # Display name for every role; patients also get their insurance details
    user_name = None
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
            user_name = patient.full_name
            insurance_provider = patient.insurance_provider
            insurance_policy_id = patient.insurance_policy_number
    elif user.role in PROFILE_MODELS:
        # Other roles get their profile name too (shown e.g. on the admin dashboard)
        profile = PROFILE_MODELS[user.role]
        user_name = (
            await db.execute(
                select(profile.full_name).where(
                    profile.user_id == user.id, profile.tenant_id == user.tenant_id, profile.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()

    return {
        "access_token": token,
        "refresh_token": "",
        "role": user.role,
        "tenant_id": user.tenant_id,
        "user_name": user_name,
        "insurance_provider": insurance_provider,
        "insurance_policy_id": insurance_policy_id,
        # The browser shows every time in the clinic's zone, not the viewer's
        "clinic_timezone": clinic_zone(clinic_timezone).key,
    }


FORGOT_PASSWORD_REPLY = {"message": "If an account exists for that email, a password reset link has been sent."}
INVALID_RESET_LINK = "This password reset link is invalid or has expired. Please request a new one."
PASSWORD_RESET_EMAIL = """We received a request to reset your password.

Open this link within {minutes} minutes to choose a new password:
{link}

The link works once. If you didn't ask for this, you can ignore this email; your password stays the same.
"""


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, http_request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Email a single-use, time-limited reset link to an active account.

    The reply is identical whether or not the email belongs to an account (and whether email could
    be sent), so it can't be used to discover which emails are registered.
    """

    email = str(request.email).strip().lower()
    await rate_limit.hit(db, "reset-ip", rate_limit.client_ip(http_request))
    await rate_limit.hit(db, "reset-email", email)
    user = await cross_tenant.login_lookup(db, email)
    if user is not None:
        await set_db_tenant(db, user.tenant_id, user.id)
        token = create_password_reset_token(user_id=user.id, password_hash=user.password_hash)
        link = f"{settings.frontend_url}/reset-password?token={token}"
        await send_email(
            email,
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
async def reset_password(request: ResetPasswordRequest, http_request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Set a new password using the token from a reset email."""
    await rate_limit.hit(db, "reset-ip", rate_limit.client_ip(http_request))

    claims = read_password_reset_token(request.token)
    if claims is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_LINK)
    user_id, fingerprint = claims
    account = await cross_tenant.reset_lookup(db, user_id)
    if account is None or not password_reset_token_matches(fingerprint, account.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_LINK)
    await set_db_tenant(db, account.tenant_id, account.id)
    user = (await db.execute(select(User).where(User.id == account.id))).scalar_one()

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
