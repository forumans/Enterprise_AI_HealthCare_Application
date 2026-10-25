"""Tenant routes.

Creating tenants is a platform-operator task (SQL or a seed script), not something a clinic admin can do
through the API: a clinic admin must never be able to create or look up other clinics.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...models import Tenant

router = APIRouter(prefix="/tenants")


async def _tenant_info(db: AsyncSession, tenant_id: str) -> dict:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return {"id": tenant.id, "name": tenant.name, "domain": tenant.domain}


@router.get("/current")
async def get_current_tenant(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the current user's tenant information"""
    return await _tenant_info(db, identity.tenant_id)


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """An admin may look up only their own tenant; any other id is reported as not found."""
    if tenant_id != identity.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")
    return await _tenant_info(db, identity.tenant_id)
