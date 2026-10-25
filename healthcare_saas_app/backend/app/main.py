"""FastAPI entrypoint with middleware wiring.

This file demonstrates how tenant/auth context, audit context, and security
headers are applied globally. The middleware ordering is intentional (outermost first):

1) CORS, then the unhandled-error catcher (so even a 500 carries CORS headers)
2) Security headers (outside the auth middleware, so its 401 responses get them too)
3) TenantContextMiddleware (auth + tenant context)
4) AuditContextMiddleware (inside auth, so it sees the tenant and user it set)

Starlette makes the last middleware added the outermost, so they're added in reverse order.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .api.routes import api_router
from .api.health import router as health_router
from .core.config import settings
from .core.database import find_naive_timestamp_columns, get_engine
from .middleware import AuditContextMiddleware, SecurityHeadersMiddleware, TenantContextMiddleware
from .models.base import Base


class _RedactAccessLog(logging.Filter):
    """Drop the client address and query string from Uvicorn access logs (local runs).

    Search URLs carry names, emails and phone numbers in `?q=`, and client IPs are personal data too.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            args = list(record.args)
            args[0] = "-"
            args[2] = str(args[2]).split("?", 1)[0]
            record.args = tuple(args)
        return True


def _configure_logging() -> logging.Logger:
    """Configure console logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler()],
    )
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, _RedactAccessLog) for f in access_logger.filters):
        access_logger.addFilter(_RedactAccessLog())
    return logging.getLogger("healthcare.app")


SERVER_ERROR_DETAIL = "Something went wrong on the server. Please try again, or contact support if it keeps happening."


async def catch_unhandled_errors(request: Request, call_next):
    """Turn an unexpected exception into a JSON 500.

    Registered just inside CORSMiddleware: Starlette's own last-resort 500 is produced outside
    every middleware, so it carries no CORS headers and browsers report it as "Failed to fetch".
    This response passes back through CORS, so the frontend can show the real error.
    """
    try:
        return await call_next(request)
    except Exception:
        logging.getLogger("healthcare.app").exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": SERVER_ERROR_DETAIL})


def create_app() -> FastAPI:
    """Create FastAPI app and register production middleware stack."""

    app_logger = _configure_logging()

    # No interactive API docs in production: they map every endpoint for an attacker
    is_production = (settings.app_env or "").lower() in {"production", "prod"}
    app = FastAPI(
        title="Healthcare SaaS API",
        version="1.0.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    # Exception handler to prevent exposing sensitive data in validation errors
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors without exposing sensitive data."""
        # Log which fields failed and why - never the submitted values (names, emails, passwords)
        problems = [f"{'.'.join(str(part) for part in err.get('loc', ()))}: {err.get('type')}" for err in exc.errors()]
        app_logger.warning("Validation error on %s %s: %s", request.method, request.url.path, "; ".join(problems))
        
        # Return a generic error message without the input data
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid request format. Please check your input and try again."},
        )

    # Centralized configuration source for all runtime secrets and CORS values.
    jwt_secret = settings.jwt_secret
    jwt_algorithm = settings.jwt_algorithm
    cors_origins = [
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ]

    app.add_middleware(AuditContextMiddleware)
    app.add_middleware(
        TenantContextMiddleware,
        secret_key=jwt_secret,
        algorithm=jwt_algorithm,
        excluded_paths={
            "/health",
            "/api/health",
            "/api/health/ready",
            "/api/health/live",
            "/auth/login",
            "/api/auth/login",
            "/auth/register",
            "/api/auth/register",
            "/auth/forgot-password",
            "/api/auth/forgot-password",
            "/auth/reset-password",
            "/api/auth/reset-password",
            # Not /doctors: listing doctors needs the caller's clinic, so it must read the token.
            # (An excluded path skips token decoding, so even logged-in calls would get 401.)
            "/doctors/register",
            "/api/doctors/register",
            "/admin/register",
            "/api/admin/register",
            "/admin/setup-status",
            "/api/admin/setup-status",
        },
        excluded_prefixes=(),
    )
    app.add_middleware(SecurityHeadersMiddleware)
    # Inside CORS (added just before it), so server errors still get CORS headers
    app.add_middleware(BaseHTTPMiddleware, dispatch=catch_unhandled_errors)

    # CORS is required so browser clients (React) can call FastAPI.
    # Add CORS middleware last to ensure it handles all requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup() -> None:
        """Initialize ORM metadata for local/dev usage.

        Production deployments should use Alembic migrations; this startup hook
        keeps first-run local development productive.
        """

        if not settings.db_schema_init_on_startup:
            app_logger.info(
                "Skipping ORM metadata initialization on startup "
                "(DB_SCHEMA_INIT_ON_STARTUP=false)."
            )
        else:
            try:
                async with get_engine().begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                app_logger.info("Database initialization completed successfully.")
            except Exception:
                app_logger.exception("Database initialization failed during startup.")
                raise

        await _require_timestamptz_columns()

    async def _require_timestamptz_columns() -> None:
        """Refuse to start against a database that hasn't had migration 003 applied.

        This code binds timezone-aware datetimes. Against a `timestamp without time zone`
        column, PostgreSQL silently converts them to the server's TimeZone, storing wrong
        values (e.g. 8 AM New York saved as 08:00 and later read back as 08:00 UTC).
        """

        try:
            async with get_engine().connect() as conn:
                naive_columns = await find_naive_timestamp_columns(conn)
        except SQLAlchemyError:
            # Don't block startup when the DB is unreachable - the health endpoint reports that.
            app_logger.warning("Could not verify timestamp column types at startup.", exc_info=True)
            return

        if naive_columns:
            raise RuntimeError(
                "Database schema is out of date: these columns are still 'timestamp without time zone': "
                + ", ".join(naive_columns)
                + ". Apply backend/migrations/003_convert_timestamps_to_timestamptz.sql (as the table "
                "owner) before starting this version of the backend."
            )

    # Expose business APIs under /api for CloudFront single-behavior proxying.
    app.include_router(api_router, prefix="/api")
    # Keep legacy unprefixed routes for backward compatibility.
    app.include_router(api_router)
    app.include_router(health_router, prefix="/api")

    return app


app = create_app()

# Lambda handler — translates API Gateway HTTP API events to ASGI.
# lifespan="off" prevents Mangum from trying to manage startup/shutdown events,
# which are handled by FastAPI's own @app.on_event hooks instead.
from mangum import Mangum  # noqa: E402
handler = Mangum(app, lifespan="off")
