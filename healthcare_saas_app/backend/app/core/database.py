"""Async SQLAlchemy database primitives."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

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
