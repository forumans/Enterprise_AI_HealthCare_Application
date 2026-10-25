"""The few lookups that must look across every clinic (tenant) before the tenant is known.

Login and password reset find an account by email or id; new emails must be unique across clinics;
the first-admin bootstrap checks whether any admin exists. Under row-level security (migration 007)
the app's database user can't see other tenants' rows, so these go through SECURITY DEFINER
functions that return only the few columns needed. Nothing else in the app reads across tenants.

If migration 007 hasn't been applied yet, the same lookups run as plain queries (there is no RLS to
get past then), so the code can be deployed before the migration without breaking sign-in.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User

_functions_available = False


@dataclass(frozen=True)
class AccountRef:
    id: str
    tenant_id: str
    role: str
    password_hash: str


async def _have_functions(db: AsyncSession) -> bool:
    global _functions_available
    if not _functions_available:
        found = (await db.execute(text("SELECT to_regprocedure('public.app_login_lookup(text)') IS NOT NULL"))).scalar()
        _functions_available = bool(found)
    return _functions_available


def _ref(row) -> AccountRef | None:
    return AccountRef(str(row.id), str(row.tenant_id), str(row.role), row.password_hash) if row else None


async def login_lookup(db: AsyncSession, email: str) -> AccountRef | None:
    """The active, non-deleted account with this (lower-cased) email, in any tenant."""

    if await _have_functions(db):
        row = (await db.execute(text("SELECT * FROM public.app_login_lookup(:email)"), {"email": email})).first()
    else:
        row = (
            await db.execute(
                select(User.id, User.tenant_id, User.role, User.password_hash).where(
                    User.email == email, User.deleted_at.is_(None), User.is_active.is_(True)
                )
            )
        ).first()
    return _ref(row)


async def reset_lookup(db: AsyncSession, user_id: str) -> AccountRef | None:
    """The active, non-deleted account with this id, in any tenant (password reset links carry only the id)."""

    if await _have_functions(db):
        row = (await db.execute(text("SELECT * FROM public.app_reset_lookup(CAST(:user_id AS uuid))"), {"user_id": user_id})).first()
    else:
        row = (
            await db.execute(
                select(User.id, User.tenant_id, User.role, User.password_hash).where(
                    User.id == user_id, User.deleted_at.is_(None), User.is_active.is_(True)
                )
            )
        ).first()
    return _ref(row)


async def email_in_use(db: AsyncSession, email: str, tenant_id: str, exclude_user_id: str | None = None) -> bool:
    """True if `email` belongs to an active account in any tenant, or to any account (even deleted) in `tenant_id`."""

    if await _have_functions(db):
        return bool(
            (
                await db.execute(
                    text("SELECT public.app_email_in_use(:email, CAST(:tenant_id AS uuid), CAST(:exclude AS uuid))"),
                    {"email": email, "tenant_id": str(tenant_id), "exclude": exclude_user_id},
                )
            ).scalar()
        )
    stmt = select(User.id).where(User.email == email, or_(User.deleted_at.is_(None), User.tenant_id == tenant_id))
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return (await db.execute(stmt.limit(1))).scalar_one_or_none() is not None


async def any_active_admin(db: AsyncSession) -> bool:
    """True if any tenant has an active, non-deleted admin (gates the public first-admin bootstrap)."""

    if await _have_functions(db):
        return bool((await db.execute(text("SELECT public.app_any_active_admin()"))).scalar())
    stmt = select(User.id).where(User.role == "ADMIN", User.is_active.is_(True), User.deleted_at.is_(None)).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none() is not None
