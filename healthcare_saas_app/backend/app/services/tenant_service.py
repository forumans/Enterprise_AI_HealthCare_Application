"""Which clinic (tenant) a public self-registration belongs to.

Each clinic is reached on its own web address, stored in `tenants.domain` (for example
`sunrise.example-health.com`). Registration requests are matched to a clinic by the host the browser
was on (the `Origin` header), so a patient who signs up on a clinic's site joins that clinic.

- A deployment with a single clinic needs no configuration: every registration joins it.
- A brand-new deployment with no clinic yet gets a default one, so the first admin can be created.
- With several clinics and no matching address, registration is refused rather than guessed.

It also changes a clinic's time zone (`set_clinic_timezone`).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import set_db_tenant
from ..core.timeutils import DEFAULT_CLINIC_TIMEZONE, clinic_zone
from ..models import Tenant
from .availability_service import keep_slot_hours_in_new_zone

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
            tenant = Tenant(name="Default Tenant", domain="default.local", timezone=DEFAULT_CLINIC_TIMEZONE)
            db.add(tenant)
            await db.flush()
        elif len(tenants) == 1:
            tenant = tenants[0]
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=NO_CLINIC_FOR_ADDRESS)
    await set_db_tenant(db, tenant.id)
    return tenant


async def set_clinic_timezone(db: AsyncSession, tenant: Tenant, timezone: str) -> int:
    """Switch the clinic to IANA zone `timezone` (already validated) and move its future open slots so
    they keep their local hours. Booked appointments keep their exact time. The caller commits.

    Returns the number of slots moved.
    """

    if timezone == tenant.timezone:
        return 0
    old_tz = clinic_zone(tenant.timezone)
    tenant.timezone = timezone
    return await keep_slot_hours_in_new_zone(db, tenant.id, old_tz, clinic_zone(timezone))
