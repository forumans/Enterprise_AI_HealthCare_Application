"""In-memory sliding-window rate limiting for the public auth endpoints.

Slows down password guessing, reset-email flooding and mass self-registration. State lives in the
process, so each Lambda instance counts on its own: a determined attacker spread over many instances
gets through more slowly rather than not at all. Put an AWS WAF rate-based rule in front of CloudFront
for a global limit; this layer still helps locally and behind a single instance.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

TOO_MANY = "Too many attempts. Please wait a few minutes and try again."

# (max events, window seconds) per limit name
LIMITS: dict[str, tuple[int, int]] = {
    "login-email": (10, 15 * 60),       # failed logins for one email
    "login-ip": (50, 15 * 60),          # failed logins from one address
    "reset-email": (5, 15 * 60),        # reset emails requested for one address
    "reset-ip": (20, 15 * 60),          # reset requests / reset submissions from one address
    "register-ip": (10, 60 * 60),       # self-registrations from one address
}

_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    """The viewer's address: the first X-Forwarded-For hop (CloudFront / API Gateway), else the socket peer."""

    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(bucket: deque[float], window: int, now: float) -> None:
    while bucket and bucket[0] <= now - window:
        bucket.popleft()


def check(limit: str, key: str) -> None:
    """Raise 429 if `key` already used up `limit` within its window (does not record an event)."""

    max_events, window = LIMITS[limit]
    now = time.monotonic()
    with _lock:
        bucket = _events[(limit, key.lower())]
        _prune(bucket, window, now)
        if len(bucket) >= max_events:
            retry_after = int(bucket[0] + window - now) + 1
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=TOO_MANY, headers={"Retry-After": str(retry_after)})


def record(limit: str, key: str) -> None:
    """Count one event for `key`."""

    _, window = LIMITS[limit]
    now = time.monotonic()
    with _lock:
        bucket = _events[(limit, key.lower())]
        _prune(bucket, window, now)
        bucket.append(now)


def hit(limit: str, key: str) -> None:
    """Check, then count: for limits where every request counts (not just failures)."""

    check(limit, key)
    record(limit, key)


def clear(limit: str, key: str) -> None:
    with _lock:
        _events.pop((limit, key.lower()), None)


def reset_all() -> None:
    """Forget every counter (tests)."""

    with _lock:
        _events.clear()
