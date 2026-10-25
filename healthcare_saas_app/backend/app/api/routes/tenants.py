"""Tenant routes.

Creating tenants is a platform-operator task (SQL or a seed script), not something a clinic admin can do
through the API: a clinic admin must never be able to create or look up other clinics. A clinic admin can
change their own clinic's settings (its time zone).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...core.timeutils import is_valid_timezone
from ...models import Tenant
from ...services.audit_service import write_audit_log
from ...services.tenant_service import set_clinic_timezone

router = APIRouter(prefix="/tenants")

UNKNOWN_TIMEZONE = "Unknown time zone. Pick one from the list (for example America/Chicago)."


class UpdateTenantRequest(BaseModel):
    timezone: str = Field(min_length=1, max_length=64, description="IANA time zone, e.g. America/Chicago")


def _info(tenant: Tenant) -> dict:
    return {"id": tenant.id, "name": tenant.name, "domain": tenant.domain, "timezone": tenant.timezone}


async def _tenant(db: AsyncSession, tenant_id: str, *, for_update: bool = False) -> Tenant:
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt.with_for_update() if for_update else stmt)).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return tenant


@router.get("/current")
async def get_current_tenant(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the current user's tenant information"""
    return _info(await _tenant(db, identity.tenant_id))


@router.patch("/current")
async def update_current_tenant(
    payload: UpdateTenantRequest,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change the clinic's time zone. Future open and blocked slots keep their local hours; booked
    appointments keep their exact time. Returns the tenant info and how many slots were moved."""
    timezone = payload.timezone.strip()
    if not is_valid_timezone(timezone):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=UNKNOWN_TIMEZONE)

    tenant = await _tenant(db, identity.tenant_id, for_update=True)
    old_timezone = tenant.timezone
    slots_moved = await set_clinic_timezone(db, tenant, timezone)
    if timezone != old_timezone:
        await write_audit_log(
            db,
            tenant_id=identity.tenant_id,
            table_name="tenants",
            record_id=tenant.id,
            action_type="UPDATE",
            old_data={"timezone": old_timezone},
            new_data={"timezone": timezone, "slots_moved": slots_moved},
            performed_by=identity.user_id,
        )
    await db.commit()
    return {**_info(tenant), "slots_moved": slots_moved}


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """An admin may look up only their own tenant; any other id is reported as not found."""
    if tenant_id != identity.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return _info(await _tenant(db, identity.tenant_id))
