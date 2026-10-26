"""Clinics in different time zones (tenants.timezone, migration 008) against a real database.

- migration 008 keeps existing clinics in the zone they ran in, honours migration.clinic_timezone and is
  idempotent
- each request carries its own clinic's zone; default slots are 8 AM-11 PM in that zone
- login tells the browser which zone to show times in
- an admin changing the zone keeps open/blocked slots at the same local hour and booked times unchanged
- the first-admin setup can set the zone

Skipped unless HC_TEST_PG_ADMIN_URL is set (see _pg.py).
"""

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.api.routes.appointments import CreateAppointmentRequest, create_appointment
from backend.app.api.routes.auth import LoginRequest, login
from backend.app.api.routes.doctor import AdminRegisterRequest, list_all_availability, register_admin
from backend.app.api.routes.tenants import UpdateTenantRequest, get_current_tenant, update_current_tenant
from backend.app.core import rate_limit, timeutils
from backend.app.core.dependencies import get_current_identity
from backend.app.core.security import hash_password
from backend.app.models import Doctor
from backend.app.services.availability_service import apply_block, ensure_default_slots, plan_range_change
from backend.tests.integration._pg import CLINIC_TZ, FAKE_HTTP, TempDatabase, http_from, require_pg, seed_clinic

NY = ZoneInfo(CLINIC_TZ)
LA = ZoneInfo("America/Los_Angeles")


def at(day, hour: int, zone: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=zone).astimezone(UTC)


class MigrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        require_pg()
        self.db = await TempDatabase().create()
        await self.db.run_migration("003_convert_timestamps_to_timestamptz.sql")
        conn = await self.db.connect()
        try:
            await conn.execute("INSERT INTO tenants (name) VALUES ('Existing Clinic')")
        finally:
            await conn.close()

    async def asyncTearDown(self):
        await self.db.drop()

    async def zones(self) -> list[str]:
        conn = await self.db.connect()
        try:
            return [r["timezone"] for r in await conn.fetch("SELECT timezone FROM tenants ORDER BY created_at")]
        finally:
            await conn.close()

    async def test_existing_clinics_keep_the_zone_they_ran_in(self):
        await self.db.run_migration("008_add_tenant_timezone.sql")
        self.assertEqual(await self.zones(), ["America/New_York"])
        await self.db.run_migration("008_add_tenant_timezone.sql")  # idempotent
        self.assertEqual(await self.zones(), ["America/New_York"])

    async def test_the_deployments_old_zone_can_be_passed_in(self):
        await self.db.run_migration("008_add_tenant_timezone.sql", {"migration.clinic_timezone": "America/Chicago"})
        conn = await self.db.connect()
        try:
            await conn.execute("INSERT INTO tenants (name) VALUES ('New Clinic')")
        finally:
            await conn.close()
        self.assertEqual(await self.zones(), ["America/Chicago", "America/Chicago"])

    async def test_a_misspelled_zone_changes_nothing(self):
        with self.assertRaises(asyncpg.PostgresError):
            await self.db.run_migration("008_add_tenant_timezone.sql", {"migration.clinic_timezone": "America/Chicgo"})
        conn = await self.db.connect()
        try:
            column = await conn.fetchval(
                "SELECT 1 FROM information_schema.columns WHERE table_name = 'tenants' AND column_name = 'timezone'"
            )
        finally:
            await conn.close()
        self.assertIsNone(column)


class ClinicTimeZoneTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        require_pg()
        rate_limit.reset_all()
        self.db = await TempDatabase().create(migrate=True)
        conn = await self.db.connect()
        try:
            self.ids = await seed_clinic(conn)  # New York clinic (the migration default)
            await conn.execute("INSERT INTO admins (tenant_id, user_id, full_name) VALUES ($1, $2, 'Ada Admin')", self.ids["tenant"], self.ids["admin_user"])
            self.ids["la_tenant"] = str(await conn.fetchval(
                "INSERT INTO tenants (name, domain, timezone) VALUES ('West Clinic', 'west.test', 'America/Los_Angeles') RETURNING id"
            ))
            self.ids["la_doctor_user"] = str(await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'west.doc@example.test', $2, 'DOCTOR') RETURNING id",
                self.ids["la_tenant"], hash_password("WestDoc1234"),
            ))
            self.ids["la_doctor"] = str(await conn.fetchval(
                "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr West') RETURNING id",
                self.ids["la_tenant"], self.ids["la_doctor_user"],
            ))
        finally:
            await conn.close()
        self.engine = create_async_engine(self.db.sqlalchemy_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def asyncTearDown(self):
        await self.engine.dispose()
        await self.db.drop()

    def identity(self, who: str, role: str, tenant: str = "tenant", zone: ZoneInfo = NY):
        return SimpleNamespace(user_id=self.ids[f"{who}_user"], tenant_id=self.ids[tenant], role=role, clinic_tz=zone)

    async def fetch(self, sql: str, *args):
        conn = await self.db.connect()
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    async def test_each_request_carries_its_own_clinics_zone(self):
        def request_for(who: str, tenant: str, role: str):
            return SimpleNamespace(state=SimpleNamespace(tenant_id=self.ids[tenant], user_id=self.ids[f"{who}_user"], role=role))

        async with self.sessions() as s:
            east = await get_current_identity(request_for("admin", "tenant", "ADMIN"), db=s)
            west = await get_current_identity(request_for("la_doctor", "la_tenant", "DOCTOR"), db=s)
        self.assertEqual(east.clinic_tz.key, "America/New_York")
        self.assertEqual(west.clinic_tz.key, "America/Los_Angeles")

    async def test_default_slots_are_office_hours_in_the_clinics_zone(self):
        identity = self.identity("la_doctor", "DOCTOR", tenant="la_tenant", zone=LA)
        async with self.sessions() as s:
            slots = await list_all_availability(doctor_id=self.ids["la_doctor"], days=8, identity=identity, db=s)
        hours = {datetime.fromisoformat(row["slot_time"]).astimezone(LA).hour for row in slots}
        self.assertTrue(slots)
        self.assertEqual(hours, set(range(8, 24)))

    async def test_login_tells_the_browser_the_clinic_zone(self):
        async with self.sessions() as s:
            reply = await login(request=LoginRequest(email="west.doc@example.test", password="WestDoc1234"), http_request=FAKE_HTTP, db=s)
        self.assertEqual(reply["clinic_timezone"], "America/Los_Angeles")

    async def test_changing_the_zone_keeps_local_hours_and_booked_times(self):
        day = timeutils.clinic_today(NY) + timedelta(days=2)
        async with self.sessions() as s:
            await ensure_default_slots(s, (await s.execute(select(Doctor).where(Doctor.id == self.ids["doctor"]))).scalar_one(), NY)
        booked_at = at(day, 14, NY)
        payload = CreateAppointmentRequest(doctor_id=self.ids["doctor"], slot=booked_at.isoformat(), reason="Regular checkup")
        async with self.sessions() as s:
            appointment_id = (await create_appointment(payload=payload, identity=self.identity("patient1", "PATIENT"), db=s))["id"]
        await self.fetch(
            "UPDATE doctor_availability SET status = 'BLOCKED', block_reason = 'Lunch' WHERE doctor_id = $1 AND slot_time = $2",
            self.ids["doctor"], at(day, 10, NY),
        )

        async with self.sessions() as s:
            reply = await update_current_tenant(
                payload=UpdateTenantRequest(timezone="America/Los_Angeles"), identity=self.identity("admin", "ADMIN"), db=s
            )
        self.assertEqual(reply["timezone"], "America/Los_Angeles")
        self.assertGreater(reply["slots_moved"], 0)

        rows = await self.fetch("SELECT slot_time, status, block_reason FROM doctor_availability WHERE doctor_id = $1", self.ids["doctor"])
        on_day = {r["slot_time"]: r for r in rows if r["slot_time"].astimezone(LA).date() == day}
        # Open slots are 8 AM-11 PM Pacific now; the blocked one moved with its reason
        self.assertEqual(on_day[at(day, 10, LA)]["status"], "BLOCKED")
        self.assertEqual(on_day[at(day, 10, LA)]["block_reason"], "Lunch")
        self.assertEqual({t.astimezone(LA).hour for t, r in on_day.items() if r["status"] == "AVAILABLE"}, set(range(8, 24)) - {10, 11})
        # The booked visit keeps its exact time (2 PM Eastern = 11 AM Pacific) and its slot
        self.assertEqual(on_day[booked_at]["status"], "BOOKED")
        appointment = (await self.fetch("SELECT appointment_time FROM appointments WHERE id = $1", appointment_id))[0]
        self.assertEqual(appointment["appointment_time"], booked_at)
        self.assertEqual(len(rows), len({r["slot_time"] for r in rows}))  # no duplicates

        audit = await self.fetch("SELECT old_data, new_data FROM audit_logs WHERE table_name = 'tenants'")
        self.assertEqual(len(audit), 1)
        async with self.sessions() as s:
            info = await get_current_tenant(identity=self.identity("admin", "ADMIN"), db=s)
        self.assertEqual(info["timezone"], "America/Los_Angeles")

    async def test_changing_the_zone_keeps_range_blocks_and_flagged_hours_blocked(self):
        day = timeutils.clinic_today(NY) + timedelta(days=2)
        async with self.sessions() as s:
            await ensure_default_slots(s, (await s.execute(select(Doctor).where(Doctor.id == self.ids["doctor"]))).scalar_one(), NY)
        flagged_at, plain_at = at(day, 14, NY), at(day, 21, NY)
        for when, who in ((flagged_at, "patient1"), (plain_at, "patient2")):
            payload = CreateAppointmentRequest(doctor_id=self.ids["doctor"], slot=when.isoformat(), reason="Regular checkup")
            async with self.sessions() as s:
                await create_appointment(payload=payload, identity=self.identity(who, "PATIENT"), db=s)
        async with self.sessions() as s:  # block 9 AM-5 PM Eastern over the 2 PM appointment
            doctor = (await s.execute(select(Doctor).where(Doctor.id == self.ids["doctor"]))).scalar_one()
            plan = await plan_range_change(s, doctor, NY, at(day, 9, NY), at(day, 17, NY), "block")
            block = await apply_block(
                s, doctor, NY, at(day, 9, NY), at(day, 17, NY), category="CONFERENCE", note=None, fingerprint=plan.fingerprint, actor=None
            )
            await s.commit()

        async with self.sessions() as s:
            await update_current_tenant(payload=UpdateTenantRequest(timezone="America/Los_Angeles"), identity=self.identity("admin", "ADMIN"), db=s)

        rows = await self.fetch("SELECT slot_time, status, block_id, block_reason FROM doctor_availability WHERE doctor_id = $1", self.ids["doctor"])
        on_day = {r["slot_time"].astimezone(LA).hour: r for r in rows if r["slot_time"].astimezone(LA).date() == day}
        # 9 AM-5 PM Pacific is still blocked under the same block; the flagged visit (11 AM Pacific) stays booked
        for hour in range(9, 17):
            self.assertEqual(str(on_day[hour]["block_id"]), block["block_id"], hour)
            self.assertEqual(on_day[hour]["status"], "BOOKED" if hour == 11 else "BLOCKED", hour)
        self.assertEqual(on_day[14]["block_reason"], "Conference")  # the flagged slot's reopened hour
        # The unflagged booked slot's hour (9 PM) reopens as AVAILABLE, as before
        self.assertEqual((on_day[21]["status"], on_day[21]["block_id"]), ("AVAILABLE", None))
        moved = await self.fetch("SELECT start_time, end_time FROM schedule_blocks WHERE id = $1", block["block_id"])
        self.assertEqual((moved[0]["start_time"], moved[0]["end_time"]), (at(day, 9, LA), at(day, 17, LA)))

    async def test_unknown_zones_are_rejected(self):
        for zone in ("Mars/Olympus_Mons", "EST-ish", " "):
            with self.subTest(zone=zone):
                async with self.sessions() as s:
                    with self.assertRaises(HTTPException) as ctx:
                        await update_current_tenant(payload=UpdateTenantRequest(timezone=zone), identity=self.identity("admin", "ADMIN"), db=s)
                self.assertEqual(ctx.exception.status_code, 422)
        rows = await self.fetch("SELECT timezone FROM tenants WHERE id = $1", self.ids["tenant"])
        self.assertEqual(rows[0]["timezone"], "America/New_York")

    async def test_another_clinic_is_never_changed(self):
        async with self.sessions() as s:
            await update_current_tenant(payload=UpdateTenantRequest(timezone="Europe/London"), identity=self.identity("admin", "ADMIN"), db=s)
        rows = await self.fetch("SELECT id, timezone FROM tenants")
        zones = {str(r["id"]): r["timezone"] for r in rows}
        self.assertEqual(zones[self.ids["tenant"]], "Europe/London")
        self.assertEqual(zones[self.ids["la_tenant"]], "America/Los_Angeles")

    async def test_first_admin_setup_sets_the_clinic_zone(self):
        await self.fetch("UPDATE users SET is_active = false WHERE role = 'ADMIN'")
        await self.fetch("UPDATE tenants SET domain = 'east.test' WHERE id = $1", self.ids["tenant"])
        payload = AdminRegisterRequest(full_name="First Admin", email="first@example.test", password="Bootstrap123", timezone="America/Denver")
        async with self.sessions() as s:
            await register_admin(payload=payload, http_request=http_from("east.test"), db=s)
        rows = await self.fetch("SELECT timezone FROM tenants WHERE id = $1", self.ids["tenant"])
        self.assertEqual(rows[0]["timezone"], "America/Denver")


if __name__ == "__main__":
    unittest.main()
