"""Async SQLAlchemy database primitives.

Row-level security (migration 007) limits every tenant table to the rows of the tenant in the
`app.current_tenant` setting. Each transaction sets it - transaction-local, so pooled connections
never carry it over - from the verified token of the current request (see `_scope_transaction`).
Public endpoints that work before anyone is signed in (login, registration, password reset) choose
the tenant explicitly with `set_db_tenant`, after looking the account up through the narrow
cross-tenant functions in `core/cross_tenant.py`.
"""

from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from ..middleware.request_context import get_request_context
from .config import settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None

# Tenant/user chosen explicitly during a public request (registration, login, reset), as (tenant_id, user_id)
_db_scope_override: ContextVar[tuple[str, str | None] | None] = ContextVar("db_scope_override", default=None)

_SET_SCOPE = text(
    "SELECT set_config('app.current_tenant', :tenant_id, true), set_config('app.current_user_id', :user_id, true)"
)


def _current_scope() -> tuple[str, str] | None:
    override = _db_scope_override.get()
    if override is not None:
        return override[0], override[1] or ""
    context = get_request_context()
    if context is not None:
        return context.tenant_id, context.user_id
    return None


@event.listens_for(Session, "after_begin")
def _scope_transaction(session, transaction, connection) -> None:
    """Tell PostgreSQL which tenant (and user, for the audit trigger) this transaction acts for."""

    scope = _current_scope()
    if scope is not None:
        connection.execute(_SET_SCOPE, {"tenant_id": str(scope[0]), "user_id": str(scope[1])})


async def set_db_tenant(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> None:
    """Scope this request's database work to `tenant_id` (public endpoints, once the tenant is known).

    Applies to the transaction in progress and to every later transaction of the request.
    """

    _db_scope_override.set((str(tenant_id), str(user_id) if user_id else None))
    await db.execute(_SET_SCOPE, {"tenant_id": str(tenant_id), "user_id": str(user_id or "")})


def get_engine() -> AsyncEngine:
    """Return singleton async engine (created lazily)."""

    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            future=True,
            pool_pre_ping=True,
            # Keep bound values (emails, names, clinical text) out of error messages and tracebacks
            hide_parameters=True,
            # Lambda scales horizontally: each instance holds exactly 1 connection
            # so we don't exhaust RDS max_connections under concurrent invocations.
            pool_size=1,
            max_overflow=0,
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return singleton sessionmaker bound to lazy engine."""

    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _session_maker


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields async DB session."""

    async with get_session_maker()() as session:
        yield session


async def find_naive_timestamp_columns(conn: AsyncConnection) -> list[str]:
    """Return `table.column` for every public column still typed `timestamp without time zone`.

    The backend binds timezone-aware datetimes, so any such column means migration 003 hasn't
    been applied and writes would be silently shifted into the server's TimeZone.
    """

    result = await conn.execute(
        text(
            "SELECT table_name || '.' || column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND data_type = 'timestamp without time zone' "
            "ORDER BY 1"
        )
    )
    return list(result.scalars().all())
