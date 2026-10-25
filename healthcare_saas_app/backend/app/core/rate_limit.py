"""Sliding-window rate limiting for the public auth endpoints.

Slows down password guessing, reset-email flooding and mass self-registration. Events are counted in
PostgreSQL (table rate_limit_events, migration 009), so every Lambda instance shares the same counts and
the limits hold globally. Keys (emails, client addresses) are stored only as SHA-256 hashes.

Until migration 009 is applied (or when there is no database, as in unit tests) the counts live in this
process instead, as before: each instance then counts on its own.

Each recorded event is committed at once, so it counts even when the request then fails (a wrong
password raises 401 and rolls the request back). Call these before the endpoint does its own work.
"""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TOO_MANY = "Too many attempts. Please wait a few minutes and try again."

# (max events, window seconds) per limit name
LIMITS: dict[str, tuple[int, int]] = {
    "login-email": (10, 15 * 60),       # failed logins for one email
    "login-ip": (50, 15 * 60),          # failed logins from one address
    "reset-email": (5, 15 * 60),        # reset emails requested for one address
    "reset-ip": (20, 15 * 60),          # reset requests / reset submissions from one address
    "register-ip": (10, 60 * 60),       # self-registrations from one address
}
# Rows older than the longest window are no longer needed
_KEEP_SECONDS = max(window for _, window in LIMITS.values())

# In-process counts, used when the table isn't available
_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    """The viewer's address: the first X-Forwarded-For hop (CloudFront / API Gateway), else the socket peer."""

    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _hash(key: str) -> str:
    return hashlib.sha256(key.lower().encode("utf-8")).hexdigest()


def _too_many(retry_after: float) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=TOO_MANY, headers={"Retry-After": str(max(1, math.ceil(retry_after)))}
    )


async def _use_table(db: AsyncSession) -> bool:
    """Whether rate_limit_events exists in this database (a catalog lookup). Anything unexpected means "no"."""

    try:
        return (await db.execute(text("SELECT to_regclass('public.rate_limit_events') IS NOT NULL"))).scalar() is True
    except Exception:
        return False


# --- in-process store ---------------------------------------------------------------------------------

def _prune(bucket: deque[float], window: int, now: float) -> None:
    while bucket and bucket[0] <= now - window:
        bucket.popleft()


def _memory_check(limit: str, key: str) -> None:
    max_events, window = LIMITS[limit]
    now = time.monotonic()
    with _lock:
        bucket = _events[(limit, key.lower())]
        _prune(bucket, window, now)
        if len(bucket) >= max_events:
            raise _too_many(bucket[0] + window - now)


def _memory_record(limit: str, key: str) -> None:
    _, window = LIMITS[limit]
    now = time.monotonic()
    with _lock:
        bucket = _events[(limit, key.lower())]
        _prune(bucket, window, now)
        bucket.append(now)


def _memory_clear(limit: str, key: str) -> None:
    with _lock:
        _events.pop((limit, key.lower()), None)


# --- public API ----------------------------------------------------------------------------------------

async def check(db: AsyncSession, limit: str, key: str) -> None:
    """Raise 429 if `key` already used up `limit` within its window (does not record an event)."""

    if not await _use_table(db):
        return _memory_check(limit, key)
    max_events, window = LIMITS[limit]
    row = (
        await db.execute(
            text(
                "SELECT count(*) AS events, extract(epoch FROM min(created_at) + make_interval(secs => :window) - now()) AS retry_after "
                "FROM rate_limit_events WHERE limit_name = :limit AND key_hash = :key AND created_at > now() - make_interval(secs => :window)"
            ),
            {"limit": limit, "key": _hash(key), "window": window},
        )
    ).one()
    if row.events >= max_events:
        raise _too_many(float(row.retry_after or 1))


async def record(db: AsyncSession, limit: str, key: str) -> None:
    """Count one event for `key` (committed immediately)."""

    if not await _use_table(db):
        return _memory_record(limit, key)
    await db.execute(
        text("INSERT INTO rate_limit_events (limit_name, key_hash) VALUES (:limit, :key)"),
        {"limit": limit, "key": _hash(key)},
    )
    await db.execute(
        text("DELETE FROM rate_limit_events WHERE created_at < now() - make_interval(secs => :keep)"),
        {"keep": _KEEP_SECONDS},
    )
    await db.commit()


async def hit(db: AsyncSession, limit: str, key: str) -> None:
    """Check, then count: for limits where every request counts (not just failures)."""

    await check(db, limit, key)
    await record(db, limit, key)


async def clear(db: AsyncSession, limit: str, key: str) -> None:
    """Forget `key`'s events for `limit` (e.g. after a successful login)."""

    if not await _use_table(db):
        return _memory_clear(limit, key)
    await db.execute(
        text("DELETE FROM rate_limit_events WHERE limit_name = :limit AND key_hash = :key"),
        {"limit": limit, "key": _hash(key)},
    )
    await db.commit()


def reset_all() -> None:
    """Forget every in-process count (tests; each integration test gets a fresh database)."""

    with _lock:
        _events.clear()
