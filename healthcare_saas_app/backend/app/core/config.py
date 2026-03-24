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
    host: str = os.getenv("HOST")
    port: int = int(os.getenv("PORT"))


# Create a singleton instance
settings = Settings()
