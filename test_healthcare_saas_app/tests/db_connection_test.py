"""Small utility to verify PostgreSQL connectivity for local setup.

Usage:
    python .\\test_healthcare_saas_app\\tests\\db_connection_test.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def get_database_url() -> str:
    """Read TEST_DATABASE_URL from .env.test file."""
    env_test_path = Path(__file__).parent.parent / ".env.test"
    if not env_test_path.exists():
        raise FileNotFoundError(f".env.test file not found at {env_test_path}")
    
    with open(env_test_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('TEST_DATABASE_URL='):
                return line.split('=', 1)[1].strip()
    
    raise ValueError("TEST_DATABASE_URL not found in .env.test file")


def redact_db_url(db_url: str) -> str:
    """Mask password in logs while keeping host/db visible for debugging."""
    if "@" not in db_url or "://" not in db_url:
        return db_url

    try:
        scheme, rest = db_url.split("://", 1)
        credentials, host_part = rest.split("@", 1)

        if ":" not in credentials:
            return db_url

        username, _password = credentials.split(":", 1)
        return f"{scheme}://{username}:***@{host_part}"
    except Exception:
        return db_url


async def test_db_connection() -> bool:
    """Attempt a lightweight query and return success/failure."""
    database_url = get_database_url()
    print(f"Using TEST_DATABASE_URL: {redact_db_url(database_url)}")

    engine = create_async_engine(database_url, pool_pre_ping=True)

    try:
        async with engine.begin() as connection:
            result = await connection.execute(text("SELECT 1"))
            connected = result.scalar() == 1

        if connected:
            print("SUCCESS: Database connection test passed.")
            return True

        print("ERROR: Database query returned an unexpected result.")
        return False
    except Exception as exc:
        print(f"ERROR: Database connection test failed: {exc}")
        return False
    finally:
        await engine.dispose()


def main() -> int:
    """CLI entrypoint."""
    success = asyncio.run(test_db_connection())
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
