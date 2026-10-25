"""FastAPI dependencies for current tenant/user context and RBAC checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Tenant, User
from .database import get_db
from .timeutils import clinic_zone


@dataclass(frozen=True)
class CurrentIdentity:
    tenant_id: str
    user_id: str
    role: str
    # The clinic's time zone (tenants.timezone): office hours, "today" and weeks are computed in it
    clinic_tz: ZoneInfo = field(default_factory=lambda: clinic_zone(None))


SESSION_ENDED = "Your session is no longer valid. Please sign in again."


async def get_current_identity(request: Request, db: AsyncSession = Depends(get_db)) -> CurrentIdentity:
    """Read identity populated by `TenantContextMiddleware`, and confirm the account is still usable.

    A token stays cryptographically valid until it expires, so the account is re-checked on every
    request: a user who was deactivated or soft-deleted (or whose role changed) after signing in is
    signed out on their next request instead of when the token expires.
    """

    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    role = getattr(request.state, "role", None)

    if not tenant_id or not user_id or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    account = (
        await db.execute(
            select(User.tenant_id, User.role, User.is_active, User.deleted_at, Tenant.timezone)
            .outerjoin(Tenant, Tenant.id == User.tenant_id)
            .where(User.id == user_id)
        )
    ).first()
    if (
        account is None
        or not account.is_active
        or account.deleted_at is not None
        or str(account.tenant_id) != str(tenant_id)
        or str(account.role).upper() != str(role).upper()
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESSION_ENDED)

    return CurrentIdentity(tenant_id=tenant_id, user_id=user_id, role=role, clinic_tz=clinic_zone(account.timezone))


def get_current_tenant(identity: CurrentIdentity = Depends(get_current_identity)) -> str:
    """Return active tenant_id for tenant-scoped queries."""

    return identity.tenant_id


def require_roles(*roles: str) -> Callable[[CurrentIdentity], CurrentIdentity]:
    """Build dependency that enforces role-based access."""

    normalized_roles = {r.upper() for r in roles}

    def _checker(identity: CurrentIdentity = Depends(get_current_identity)) -> CurrentIdentity:
        if identity.role.upper() not in normalized_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for this role.")
        return identity

    return _checker
