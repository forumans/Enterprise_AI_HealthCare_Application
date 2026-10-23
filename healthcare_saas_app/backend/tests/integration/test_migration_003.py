"""Migration 003 (timestamp -> timestamptz) must not lose or shift any data."""

import unittest
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.core.database import find_naive_timestamp_columns
from backend.tests.integration._pg import CLINIC_TZ, TempDatabase, require_pg, seed_clinic

MIGRATION = "003_convert_timestamps_to_timestamptz.sql"
ROLLBACK = "003_convert_timestamps_to_timestamptz_rollback.sql"
# Columns filled by a CURRENT_TIMESTAMP default are written in the server's TimeZone;
# every other timestamp column is written by the backend as naive UTC.
DB_DEFAULT_COLUMNS = {"created_at", "performed_at"}


async def snapshot(conn: asyncpg.Connection) -> dict[str, dict]:
    """Every row of every public table, keyed by table then id."""

    tables = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    )
    return {
        t["table_name"]: {r["id"]: dict(r) for r in await conn.fetch(f'SELECT * FROM public."{t["table_name"]}"')}
        for t in tables
    }


class Migration003Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        require_pg()
        self.db = await TempDatabase().create()
        conn = await self.db.connect()
        try:
            self.ids = ids = await seed_clinic(conn)
            # App-written columns hold naive UTC.
            await conn.executemany(
                "INSERT INTO doctor_availability (tenant_id, doctor_id, slot_time, status) VALUES ($1, $2, $3, $4)",
                [
                    (ids["tenant"], ids["doctor"], datetime(2026, 11, 2, 13, 0), "AVAILABLE"),
                    (ids["tenant"], ids["doctor"], datetime(2026, 11, 2, 14, 0), "BOOKED"),
                    (ids["tenant"], ids["doctor"], datetime(2026, 3, 8, 7, 0), "BLOCKED"),  # DST-start day
                ],
            )
            await conn.execute(
                "INSERT INTO appointments (tenant_id, doctor_id, patient_id, appointment_time, notes) "
                "VALUES ($1, $2, $3, '2026-11-02 14:00', 'checkup')",
                ids["tenant"], ids["doctor"], ids["patient1"],
            )
            await conn.execute(
                "INSERT INTO appointments (tenant_id, doctor_id, patient_id, appointment_time, status, deleted_at) "
                "VALUES ($1, $2, $3, '2026-10-01 15:00', 'CANCELLED', '2026-09-30 18:45:12.123456')",
                ids["tenant"], ids["doctor"], ids["patient2"],
            )
            # A DB-default value in the ambiguous fall-back hour must still round-trip.
            await conn.execute("UPDATE patients SET created_at = '2026-11-01 01:30:00' WHERE id = $1", ids["patient1"])
            self.before = await snapshot(conn)
        finally:
            await conn.close()

    async def asyncTearDown(self):
        await self.db.drop()

    async def test_converts_every_column_and_preserves_every_instant(self):
        await self.db.run_migration(MIGRATION)

        conn = await self.db.connect()
        try:
            naive = await conn.fetchval(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = 'public' AND data_type = 'timestamp without time zone'"
            )
            after = await snapshot(conn)
            plan = {(r["table_name"], r["column_name"]): r["source_zone"]
                    for r in await conn.fetch("SELECT * FROM tz_migration_backup.column_plan")}
        finally:
            await conn.close()

        self.assertEqual(naive, 0)
        self.assertEqual(len(plan), 24)
        for (table, column), zone in plan.items():
            self.assertEqual(zone, CLINIC_TZ if column in DB_DEFAULT_COLUMNS else "UTC", f"{table}.{column}")

        self.assertEqual(after.keys(), self.before.keys())
        checked = 0
        for table, rows in self.before.items():
            self.assertEqual(rows.keys(), after[table].keys(), f"rows lost/added in {table}")
            for row_id, old in rows.items():
                new = after[table][row_id]
                for column, old_value in old.items():
                    if (table, column) in plan and old_value is not None:
                        zone = ZoneInfo(plan[(table, column)])
                        # A wall-clock time in the fall-back hour occurs twice; a naive value can't say
                        # which, so either reading is acceptable (PostgreSQL picks standard time).
                        # Everywhere else both readings coincide, so this is an exact check.
                        readings = {old_value.replace(tzinfo=zone, fold=f).astimezone(UTC) for f in (0, 1)}
                        self.assertIn(new[column], readings, f"{table}.{column} id={row_id}")
                        self.assertEqual(new[column].astimezone(zone).replace(tzinfo=None), old_value)
                    else:
                        self.assertEqual(new[column], old_value, f"{table}.{column} id={row_id}")
                    checked += 1
        self.assertGreater(checked, 50)

    async def test_rerun_is_refused_and_changes_nothing(self):
        await self.db.run_migration(MIGRATION)
        conn = await self.db.connect()
        try:
            migrated = await snapshot(conn)
        finally:
            await conn.close()

        with self.assertRaisesRegex(asyncpg.PostgresError, "tz_migration_backup already exists"):
            await self.db.run_migration(MIGRATION)

        conn = await self.db.connect()
        try:
            self.assertEqual(await snapshot(conn), migrated)
        finally:
            await conn.close()

    async def test_rollback_restores_original_values_exactly(self):
        await self.db.run_migration(MIGRATION)
        await self.db.run_migration(ROLLBACK)

        conn = await self.db.connect()
        try:
            self.assertEqual(await snapshot(conn), self.before)
            tz_columns = await conn.fetchval(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = 'public' AND data_type = 'timestamp with time zone'"
            )
        finally:
            await conn.close()
        self.assertEqual(tz_columns, 0)

    async def test_unconvertible_value_aborts_and_leaves_database_untouched(self):
        # 2:30 AM on the spring-forward day doesn't exist in New York, so it can't be a real
        # CURRENT_TIMESTAMP value - the migration must refuse rather than guess.
        conn = await self.db.connect()
        try:
            await conn.execute("UPDATE users SET created_at = '2026-03-08 02:30:00' WHERE id = $1", self.ids["admin_user"])
            before = await snapshot(conn)
        finally:
            await conn.close()

        with self.assertRaisesRegex(asyncpg.PostgresError, "Verification failed for users.created_at"):
            await self.db.run_migration(MIGRATION)

        conn = await self.db.connect()
        try:
            self.assertEqual(await snapshot(conn), before)
            self.assertIsNone(await conn.fetchval("SELECT to_regnamespace('tz_migration_backup')"))
        finally:
            await conn.close()

    async def test_backend_startup_check_detects_unmigrated_schema(self):
        engine = create_async_engine(self.db.sqlalchemy_url, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                self.assertIn("doctor_availability.slot_time", await find_naive_timestamp_columns(conn))
            await self.db.run_migration(MIGRATION)
            async with engine.connect() as conn:
                self.assertEqual(await find_naive_timestamp_columns(conn), [])
        finally:
            await engine.dispose()


if __name__ == "__main__":
    unittest.main()
