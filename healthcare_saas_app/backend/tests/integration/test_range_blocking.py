"""Range block/unblock of a doctor's slots (migration 010) against a real PostgreSQL database.

- migration 010 is idempotent and its rollback restores the previous schema
- the release rule: a freed slot stays BLOCKED while a range block wants the hour (trigger and reschedule)
- preview counts, the fingerprint check (409), filling empty days, overlapping and repeated blocks
- unblock (whole, partial, after a patient was moved out) never touches appointments or re-creates deleted hours
- block records and their derived state, single-slot changes inside a block, the grid fields
- the support staff "Needs reschedule" queue
- concurrency (booking racing a block, two overlapping blocks) and a 180-day block's speed

Skipped unless HC_TEST_PG_ADMIN_URL is set (see _pg.py).
"""

import asyncio
import json
import os
import time
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.api.routes.appointments import (
    CreateAppointmentRequest,
    RescheduleAppointmentRequest,
    create_appointment,
    delete_appointment,
    list_all_appointments,
    reschedule_appointment_route,
)
from backend.app.api.routes.doctor import (
    BlockRangeRequest,
    DeleteAvailabilityRequest,
    RangeRequest,
    UpsertDoctorAvailabilityRequest,
    block_range,
    delete_availability,
    list_all_availability,
    list_block_ranges,
    preview_block_range,
    preview_unblock_range,
    unblock_range,
    upsert_doctor_availability,
)
from backend.app.api.routes.support import reschedule_queue
from backend.app.core import timeutils
from backend.app.models import Doctor
from backend.app.services.availability_service import (
    SCHEDULE_CHANGED,
    apply_block,
    ensure_default_slots,
    plan_range_change,
)
from backend.tests.integration._pg import CLINIC_TZ, TempDatabase, require_pg, seed_clinic

NY = ZoneInfo(CLINIC_TZ)
SNAPSHOT_SQL = Path(__file__).resolve().parents[4] / "aws_env_spin_up" / "scripts" / "schema_snapshot.sql"
SCHEMA_KEYS = ["columns", "enums", "indexes", "constraints", "triggers", "functions", "rls_tables", "policies"]


def local(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=NY).astimezone(UTC)


class Migration010Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        require_pg()
        self.db = await TempDatabase().create()
        for name in (
            "003_convert_timestamps_to_timestamptz.sql",
            "005_add_support_staff_role.sql",
            "007_row_level_security.sql",
            "008_add_tenant_timezone.sql",
            "009_rate_limits_and_gender_values.sql",
        ):
            await self.db.run_migration(name)

    async def asyncTearDown(self):
        await self.db.drop()

    async def snapshot(self) -> dict:
        conn = await self.db.connect()
        try:
            return json.loads(await conn.fetchval(SNAPSHOT_SQL.read_text(encoding="utf-8")))
        finally:
            await conn.close()

    async def test_applies_twice_and_rolls_back_to_the_previous_schema(self):
        before = await self.snapshot()
        self.assertNotIn("010_schedule_blocks", before["migrations_applied"])

        await self.db.run_migration("010_schedule_blocks.sql")
        once = await self.snapshot()
        await self.db.run_migration("010_schedule_blocks.sql")  # idempotent
        twice = await self.snapshot()
        for key in SCHEMA_KEYS:
            self.assertEqual(set(once[key] or []), set(twice[key] or []), key)
        self.assertIn("010_schedule_blocks", twice["migrations_applied"])
        self.assertIn("schedule_blocks", twice["rls_tables"])
        self.assertTrue(any("doctor_availability.block_id uuid null" in c for c in twice["columns"]))
        self.assertTrue(any("audit_schedule_blocks" in t for t in twice["triggers"]))

        await self.db.run_migration("010_schedule_blocks_rollback.sql")
        after = await self.snapshot()
        for key in SCHEMA_KEYS:
            self.assertEqual(set(before[key] or []), set(after[key] or []), key)
        self.assertNotIn("010_schedule_blocks", after["migrations_applied"])


class RangeBlockingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        require_pg()
        self.db = await TempDatabase().create(migrate=True)
        conn = await self.db.connect()
        try:
            self.ids = await seed_clinic(conn)
            tenant = self.ids["tenant"]
            self.ids["staff_user"] = str(await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'staff@example.test', 'x', 'SUPPORT_STAFF') RETURNING id",
                tenant,
            ))
            await conn.execute("INSERT INTO support_staff (tenant_id, user_id, full_name) VALUES ($1, $2, 'Sam Support')", tenant, self.ids["staff_user"])
            self.ids["doctor2_user"] = str(await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'doc2@example.test', 'x', 'DOCTOR') RETURNING id",
                tenant,
            ))
            self.ids["doctor2"] = str(await conn.fetchval(
                "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Two') RETURNING id", tenant, self.ids["doctor2_user"]
            ))
            await conn.execute("UPDATE patients SET phone = '555-0101' WHERE id = $1", self.ids["patient1"])
        finally:
            await conn.close()
        self.engine = create_async_engine(self.db.sqlalchemy_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
        self.today = timeutils.clinic_today(NY)
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s), NY)

    async def asyncTearDown(self):
        await self.engine.dispose()
        await self.db.drop()

    # --- helpers ----------------------------------------------------------------------------------

    def identity(self, who: str, role: str):
        return SimpleNamespace(user_id=self.ids[f"{who}_user"], tenant_id=self.ids["tenant"], role=role, clinic_tz=NY)

    def doctor_identity(self):
        return self.identity("doctor", "DOCTOR")

    async def doctor(self, session: AsyncSession, doctor_id: str | None = None) -> Doctor:
        return (await session.execute(select(Doctor).where(Doctor.id == (doctor_id or self.ids["doctor"])))).scalar_one()

    async def fetch(self, sql: str, *args):
        conn = await self.db.connect()
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    async def slots(self, day: date | None = None, doctor_id: str | None = None) -> dict:
        rows = await self.fetch(
            "SELECT slot_time, status, block_id, block_reason FROM doctor_availability WHERE doctor_id = $1 ORDER BY slot_time",
            doctor_id or self.ids["doctor"],
        )
        return {r["slot_time"]: r for r in rows if day is None or r["slot_time"].astimezone(NY).date() == day}

    def block_payload(self, start, end, fingerprint=None, category="VACATION", note=None):
        return BlockRangeRequest(start=start.isoformat(), end=end.isoformat(), reason_category=category, reason_note=note, fingerprint=fingerprint)

    async def preview_block(self, start, end, identity=None, doctor_id=None, **kwargs) -> dict:
        async with self.sessions() as s:
            return await preview_block_range(
                doctor_id=doctor_id or self.ids["doctor"], payload=self.block_payload(start, end, **kwargs), identity=identity or self.doctor_identity(), db=s
            )

    async def apply_block(self, start, end, fingerprint, identity=None, doctor_id=None, **kwargs) -> dict:
        async with self.sessions() as s:
            return await block_range(
                doctor_id=doctor_id or self.ids["doctor"],
                payload=self.block_payload(start, end, fingerprint=fingerprint, **kwargs),
                identity=identity or self.doctor_identity(),
                db=s,
            )

    async def block(self, start, end, identity=None, doctor_id=None, **kwargs) -> tuple[dict, dict]:
        preview = await self.preview_block(start, end, identity=identity, doctor_id=doctor_id, **kwargs)
        result = await self.apply_block(start, end, preview["fingerprint"], identity=identity, doctor_id=doctor_id, **kwargs)
        return preview, result

    async def unblock(self, start, end, identity=None) -> tuple[dict, dict]:
        identity = identity or self.doctor_identity()
        async with self.sessions() as s:
            preview = await preview_unblock_range(
                doctor_id=self.ids["doctor"], payload=RangeRequest(start=start.isoformat(), end=end.isoformat()), identity=identity, db=s
            )
        async with self.sessions() as s:
            result = await unblock_range(
                doctor_id=self.ids["doctor"],
                payload=RangeRequest(start=start.isoformat(), end=end.isoformat(), fingerprint=preview["fingerprint"]),
                identity=identity,
                db=s,
            )
        return preview, result

    async def book(self, who: str, slot: datetime, doctor_id: str | None = None) -> str:
        payload = CreateAppointmentRequest(doctor_id=doctor_id or self.ids["doctor"], slot=slot.isoformat(), reason="Check-up")
        async with self.sessions() as s:
            return (await create_appointment(payload=payload, identity=self.identity(who, "PATIENT"), db=s))["id"]

    async def cancel(self, appointment_id: str, who: str = "patient1") -> None:
        async with self.sessions() as s:
            await delete_appointment(appointment_id=appointment_id, identity=self.identity(who, "PATIENT"), db=s)

    async def reschedule(self, appointment_id: str, slot: datetime) -> dict:
        async with self.sessions() as s:
            return await reschedule_appointment_route(
                appointment_id=appointment_id,
                payload=RescheduleAppointmentRequest(slot=slot.isoformat()),
                identity=self.identity("staff", "SUPPORT_STAFF"),
                db=s,
            )

    async def queue(self, doctor_id: str | None = None) -> list[dict]:
        async with self.sessions() as s:
            return await reschedule_queue(doctor_id=doctor_id, identity=self.identity("staff", "SUPPORT_STAFF"), db=s)

    async def blocks(self) -> list[dict]:
        async with self.sessions() as s:
            return await list_block_ranges(doctor_id=self.ids["doctor"], identity=self.doctor_identity(), db=s)

    async def assert_http(self, status_code: int, detail: str | None, awaitable):
        with self.assertRaises(HTTPException) as ctx:
            await awaitable
        self.assertEqual(ctx.exception.status_code, status_code)
        if detail is not None:
            self.assertEqual(ctx.exception.detail, detail)

    # --- release rule -----------------------------------------------------------------------------

    async def test_cancelling_a_flagged_appointment_leaves_the_hour_blocked(self):
        day = self.today + timedelta(days=2)
        flagged = await self.book("patient1", local(day, 10))
        plain = await self.book("patient1", local(day, 15))
        await self.block(local(day, 9), local(day, 12), note="Family trip")

        await self.cancel(flagged)
        await self.cancel(plain)
        rows = await self.slots(day)
        self.assertEqual(rows[local(day, 10)]["status"], "BLOCKED")
        self.assertEqual(rows[local(day, 10)]["block_reason"], "Vacation: Family trip")
        self.assertIsNotNone(rows[local(day, 10)]["block_id"])
        self.assertEqual(rows[local(day, 15)]["status"], "AVAILABLE")  # outside any block, as before

        # Nobody can grab the freed blocked hour
        await self.assert_http(409, "Requested slot is not available.", self.book("patient2", local(day, 10)))

    async def test_trigger_releases_by_the_rule_on_update_and_delete(self):
        day = self.today + timedelta(days=3)
        first = await self.book("patient1", local(day, 9))
        second = await self.book("patient2", local(day, 11))
        rows = await self.slots(day)
        self.assertIsNone(rows[local(day, 9)]["block_id"])  # booking an unblocked slot leaves block_id empty

        await self.block(local(day, 8), local(day, 12))
        await self.fetch("UPDATE appointments SET status = 'CANCELLED' WHERE id = $1", first)
        await self.fetch("DELETE FROM appointments WHERE id = $1", second)
        rows = await self.slots(day)
        self.assertEqual((rows[local(day, 9)]["status"], rows[local(day, 11)]["status"]), ("BLOCKED", "BLOCKED"))

    async def test_touching_a_cancelled_appointment_does_not_free_a_rebooked_slot(self):
        day = self.today + timedelta(days=2)
        old = await self.book("patient1", local(day, 13))
        await self.cancel(old)
        await self.book("patient2", local(day, 13))
        await self.fetch("UPDATE appointments SET notes = 'edited' WHERE id = $1", old)
        await self.fetch("DELETE FROM appointments WHERE id = $1", old)
        self.assertEqual((await self.slots(day))[local(day, 13)]["status"], "BOOKED")

    async def test_rescheduling_a_flagged_appointment_keeps_the_old_hour_blocked(self):
        day = self.today + timedelta(days=2)
        appointment = await self.book("patient1", local(day, 10))
        await self.block(local(day, 9), local(day, 12))
        self.assertEqual([item["id"] for item in await self.queue()], [appointment])

        # Not into another hour of the same block
        await self.assert_http(409, "Requested slot is not available.", self.reschedule(appointment, local(day, 11)))

        await self.reschedule(appointment, local(day, 16))
        rows = await self.slots(day)
        self.assertEqual(rows[local(day, 10)]["status"], "BLOCKED")
        self.assertEqual(rows[local(day, 16)]["status"], "BOOKED")
        self.assertIsNone(rows[local(day, 16)]["block_id"])
        self.assertEqual(await self.queue(), [])

    # --- input rules ------------------------------------------------------------------------------

    async def test_range_input_errors(self):
        day = self.today + timedelta(days=2)
        now = timeutils.utc_now()
        cases = [
            (local(day, 12), local(day, 12), {}, 422, "End must be after start."),
            (local(day, 12), local(day, 9), {}, 422, "End must be after start."),
            (now - timedelta(days=2), now - timedelta(hours=1), {}, 400, "Range is entirely in the past."),
            (local(day, 9), now + timedelta(days=181), {}, 400, "Cannot change slots beyond 180 days."),
            (local(day, 9), local(day, 12), {"category": "OTHER"}, 422, "Please describe the reason."),
            (local(day, 9), local(day, 12), {"category": "OTHER", "note": "   "}, 422, "Please describe the reason."),
            (local(day, 9), local(day, 12), {"category": "HOLIDAY"}, 422, "Please choose a reason."),
        ]
        before = await self.slots()
        for start, end, extra, code, detail in cases:
            with self.subTest(detail=detail, extra=extra):
                await self.assert_http(code, detail, self.preview_block(start, end, **extra))
                await self.assert_http(code, detail, self.apply_block(start, end, "x", **extra))
        self.assertEqual(await self.slots(), before)
        with self.assertRaises(ValueError):  # no category at all: request validation (422)
            BlockRangeRequest(start=local(day, 9).isoformat(), end=local(day, 12).isoformat())

    async def test_a_block_five_months_ahead_is_allowed(self):
        start = local(self.today + timedelta(days=148), 9)
        preview, result = await self.block(start, start + timedelta(hours=3), category="CONFERENCE")
        self.assertEqual((preview["slots_to_create"], preview["created_blocked"]), (16, 3))
        self.assertIsNotNone(result["block_id"])

    async def test_half_open_range_and_past_start_is_clamped(self):
        day = self.today + timedelta(days=2)
        await self.block(local(day, 9), local(day, 12))
        rows = await self.slots(day)
        self.assertEqual([t.astimezone(NY).hour for t, r in rows.items() if r["status"] == "BLOCKED"], [9, 10, 11])

        # At 10:20 AM, a block from 8 AM to 1 PM today affects only 11 AM and 12 PM
        now = local(day, 10) + timedelta(minutes=20)
        async with self.sessions() as s:
            plan = await plan_range_change(s, await self.doctor(s), NY, local(day, 8), local(day, 13), "block", now=now)
        self.assertEqual(plan.start, local(day, 11))
        self.assertEqual(plan.counts()["to_block"], 1)  # 12 PM (11 AM already blocked)
        self.assertEqual(plan.counts()["already_blocked"], 1)

    async def test_multi_day_range_covers_office_hours_only(self):
        day = self.today + timedelta(days=2)
        await self.block(local(day, 14), local(day + timedelta(days=2), 10))
        blocked = sorted(t for r in [await self.slots()] for t, row in r.items() if row["status"] == "BLOCKED")
        expected = (
            [local(day, h) for h in range(14, 24)]
            + [local(day + timedelta(days=1), h) for h in range(8, 24)]
            + [local(day + timedelta(days=2), h) for h in (8, 9)]
        )
        self.assertEqual(blocked, expected)

    # --- preview ----------------------------------------------------------------------------------

    async def test_preview_counts_booked_and_blocked_and_changes_nothing(self):
        day = self.today + timedelta(days=3)
        appointments = [await self.book(who, local(day, h)) for who, h in (("patient1", 9), ("patient2", 12), ("patient1", 18))]
        for hour in (14, 15):
            async with self.sessions() as s:
                await upsert_doctor_availability(
                    payload=UpsertDoctorAvailabilityRequest(slot=local(day, hour).isoformat(), is_available=False, block_reason="Lunch"),
                    identity=self.doctor_identity(),
                    db=s,
                )
        before = await self.slots(day)
        preview = await self.preview_block(local(day, 8), local(day + timedelta(days=1), 0))
        self.assertEqual(
            (preview["to_block"], preview["already_blocked"], preview["to_flag"], preview["slots_to_create"]), (11, 2, 3, 0)
        )
        self.assertEqual([a["appointment_id"] for a in preview["appointments"]], appointments)
        self.assertEqual(preview["appointments"][0]["patient_name"], "Patient 1")
        self.assertEqual(await self.slots(day), before)

    async def test_preview_over_days_with_no_slots(self):
        day = self.today + timedelta(days=20)
        preview = await self.preview_block(local(day, 0), local(day + timedelta(days=2), 0))
        self.assertEqual((preview["slots_to_create"], preview["created_blocked"], preview["days_to_fill"]), (32, 32, 2))
        preview = await self.preview_block(local(day, 14), local(day + timedelta(days=1), 10))
        self.assertEqual((preview["slots_to_create"], preview["created_blocked"]), (32, 12))
        self.assertEqual(await self.slots(day), {})

    # --- fill missing days ------------------------------------------------------------------------

    async def test_partial_day_block_on_an_empty_day_fills_the_whole_day(self):
        day = self.today + timedelta(days=20)
        await self.block(local(day, 14), local(day, 16))
        rows = await self.slots(day)
        self.assertEqual(len(rows), 16)
        blocked = [t.astimezone(NY).hour for t, r in rows.items() if r["status"] == "BLOCKED"]
        self.assertEqual(blocked, [14, 15])
        self.assertEqual(sum(1 for r in rows.values() if r["status"] == "AVAILABLE"), 14)

    async def test_block_recreates_a_deleted_hour_but_unblock_does_not(self):
        day = self.today + timedelta(days=3)
        async with self.sessions() as s:
            await delete_availability(
                doctor_id=self.ids["doctor"], payload=DeleteAvailabilityRequest(slot_time=local(day, 9).isoformat()), identity=self.doctor_identity(), db=s
            )
        await self.unblock(local(day, 8), local(day, 11))
        self.assertNotIn(local(day, 9), await self.slots(day))

        await self.block(local(day, 8), local(day, 11))
        rows = await self.slots(day)
        self.assertEqual([rows[local(day, h)]["status"] for h in (8, 9, 10)], ["BLOCKED"] * 3)

    # --- applying a block -------------------------------------------------------------------------

    async def test_block_over_booked_appointments_flags_them_and_audits_ids_only(self):
        day = self.today + timedelta(days=4)
        booked = [await self.book(who, local(day, h)) for who, h in (("patient1", 9), ("patient2", 10), ("patient1", 20))]
        before = await self.fetch("SELECT id, appointment_time, status, notes FROM appointments ORDER BY id")

        _, result = await self.block(local(day, 8), local(day + timedelta(days=1), 0), category="SICK")
        self.assertEqual((result["to_block"], result["to_flag"], result["needs_reschedule"]), (13, 3, 3))
        rows = await self.slots(day)
        self.assertTrue(all(r["status"] == "BLOCKED" for t, r in rows.items() if t.astimezone(NY).hour not in (9, 10, 20)))
        for hour in (9, 10, 20):
            self.assertEqual((rows[local(day, hour)]["status"], str(rows[local(day, hour)]["block_id"])), ("BOOKED", result["block_id"]))
        self.assertEqual(await self.fetch("SELECT id, appointment_time, status, notes FROM appointments ORDER BY id"), before)
        self.assertEqual({item["id"] for item in await self.queue()}, set(booked))

        block_entries = await self.fetch("SELECT record_id, new_data FROM audit_logs WHERE table_name = 'schedule_blocks' AND new_data ? 'slot_ids'")
        self.assertEqual(len(block_entries), 1)
        self.assertEqual(str(block_entries[0]["record_id"]), result["block_id"])
        flag_entries = await self.fetch("SELECT record_id, new_data FROM audit_logs WHERE table_name = 'appointments' AND new_data ? 'needs_reschedule'")
        self.assertEqual({str(r["record_id"]) for r in flag_entries}, set(booked))
        for entry in block_entries + flag_entries:
            self.assertNotIn("Patient", entry["new_data"])

    async def test_overlapping_and_repeated_blocks(self):
        d3, d4, d6 = (self.today + timedelta(days=n) for n in (3, 4, 6))
        _, first = await self.block(local(d3, 0), local(d3 + timedelta(days=3), 0), category="VACATION")
        preview, second = await self.block(local(d4, 0), local(d6 + timedelta(days=1), 0), category="CONFERENCE")
        self.assertEqual(preview["already_blocked"], 32)  # Nov 4-5 style overlap counted as already blocked
        self.assertEqual(preview["to_block"], 16)
        rows = await self.slots()
        self.assertEqual({str(rows[local(d4, h)]["block_id"]) for h in range(8, 24)}, {first["block_id"]})
        self.assertEqual(rows[local(d4, 9)]["block_reason"], "Vacation")
        self.assertEqual({str(rows[local(d6, h)]["block_id"]) for h in range(8, 24)}, {second["block_id"]})

        _, again = await self.block(local(d4, 0), local(d6 + timedelta(days=1), 0), category="CONFERENCE")
        self.assertIsNone(again["block_id"])
        self.assertEqual((again["to_block"], again["already_blocked"]), (0, 48))
        self.assertEqual(len(await self.fetch("SELECT id FROM schedule_blocks")), 2)

    async def test_support_staff_blocks_on_a_doctors_behalf(self):
        day = self.today + timedelta(days=2)
        _, result = await self.block(local(day, 9), local(day, 11), identity=self.identity("staff", "SUPPORT_STAFF"))
        creator = await self.fetch("SELECT created_by FROM schedule_blocks WHERE id = $1", result["block_id"])
        self.assertEqual(str(creator[0]["created_by"]), self.ids["staff_user"])

    async def test_who_may_change_a_range(self):
        day = self.today + timedelta(days=2)
        start, end = local(day, 9), local(day, 11)
        await self.assert_http(
            403, "Not allowed to change another doctor's availability.", self.preview_block(start, end, doctor_id=self.ids["doctor2"])
        )
        await self.assert_http(403, None, self.preview_block(start, end, identity=self.identity("patient1", "PATIENT")))
        await self.assert_http(404, None, self.preview_block(start, end, identity=self.identity("staff", "SUPPORT_STAFF"), doctor_id="nope"))
        preview = await self.preview_block(start, end, identity=self.identity("staff", "SUPPORT_STAFF"), doctor_id=self.ids["doctor2"])
        self.assertEqual(preview["slots_to_create"], 16)

    # --- fingerprint ------------------------------------------------------------------------------

    async def test_a_booking_between_preview_and_confirm_is_refused_with_409(self):
        day = self.today + timedelta(days=3)
        preview = await self.preview_block(local(day, 8), local(day, 12))
        appointment = await self.book("patient1", local(day, 10))
        before = await self.slots(day)
        await self.assert_http(409, SCHEDULE_CHANGED, self.apply_block(local(day, 8), local(day, 12), preview["fingerprint"]))
        self.assertEqual(await self.slots(day), before)
        await self.assert_http(409, SCHEDULE_CHANGED, self.apply_block(local(day, 8), local(day, 12), None))

        again = await self.preview_block(local(day, 8), local(day, 12))
        self.assertEqual([a["appointment_id"] for a in again["appointments"]], [appointment])
        result = await self.apply_block(local(day, 8), local(day, 12), again["fingerprint"])
        self.assertEqual((result["to_block"], result["to_flag"]), (3, 1))

    # --- unblock ----------------------------------------------------------------------------------

    async def test_unblock_with_appointments_keeps_them_and_clears_the_flags(self):
        day = self.today + timedelta(days=4)
        booked = [await self.book("patient1", local(day, h)) for h in (9, 10, 11)]
        _, block = await self.block(local(day, 8), local(day, 13))
        before = await self.fetch("SELECT id, appointment_time, status FROM appointments ORDER BY id")
        preview, result = await self.unblock(local(day, 8), local(day, 13))
        self.assertEqual((preview["to_open"], preview["to_unflag"]), (2, 3))
        self.assertEqual(result["released_block_ids"], [block["block_id"]])
        rows = await self.slots(day)
        self.assertEqual([rows[local(day, h)]["status"] for h in range(8, 13)], ["AVAILABLE", "BOOKED", "BOOKED", "BOOKED", "AVAILABLE"])
        self.assertTrue(all(r["block_id"] is None and r["block_reason"] is None for r in rows.values()))
        self.assertEqual(await self.fetch("SELECT id, appointment_time, status FROM appointments ORDER BY id"), before)
        self.assertEqual(await self.queue(), [])
        unflags = await self.fetch("SELECT record_id FROM audit_logs WHERE table_name = 'appointments' AND new_data @> '{\"needs_reschedule\": false}'")
        self.assertEqual({str(r["record_id"]) for r in unflags}, set(booked))

    async def test_partial_unblock_leaves_the_rest_of_the_block(self):
        first = self.today + timedelta(days=2)
        _, block = await self.block(local(first, 0), local(first + timedelta(days=5), 0))
        middle = first + timedelta(days=2)
        await self.unblock(local(middle, 10), local(middle, 14))
        rows = await self.slots()
        opened = sorted(t for t, r in rows.items() if r["status"] == "AVAILABLE" and first <= t.astimezone(NY).date() < first + timedelta(days=5))
        self.assertEqual(opened, [local(middle, h) for h in range(10, 14)])
        states = {b["id"]: b for b in await self.blocks()}
        self.assertEqual(states[block["block_id"]]["state"], "PARTIALLY_RELEASED")
        self.assertEqual(states[block["block_id"]]["blocked_hours"], 5 * 16 - 4)

    async def test_unblock_after_a_patient_was_moved_out(self):
        day = self.today + timedelta(days=2)
        appointment = await self.book("patient1", local(day, 10))
        await self.block(local(day, 10), local(day, 11))
        await self.reschedule(appointment, local(day, 17))
        self.assertEqual((await self.slots(day))[local(day, 10)]["status"], "BLOCKED")
        await self.unblock(local(day, 10), local(day, 11))
        self.assertEqual((await self.slots(day))[local(day, 10)]["status"], "AVAILABLE")

    async def test_unblock_fills_empty_days_with_open_slots(self):
        day = self.today + timedelta(days=25)
        preview, _ = await self.unblock(local(day, 9), local(day, 12))
        self.assertEqual((preview["days_to_fill"], preview["slots_to_create"]), (1, 16))
        self.assertEqual({r["status"] for r in (await self.slots(day)).values()}, {"AVAILABLE"})

    # --- block records ----------------------------------------------------------------------------

    async def test_block_list_states_and_unblock_all(self):
        day = self.today + timedelta(days=3)
        _, block = await self.block(local(day, 9), local(day, 17), note="Board exam")
        [listed] = await self.blocks()
        self.assertEqual((listed["state"], listed["blocked_hours"], listed["reason_label"], listed["reason_note"]), ("ACTIVE", 8, "Vacation", "Board exam"))

        # Unblocking one hour from the grid clears its block_id and leaves the block partially released
        async with self.sessions() as s:
            await upsert_doctor_availability(
                payload=UpsertDoctorAvailabilityRequest(slot=local(day, 12).isoformat(), is_available=True), identity=self.doctor_identity(), db=s
            )
        self.assertIsNone((await self.slots(day))[local(day, 12)]["block_id"])
        [listed] = await self.blocks()
        self.assertEqual((listed["state"], listed["blocked_hours"], listed["opened_hours"]), ("PARTIALLY_RELEASED", 7, 1))

        # "Unblock all" previews the block's own range
        await self.unblock(datetime.fromisoformat(listed["start"]), datetime.fromisoformat(listed["end"]))
        [listed] = await self.blocks()
        self.assertEqual(listed["state"], "RELEASED")
        released = await self.fetch("SELECT released_at, released_by FROM schedule_blocks WHERE id = $1", block["block_id"])
        self.assertIsNotNone(released[0]["released_at"])
        self.assertEqual(str(released[0]["released_by"]), self.ids["doctor_user"])

    async def test_single_slot_changes_keep_their_rules_inside_a_block(self):
        day = self.today + timedelta(days=3)
        await self.book("patient1", local(day, 10))
        await self.block(local(day, 9), local(day, 12))
        for available in (True, False):
            with self.subTest(available=available):
                payload = UpsertDoctorAvailabilityRequest(slot=local(day, 10).isoformat(), is_available=available)
                async with self.sessions() as s:
                    await self.assert_http(400, "Cannot modify a patient-booked slot.", upsert_doctor_availability(payload=payload, identity=self.doctor_identity(), db=s))
        payload = UpsertDoctorAvailabilityRequest(slot=local(self.today + timedelta(days=40), 10).isoformat(), is_available=False)
        async with self.sessions() as s:
            await self.assert_http(400, "Cannot update slots beyond 30 days.", upsert_doctor_availability(payload=payload, identity=self.doctor_identity(), db=s))

    # --- what each role sees ----------------------------------------------------------------------

    async def test_grid_shows_flags_to_staff_and_nothing_to_patients(self):
        day = self.today + timedelta(days=2)
        appointment = await self.book("patient1", local(day, 10))
        await self.block(local(day, 9), local(day, 12), category="PERSONAL")

        async with self.sessions() as s:
            staff_view = await list_all_availability(doctor_id=self.ids["doctor"], days=7, identity=self.doctor_identity(), db=s)
        by_time = {datetime.fromisoformat(r["slot_time"]): r for r in staff_view}
        self.assertEqual((by_time[local(day, 10)]["status"], by_time[local(day, 10)]["needs_reschedule"]), ("BOOKED", True))
        self.assertEqual(by_time[local(day, 9)]["block_reason"], "Personal")
        self.assertFalse(by_time[local(day, 13)]["needs_reschedule"])

        async with self.sessions() as s:
            patient_view = await list_all_availability(doctor_id=self.ids["doctor"], days=7, identity=self.identity("patient2", "PATIENT"), db=s)
        self.assertTrue(all(set(r) == {"slot_time", "status"} for r in patient_view))
        async with self.sessions() as s:
            mine = await list_all_appointments(include_cancelled=False, identity=self.identity("patient1", "PATIENT"), db=s)
        text = json.dumps(mine, default=str)
        self.assertIn(appointment, text)
        self.assertNotIn("Personal", text)
        self.assertNotIn("reschedule", text.lower())

    # --- the Needs Reschedule queue ---------------------------------------------------------------

    async def test_queue_is_sorted_urgent_first_and_filterable_by_doctor(self):
        now = timeutils.utc_now()
        soon = (now + timedelta(hours=6)).replace(minute=0, second=0, microsecond=0)
        later_day = self.today + timedelta(days=5)
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s, self.ids["doctor2"]), NY)
        soon_exists = soon in await self.slots()
        later = await self.book("patient1", local(later_day, 10))
        other = await self.book("patient2", local(later_day, 11), doctor_id=self.ids["doctor2"])
        await self.block(local(later_day, 9), local(later_day, 12))
        staff = self.identity("staff", "SUPPORT_STAFF")
        await self.block(local(later_day, 9), local(later_day, 12), identity=staff, doctor_id=self.ids["doctor2"])
        expected = [later]
        if soon_exists:  # an office hour about 6 hours from now (not at night)
            urgent = await self.book("patient2", soon)
            await self.block(soon, soon + timedelta(hours=1))
            expected = [urgent, later]

        items = [item for item in await self.queue() if item["doctor_id"] == self.ids["doctor"]]
        self.assertEqual([item["id"] for item in items], expected)
        self.assertEqual([item["urgent"] for item in items], [True, False] if soon_exists else [False])
        self.assertEqual(items[-1]["patient_phone"], "555-0101")
        self.assertEqual(items[-1]["patient_email"], "patient1@example.test")
        self.assertEqual(items[-1]["reason_label"], "Vacation")
        self.assertEqual([item["id"] for item in await self.queue(self.ids["doctor2"])], [other])
        await self.assert_http(422, None, self.queue("not-a-uuid"))

    async def test_past_and_completed_appointments_are_not_queued(self):
        day = self.today + timedelta(days=3)
        completed = await self.book("patient1", local(day, 10))
        await self.fetch("UPDATE appointments SET status = 'COMPLETED' WHERE id = $1", completed)
        preview, _ = await self.block(local(day, 9), local(day, 12))
        self.assertEqual(preview["appointments"], [])
        self.assertEqual(await self.queue(), [])

    # --- concurrency and speed --------------------------------------------------------------------

    async def test_booking_racing_a_block_never_double_books(self):
        day = self.today + timedelta(days=3)
        for hour in (9, 13, 17):
            with self.subTest(hour=hour):
                slot = local(day, hour)
                preview = await self.preview_block(slot, slot + timedelta(hours=1))
                results = await asyncio.gather(
                    self.apply_block(slot, slot + timedelta(hours=1), preview["fingerprint"]),
                    self.book("patient1", slot),
                    return_exceptions=True,
                )
                block_result, booking = results
                failures = [r for r in results if isinstance(r, Exception)]
                self.assertEqual(len(failures), 1, results)
                self.assertIsInstance(failures[0], HTTPException)
                row = (await self.slots(day))[slot]
                live = await self.fetch(
                    "SELECT count(*) AS n FROM appointments WHERE appointment_time = $1 AND status <> 'CANCELLED'", slot
                )
                if isinstance(booking, Exception):  # the block won
                    self.assertEqual(booking.detail, "Requested slot is not available.")
                    self.assertEqual((row["status"], live[0]["n"]), ("BLOCKED", 0))
                else:  # the booking won; the block must be previewed again and then flags it
                    self.assertEqual(block_result.detail, SCHEDULE_CHANGED)
                    self.assertEqual((row["status"], live[0]["n"]), ("BOOKED", 1))
                    _, result = await self.block(slot, slot + timedelta(hours=1))
                    self.assertEqual(result["to_flag"], 1)

    async def test_two_overlapping_blocks_at_once_one_gets_409(self):
        day = self.today + timedelta(days=3)
        staff = self.identity("staff", "SUPPORT_STAFF")
        first = await self.preview_block(local(day, 8), local(day, 14), identity=staff)
        second = await self.preview_block(local(day, 12), local(day, 18), identity=self.doctor_identity())
        results = await asyncio.gather(
            self.apply_block(local(day, 8), local(day, 14), first["fingerprint"], identity=staff),
            self.apply_block(local(day, 12), local(day, 18), second["fingerprint"]),
            return_exceptions=True,
        )
        failures = [r for r in results if isinstance(r, Exception)]
        self.assertEqual(len(failures), 1, results)
        self.assertEqual((failures[0].status_code, failures[0].detail), (409, SCHEDULE_CHANGED))
        self.assertEqual(len(await self.fetch("SELECT id FROM schedule_blocks")), 1)

    async def test_daylight_saving_range_blocks_each_office_hour_once(self):
        # DST ends Sunday 2030-11-03 in America/New_York; block Nov 3 8 AM -> Nov 4 8 AM
        now = datetime(2030, 10, 30, 12, 0, tzinfo=UTC)
        start = datetime(2030, 11, 3, 8, tzinfo=NY)
        async with self.sessions() as s:
            doctor = await self.doctor(s)
            plan = await plan_range_change(s, doctor, NY, start, start + timedelta(days=1), "block", now=now)
            await apply_block(s, doctor, NY, start, start + timedelta(days=1), category="VACATION", note=None, fingerprint=plan.fingerprint, actor=None, now=now)
            await s.commit()
        rows = await self.slots(date(2030, 11, 3))
        self.assertEqual(sorted(t.astimezone(NY).hour for t, r in rows.items() if r["status"] == "BLOCKED"), list(range(8, 24)))
        self.assertEqual(len(rows), 16)

    @unittest.skipIf(os.environ.get("HC_SKIP_SLOW"), "slow: 180-day block")
    async def test_slow_a_180_day_block_on_an_empty_schedule_is_fast(self):
        start = local(self.today + timedelta(days=1), 0)
        end = timeutils.utc_now() + timedelta(days=179)
        async with self.sessions() as s:
            doctor2 = await self.doctor(s, self.ids["doctor2"])
        staff = self.identity("staff", "SUPPORT_STAFF")
        began = time.perf_counter()
        preview = await self.preview_block(start, end, identity=staff, doctor_id=doctor2.id)
        result = await self.apply_block(start, end, preview["fingerprint"], identity=staff, doctor_id=doctor2.id)
        elapsed = time.perf_counter() - began
        self.assertGreater(result["created_blocked"], 170 * 16)
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
