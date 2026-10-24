"""Application configuration.

Centralizes environment-driven settings for database/JWT so both middleware and
API dependencies read from one source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


def _env_flag(name: str) -> bool:
    """Parse common truthy env values into bool."""
    value = os.getenv(name)
    return value and value.strip().lower() in {"1", "true", "yes", "on"}

# Load environment variables with explicit precedence:
# 1) .env (base defaults)
# 2) .env.test (test-only overrides when APP_ENV=test)
load_dotenv(".env", override=False)
if os.getenv("APP_ENV", "dev").lower() == "test":
    load_dotenv(".env.test", override=True)


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV")
    database_url: str = os.getenv("DATABASE_URL")
    jwt_secret: str = os.getenv("JWT_SECRET")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM")
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES"))
    cors_origins: str = os.getenv("CORS_ORIGINS")
    db_schema_init_on_startup: bool = _env_flag("DB_SCHEMA_INIT_ON_STARTUP")
    # HOST/PORT are only used by Uvicorn in local development.
    # Lambda does not need them, so they default to safe values.
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    # S3 bucket for document uploads (required when running on Lambda)
    s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "")
    # Outgoing email (password reset links). Email is skipped when SMTP_HOST is empty.
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_tls: bool = _env_flag("SMTP_TLS") if os.getenv("SMTP_TLS") is not None else True
    smtp_from: str = os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USER", "")
    # Public URL of the web app, used to build links in emails (defaults to the first CORS origin)
    frontend_url: str = (os.getenv("FRONTEND_URL", "") or (os.getenv("CORS_ORIGINS") or "").split(",")[0]).strip().rstrip("/")
    password_reset_minutes: int = int(os.getenv("PASSWORD_RESET_MINUTES", "30"))


# Create a singleton instance
settings = Settings()
