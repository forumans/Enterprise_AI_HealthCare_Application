"""Helpers for the PostgreSQL integration tests.

These tests run real SQL - the migrations, the booking trigger, unique indexes and the backend's
route/service code - against a real PostgreSQL server. They are skipped unless
HC_TEST_PG_ADMIN_URL points at a *disposable* server whose user may CREATE/DROP DATABASE, e.g.:

    docker run -d --name hc-test-pg -e POSTGRES_PASSWORD=test -p 55440:5432 postgres:17
    HC_TEST_PG_ADMIN_URL=postgresql://postgres:test@localhost:55440/postgres

Each test creates its own database named hc_it_<random>, loads baseline_schema_pre_003.sql into it
and drops it afterwards. No other database on the server is read or modified.
"""

from __future__ import annotations

import os
import unittest
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg

ADMIN_URL = os.environ.get("HC_TEST_PG_ADMIN_URL", "")
HERE = Path(__file__).resolve().parent
MIGRATIONS_DIR = HERE.parent.parent / "migrations"
BASELINE_SCHEMA = HERE / "baseline_schema_pre_003.sql"
CLINIC_TZ = "America/New_York"


def require_pg() -> None:
    if not ADMIN_URL:
        raise unittest.SkipTest("HC_TEST_PG_ADMIN_URL is not set - skipping PostgreSQL integration tests.")


class TempDatabase:
    """A throwaway database loaded with the pre-migration-003 schema."""

    name: str
    url: str

    async def create(self, *, server_timezone: str = CLINIC_TZ, migrate: bool = False) -> "TempDatabase":
        self.name = f"hc_it_{uuid.uuid4().hex[:12]}"
        admin = await asyncpg.connect(ADMIN_URL)
        try:
            await admin.execute(f'CREATE DATABASE "{self.name}"')
            # Mirrors the server setting that CURRENT_TIMESTAMP defaults are written in.
            await admin.execute(f"ALTER DATABASE \"{self.name}\" SET timezone TO '{server_timezone}'")
        finally:
            await admin.close()
        self.url = urlsplit(ADMIN_URL)._replace(path=f"/{self.name}").geturl()

        conn = await self.connect()
        try:
            await conn.execute(BASELINE_SCHEMA.read_text(encoding="utf-8"))
        finally:
            await conn.close()
        if migrate:
            await self.run_migration("003_convert_timestamps_to_timestamptz.sql")
        return self

    @property
    def sqlalchemy_url(self) -> str:
        return self.url.replace("postgresql://", "postgresql+asyncpg://", 1)

    async def connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(self.url)

    async def run_migration(self, filename: str, settings: dict[str, str] | None = None) -> None:
        """Run a migration file the way psql -f would (its own BEGIN/COMMIT), in a fresh session."""

        conn = await self.connect()
        try:
            for key, value in (settings or {}).items():
                await conn.execute("SELECT set_config($1, $2, false)", key, value)
            await conn.execute((MIGRATIONS_DIR / filename).read_text(encoding="utf-8"))
        finally:
            await conn.close()

    async def drop(self) -> None:
        admin = await asyncpg.connect(ADMIN_URL)
        try:
            await admin.execute(f'DROP DATABASE IF EXISTS "{self.name}" WITH (FORCE)')
        finally:
            await admin.close()


async def seed_clinic(conn: asyncpg.Connection) -> dict[str, str]:
    """Insert a tenant with one doctor, two patients and an admin. Returns their ids."""

    tenant = await conn.fetchval("INSERT INTO tenants (name) VALUES ('Test Clinic') RETURNING id")

    async def user(email: str, role: str) -> str:
        return await conn.fetchval(
            "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, $2, 'x', $3) RETURNING id",
            tenant, email, role,
        )

    ids = {"tenant": tenant}
    ids["doctor_user"] = await user("doc@example.test", "DOCTOR")
    ids["doctor"] = await conn.fetchval(
        "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Test') RETURNING id",
        tenant, ids["doctor_user"],
    )
    for n in (1, 2):
        ids[f"patient{n}_user"] = await user(f"patient{n}@example.test", "PATIENT")
        ids[f"patient{n}"] = await conn.fetchval(
            "INSERT INTO patients (tenant_id, user_id, full_name) VALUES ($1, $2, $3) RETURNING id",
            tenant, ids[f"patient{n}_user"], f"Patient {n}",
        )
    ids["admin_user"] = await user("admin@example.test", "ADMIN")
    return {k: str(v) for k, v in ids.items()}
