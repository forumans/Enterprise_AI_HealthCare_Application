"""Audit log query endpoint used by admin UI."""

from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...core.timeutils import parse_client_datetime
from ...models import AuditLog

router = APIRouter()


@router.get("/audit-logs")
async def list_audit_logs(
    table: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    identity: CurrentIdentity = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    conditions = [AuditLog.tenant_id == identity.tenant_id]

    if table.strip():
        conditions.append(AuditLog.table_name == table.strip())
    try:
        if date_from.strip():
            conditions.append(AuditLog.performed_at >= parse_client_datetime(date_from))
        if date_to.strip():
            conditions.append(AuditLog.performed_at <= parse_client_datetime(date_to))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid datetime format.") from exc

    stmt = select(AuditLog).where(and_(*conditions)).order_by(AuditLog.performed_at.desc()).limit(200)
    rows = (await db.execute(stmt)).scalars().all()

    return [
        {
            "action": row.action_type,
            "timestamp": row.performed_at.isoformat(),
            "performed_by": row.performed_by or "",
            "table": row.table_name,
            "old": row.old_data or {},
            "new": row.new_data or {},
        }
        for row in rows
    ]
