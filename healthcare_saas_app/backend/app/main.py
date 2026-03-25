"""FastAPI entrypoint with middleware wiring.

This file demonstrates how tenant/auth context, audit context, and security
headers are applied globally. The middleware ordering is intentional:

1) Security headers (always applied)
2) TenantContextMiddleware (auth + tenant context)
3) AuditContextMiddleware (captures actor/tenant for write operations)
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import api_router
from .api.health import router as health_router
from .core.config import settings
from .core.database import get_engine
from .middleware import AuditContextMiddleware, SecurityHeadersMiddleware, TenantContextMiddleware
from .models.base import Base


def _configure_logging() -> logging.Logger:
    """Configure console logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler()],
    )
    return logging.getLogger("healthcare.app")


def create_app() -> FastAPI:
    """Create FastAPI app and register production middleware stack."""

    app_logger = _configure_logging()

    app = FastAPI(title="Healthcare SaaS API", version="1.0.0")

    # Exception handler to prevent exposing sensitive data in validation errors
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors without exposing sensitive data."""
        # Log the full error for debugging
        app_logger.error(f"Validation error: {exc.errors()}")
        
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

    app.add_middleware(SecurityHeadersMiddleware)
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
            "/doctors",
            "/api/doctors",
            "/doctors/register",
            "/api/doctors/register",
            "/admin/register",
            "/api/admin/register",
            "/doctor/availability/{doctor_id}/ndays",
            "/api/doctor/availability/{doctor_id}/ndays",
        },
        excluded_prefixes=(),
    )
    app.add_middleware(AuditContextMiddleware)
    
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
            return

        try:
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            app_logger.info("Database initialization completed successfully.")
        except Exception:
            app_logger.exception("Database initialization failed during startup.")
            raise

    # Expose business APIs under /api for CloudFront single-behavior proxying.
    app.include_router(api_router, prefix="/api")
    # Keep legacy unprefixed routes for backward compatibility.
    app.include_router(api_router)
    app.include_router(health_router, prefix="/api")

    return app


app = create_app()
