"""Which clinic (tenant) a public self-registration belongs to.

Each clinic is reached on its own web address, stored in `tenants.domain` (for example
`sunrise.example-health.com`). Registration requests are matched to a clinic by the host the browser
was on (the `Origin` header), so a patient who signs up on a clinic's site joins that clinic.

- A deployment with a single clinic needs no configuration: every registration joins it.
- A brand-new deployment with no clinic yet gets a default one, so the first admin can be created.
- With several clinics and no matching address, registration is refused rather than guessed.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import set_db_tenant
from ..models import Tenant

NO_CLINIC_FOR_ADDRESS = "Registration isn't available at this address. Please use your clinic's website or contact the clinic."


def request_host(request: Request) -> str:
    """Host name the browser was on: Origin (sent by browsers on POST), else X-Forwarded-Host, else Host."""

    origin = request.headers.get("origin", "")
    if origin:
        host = urlsplit(origin).hostname or ""
    else:
        host = request.headers.get("x-forwarded-host", "") or request.headers.get("host", "")
        host = host.split(",", 1)[0].strip().rsplit(":", 1)[0] if host and not host.startswith("[") else host
    return host.strip().lower().rstrip(".")


async def resolve_registration_tenant(db: AsyncSession, request: Request) -> Tenant:
    """The clinic a self-registration joins (see module docstring). Also scopes the DB session to it."""

    host = request_host(request)
    tenant = None
    if host:
        tenant = (await db.execute(select(Tenant).where(func.lower(Tenant.domain) == host))).scalar_one_or_none()
    if tenant is None:
        tenants = (await db.execute(select(Tenant).order_by(Tenant.created_at).limit(2))).scalars().all()
        if not tenants:
            tenant = Tenant(name="Default Tenant", domain="default.local")
            db.add(tenant)
            await db.flush()
        elif len(tenants) == 1:
            tenant = tenants[0]
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NO_CLINIC_FOR_ADDRESS)
    await set_db_tenant(db, tenant.id)
    return tenant
