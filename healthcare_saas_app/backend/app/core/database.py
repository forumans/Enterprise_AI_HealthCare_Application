"""Async SQLAlchemy database primitives."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return singleton async engine (created lazily)."""

    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            future=True,
            pool_pre_ping=True,
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
