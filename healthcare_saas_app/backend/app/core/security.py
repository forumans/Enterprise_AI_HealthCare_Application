"""Security helpers for password hashing and JWT handling."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Dict

import jwt

from .config import settings


def hash_password(password: str) -> str:
    """Hash password for persistence.

    Uses PBKDF2 for consistency.
    """
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def verify_password(password: str, hashed_value: str) -> bool:
    """Verify incoming password against stored hash."""

    if hashed_value.startswith("pbkdf2$"):
        try:
            _, salt_hex, digest_hex = hashed_value.split("$", maxsplit=2)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except ValueError:
            return False
        current = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
        return hmac.compare_digest(current, expected)

    # For backward compatibility with bcrypt hashes
    try:
        import bcrypt  # type: ignore
        return bcrypt.checkpw(password.encode("utf-8"), hashed_value.encode("utf-8"))
    except Exception:
        return False


PASSWORD_RESET_PURPOSE = "password_reset"


def _password_reset_key() -> str:
    # A key separate from the access-token key, so a reset link can never be used as a session
    return hmac.new(settings.jwt_secret.encode("utf-8"), b"password-reset", hashlib.sha256).hexdigest()


def _password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:24]


def create_password_reset_token(*, user_id: str, password_hash: str, expires_minutes: int | None = None) -> str:
    """Signed, short-lived reset token. It embeds a fingerprint of the current password hash, so it
    stops working as soon as the password changes - each link works once."""

    now = datetime.now(tz=UTC)
    ttl = timedelta(minutes=expires_minutes or settings.password_reset_minutes)
    payload = {
        "sub": user_id,
        "purpose": PASSWORD_RESET_PURPOSE,
        "pwh": _password_fingerprint(password_hash),
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, _password_reset_key(), algorithm="HS256")


def read_password_reset_token(token: str) -> tuple[str, str] | None:
    """Return (user_id, password fingerprint) for a valid, unexpired reset token, else None."""

    try:
        claims = jwt.decode(token, _password_reset_key(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if claims.get("purpose") != PASSWORD_RESET_PURPOSE or not claims.get("sub") or not claims.get("pwh"):
        return None
    return claims["sub"], claims["pwh"]


def password_reset_token_matches(fingerprint: str, password_hash: str) -> bool:
    """True while the account still has the password the token was issued for."""

    return hmac.compare_digest(fingerprint, _password_fingerprint(password_hash))


def create_access_token(*, user_id: str, tenant_id: str, role: str, expires_minutes: int | None = None) -> str:
    """Create JWT access token with required tenant/user claims."""

    ttl = timedelta(minutes=expires_minutes or settings.access_token_minutes)
    now = datetime.now(tz=UTC)
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
