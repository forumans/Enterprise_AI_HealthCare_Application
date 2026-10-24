"""Tenant-aware authentication middleware.

This middleware enforces the multi-tenant contract from
`Healthcare_Postgres_DB_Script.sql` and the backend prompt:

- tenant context is resolved from JWT claim ``tenant_id``
- user identity includes ``user_id`` and ``role``
- valid roles match DB enum `user_role` (ADMIN, DOCTOR, PATIENT, SUPPORT_STAFF)
- request context is isolated per request (no cross-request leakage)

Industry best-practice behavior implemented here:
1) strict Bearer token parsing
2) JWT signature and expiry validation
3) UUID validation for tenant_id/user_id claims
4) explicit exclusions for public endpoints (health, auth login/register)
5) stable request-id for tracing and audit correlation
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable, Optional
from uuid import UUID, uuid4

import jwt

from fastapi import status
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .request_context import RequestContext, reset_request_context, set_request_context

ROLE_ENUM = {"ADMIN", "DOCTOR", "PATIENT", "SUPPORT_STAFF"}


def extract_bearer_token(authorization: str | None) -> Optional[str]:
    """Extract token from Authorization header.

    Accepts format: ``Authorization: Bearer <token>``.
    Returns ``None`` when missing or malformed.
    """

    if not authorization:
        return None

    parts = authorization.strip().split(" ", maxsplit=1)
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None

    token = parts[1].strip()
    return token or None


def decode_jwt_claims(token: str, secret_key: str, algorithm: str) -> dict:
    """Decode and validate JWT claims.

    Raises ValueError on invalid token or if JWT dependency is not present.
    """

    try:
        claims = jwt.decode(token, secret_key, algorithms=[algorithm])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token."
        ) from exc

    if not isinstance(claims, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token payload."
        )
    return claims


def _as_uuid(value: object, field_name: str) -> str:
    """Validate UUID claims and normalize to canonical string format."""

    if not isinstance(value, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"JWT claim '{field_name}' is missing or invalid."
        )

    try:
        return str(UUID(value))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"JWT claim '{field_name}' must be a valid UUID."
        ) from exc


def _as_role(value: object) -> str:
    """Validate role claim against DB enum values from SQL schema."""

    if not isinstance(value, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT claim 'role' is missing or invalid."
        )

    role = value.upper()
    if role not in ROLE_ENUM:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid role '{value}'. Must be one of: {sorted(ROLE_ENUM)}."
        )
    return role


def _is_excluded_path(path: str, exact: Iterable[str], prefixes: Iterable[str]) -> bool:
    """Return True when middleware auth enforcement should be skipped."""

    if path in exact:
        return True
    return any(path.startswith(prefix) for prefix in prefixes)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Attach validated tenant/user context to `request.state` and contextvars."""

    def __init__(
        self,
        app,
        *,
        secret_key: str,
        algorithm: str = "HS256",
        excluded_paths: Optional[Iterable[str]] = None,
        excluded_prefixes: Optional[Iterable[str]] = None,
    ) -> None:
        super().__init__(app)
        self.secret_key = secret_key
        self.algorithm = algorithm

        # Public routes should include health checks and auth bootstrap endpoints.
        self.excluded_paths = set(excluded_paths) if excluded_paths is not None else {"/health", "/auth/login", "/auth/register"}
        self.excluded_prefixes = tuple(excluded_prefixes or ("/docs", "/openapi", "/redoc"))

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = str(uuid4())
        request.state.request_id = request_id

        path = request.url.path

        # Allow OPTIONS requests for CORS preflight
        if request.method == "OPTIONS" or _is_excluded_path(request.url.path, self.excluded_paths, self.excluded_prefixes):
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        token = extract_bearer_token(request.headers.get("Authorization"))
        if token is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header."},
                headers={"X-Request-ID": request_id},
            )

        try:
            claims = decode_jwt_claims(token, self.secret_key, self.algorithm)
            tenant_id = _as_uuid(claims.get("tenant_id"), "tenant_id")
            user_id = _as_uuid(claims.get("user_id"), "user_id")
            role = _as_role(claims.get("role"))

            # Optional hardening: reject tokens with issued-at in the future.
            iat = claims.get("iat")
            if isinstance(iat, (int, float)) and datetime.fromtimestamp(iat, tz=UTC) > datetime.now(tz=UTC):
                raise ValueError("Access token has an invalid issued-at timestamp.")

        except ValueError as exc:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": str(exc)},
                headers={"X-Request-ID": request_id},
            )

        # Store context on both request.state and contextvars for downstream usage.
        request.state.tenant_id = tenant_id
        request.state.user_id = user_id
        request.state.role = role
        context_token = set_request_context(
            RequestContext(request_id=request_id, tenant_id=tenant_id, user_id=user_id, role=role)
        )

        try:
            response = await call_next(request)
        finally:
            reset_request_context(context_token)

        response.headers["X-Request-ID"] = request_id
        return response
