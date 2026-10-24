"""Core scheduling flows against a real, migrated PostgreSQL database.

Exercises the backend's own service/route functions (not HTTP) together with the real schema:
slot generation, the booking trigger, the double-booking indexes, cancel/rebook, rescheduling,
patient and doctor cancellation, the clinic-local "today"/week views, and backfill migration 004.
"""

import asyncio
import unittest
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.api.routes.appointments import (
    CreateAppointmentRequest,
    RescheduleAppointmentRequest,
    confirm_appointment,
    create_appointment,
    delete_appointment,
    reschedule_appointment_route,
)
from backend.app.api.routes.doctor import doctor_all_appointments, doctor_appointments_today
from backend.app.core import timeutils
from backend.app.models import Doctor
from backend.app.services.availability_service import ensure_default_slots
from backend.tests.integration._pg import CLINIC_TZ, TempDatabase, require_pg, seed_clinic

NY = ZoneInfo(CLINIC_TZ)


def local(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=NY).astimezone(UTC)


class CoreFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        require_pg()
        # Pin the clinic zone so the tests don't depend on the CLINIC_TIMEZONE env var.
        self._tz_patch = patch.object(timeutils, "CLINIC_TZ", NY)
        self._tz_patch.start()
        self.db = await TempDatabase().create(migrate=True)
        conn = await self.db.connect()
        try:
            self.ids = await seed_clinic(conn)
        finally:
            await conn.close()
        self.engine = create_async_engine(self.db.sqlalchemy_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def asyncTearDown(self):
        await self.engine.dispose()
        await self.db.drop()
        self._tz_patch.stop()

    def identity(self, who: str, role: str):
        return SimpleNamespace(user_id=self.ids[f"{who}_user"], tenant_id=self.ids["tenant"], role=role)

    async def doctor(self, session: AsyncSession) -> Doctor:
        return (await session.execute(select(Doctor).where(Doctor.id == self.ids["doctor"]))).scalar_one()

    async def slots(self) -> list:
        conn = await self.db.connect()
        try:
            return await conn.fetch(
                "SELECT slot_time, status FROM doctor_availability WHERE doctor_id = $1 ORDER BY slot_time", self.ids["doctor"]
            )
        finally:
            await conn.close()

    # --- default slot generation -------------------------------------------------------------

    async def test_default_slots_cover_7_days_8am_to_11pm_across_dst(self):
        now = datetime(2030, 3, 9, 10, 0, tzinfo=UTC)  # 5 AM EST Sat; DST starts Sun 2030-03-10
        async with self.sessions() as s:
            created = await ensure_default_slots(s, await self.doctor(s), now=now)

        rows = await self.slots()
        self.assertEqual(created, 7 * 16)
        self.assertEqual(len(rows), 7 * 16)
        by_day: dict[date, list[int]] = {}
        for r in rows:
            by_day.setdefault(r["slot_time"].astimezone(NY).date(), []).append(r["slot_time"].astimezone(NY).hour)
        self.assertEqual(sorted(by_day), [date(2030, 3, 9) + timedelta(days=i) for i in range(7)])
        self.assertTrue(all(hours == list(range(8, 24)) for hours in by_day.values()))
        self.assertIn(local(date(2030, 3, 10), 8), [r["slot_time"] for r in rows])  # 8 AM EDT = 12:00 UTC

    async def test_top_up_fills_only_days_without_slots(self):
        now = datetime(2030, 6, 10, 10, 0, tzinfo=UTC)  # 6 AM EDT
        day1, day3 = date(2030, 6, 11), date(2030, 6, 13)
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s), now=now)

        conn = await self.db.connect()
        try:  # the doctor customises day1 and clears day3 entirely
            await conn.execute("UPDATE doctor_availability SET status = 'BLOCKED' WHERE slot_time = $1", local(day1, 10))
            await conn.execute("DELETE FROM doctor_availability WHERE slot_time = $1", local(day1, 15))
            await conn.execute(
                "DELETE FROM doctor_availability WHERE slot_time >= $1 AND slot_time < $2", local(day3, 0), local(day3, 0) + timedelta(days=1)
            )
        finally:
            await conn.close()

        async with self.sessions() as s:
            created = await ensure_default_slots(s, await self.doctor(s), now=now)
        async with self.sessions() as s:
            created_again = await ensure_default_slots(s, await self.doctor(s), now=now)

        rows = {r["slot_time"]: r["status"] for r in await self.slots()}
        self.assertEqual(created, 16)  # only day3 was re-created
        self.assertEqual(created_again, 0)
        self.assertEqual(sum(1 for t in rows if t.astimezone(NY).date() == day3), 16)
        self.assertEqual(rows[local(day1, 10)], "BLOCKED")  # doctor's block kept
        self.assertNotIn(local(day1, 15), rows)  # doctor's removal kept

    async def test_concurrent_generation_creates_no_duplicates(self):
        now = datetime(2030, 6, 10, 10, 0, tzinfo=UTC)

        async def generate():
            async with self.sessions() as s:
                return await ensure_default_slots(s, await self.doctor(s), now=now)

        await asyncio.gather(*(generate() for _ in range(4)))
        times = [r["slot_time"] for r in await self.slots()]
        self.assertEqual(len(times), 7 * 16)
        self.assertEqual(len(set(times)), len(times))

    # --- booking / cancel / rebook -----------------------------------------------------------

    async def test_book_cancel_rebook_evening_slot(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        tomorrow = timeutils.clinic_today() + timedelta(days=1)
        slot = local(tomorrow, 21)  # 9 PM clinic time
        payload = CreateAppointmentRequest(
            doctor_id=self.ids["doctor"], slot=slot.strftime("%Y-%m-%dT%H:%M:%S.000Z"), reason="Evening visit"
        )

        async with self.sessions() as s:
            booked = await create_appointment(payload=payload, identity=self.identity("patient1", "PATIENT"), db=s)
        rows = {r["slot_time"]: r["status"] for r in await self.slots()}
        self.assertEqual(rows[slot], "BOOKED")

        async with self.sessions() as s:  # the same slot can't be booked twice
            with self.assertRaises(HTTPException) as ctx:
                await create_appointment(payload=payload, identity=self.identity("patient2", "PATIENT"), db=s)
        self.assertEqual(ctx.exception.status_code, 409)

        async with self.sessions() as s:
            await delete_appointment(appointment_id=booked["id"], identity=self.identity("patient1", "PATIENT"), db=s)
        rows = {r["slot_time"]: r["status"] for r in await self.slots()}
        self.assertEqual(rows[slot], "AVAILABLE")  # trigger freed the slot

        async with self.sessions() as s:
            rebooked = await create_appointment(payload=payload, identity=self.identity("patient2", "PATIENT"), db=s)
        self.assertEqual(rebooked["status"], "SCHEDULED")

        conn = await self.db.connect()
        try:
            stored = await conn.fetchval("SELECT appointment_time FROM appointments WHERE id = $1", rebooked["id"])
        finally:
            await conn.close()
        self.assertEqual(stored, slot)

    async def test_patient_cannot_cancel_someone_elses_appointment(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        slot = local(timeutils.clinic_today() + timedelta(days=2), 10)
        payload = CreateAppointmentRequest(doctor_id=self.ids["doctor"], slot=slot.isoformat(), reason="Morning visit")
        async with self.sessions() as s:
            booked = await create_appointment(payload=payload, identity=self.identity("patient1", "PATIENT"), db=s)
        async with self.sessions() as s:
            with self.assertRaises(HTTPException) as ctx:
                await delete_appointment(appointment_id=booked["id"], identity=self.identity("patient2", "PATIENT"), db=s)
        self.assertEqual(ctx.exception.status_code, 403)

    # --- reschedule ---------------------------------------------------------------------------

    async def _book(self, who: str, slot: datetime, reason: str = "Follow-up visit") -> str:
        payload = CreateAppointmentRequest(doctor_id=self.ids["doctor"], slot=slot.isoformat(), reason=reason)
        async with self.sessions() as s:
            return (await create_appointment(payload=payload, identity=self.identity(who, "PATIENT"), db=s))["id"]

    async def _reschedule(self, appointment_id: str, slot: datetime, who: str, role: str) -> dict:
        async with self.sessions() as s:
            return await reschedule_appointment_route(
                appointment_id=appointment_id,
                payload=RescheduleAppointmentRequest(slot=slot.isoformat()),
                identity=self.identity(who, role),
                db=s,
            )

    async def test_patient_and_doctor_reschedule_keeps_details_and_moves_slot(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        day = timeutils.clinic_today() + timedelta(days=2)
        original, by_patient, by_doctor = local(day, 10), local(day, 15), local(day + timedelta(days=1), 20)
        appointment_id = await self._book("patient1", original, reason="Knee pain review")

        await self._reschedule(appointment_id, by_patient, "patient1", "PATIENT")
        rows = {r["slot_time"]: r["status"] for r in await self.slots()}
        self.assertEqual((rows[original], rows[by_patient]), ("AVAILABLE", "BOOKED"))

        async with self.sessions() as s:  # doctor confirms, then moves it again; status survives
            await confirm_appointment(appointment_id=appointment_id, identity=self.identity("doctor", "DOCTOR"), db=s)
        result = await self._reschedule(appointment_id, by_doctor, "doctor", "DOCTOR")
        self.assertEqual(result["status"], "CONFIRMED")
        rows = {r["slot_time"]: r["status"] for r in await self.slots()}
        self.assertEqual((rows[by_patient], rows[by_doctor]), ("AVAILABLE", "BOOKED"))

        conn = await self.db.connect()
        try:
            stored = await conn.fetchrow(
                "SELECT appointment_time, notes, patient_id, doctor_id, status, slot_id FROM appointments WHERE id = $1", appointment_id
            )
            new_slot_id = await conn.fetchval(
                "SELECT id FROM doctor_availability WHERE doctor_id = $1 AND slot_time = $2", self.ids["doctor"], by_doctor
            )
        finally:
            await conn.close()
        self.assertEqual(stored["appointment_time"], by_doctor)
        self.assertEqual(stored["notes"], "Knee pain review")
        self.assertEqual((str(stored["patient_id"]), str(stored["doctor_id"])), (self.ids["patient1"], self.ids["doctor"]))
        self.assertEqual(stored["status"], "CONFIRMED")
        self.assertEqual(stored["slot_id"], new_slot_id)

        # The freed original slot can be booked by someone else.
        await self._book("patient2", original)

    async def test_reschedule_rejects_taken_slot_other_owner_and_past_time(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        day = timeutils.clinic_today() + timedelta(days=2)
        mine = await self._book("patient1", local(day, 10))
        await self._book("patient2", local(day, 11))

        cases = [
            (local(day, 11), "patient1", "PATIENT", 409),  # slot already booked by patient2
            (local(day, 12), "patient2", "PATIENT", 403),  # not patient2's appointment
            (timeutils.utc_now() - timedelta(hours=1), "patient1", "PATIENT", 400),
        ]
        for slot, who, role, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(HTTPException) as ctx:
                    await self._reschedule(mine, slot, who, role)
                self.assertEqual(ctx.exception.status_code, expected)

        rows = {r["slot_time"]: r["status"] for r in await self.slots()}
        self.assertEqual((rows[local(day, 10)], rows[local(day, 12)]), ("BOOKED", "AVAILABLE"))  # nothing moved

    async def test_patient_can_cancel_confirmed_appointment(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        slot = local(timeutils.clinic_today() + timedelta(days=2), 14)
        appointment_id = await self._book("patient1", slot)
        async with self.sessions() as s:
            await confirm_appointment(appointment_id=appointment_id, identity=self.identity("doctor", "DOCTOR"), db=s)

        async with self.sessions() as s:
            await delete_appointment(appointment_id=appointment_id, identity=self.identity("patient1", "PATIENT"), db=s)

        rows = {r["slot_time"]: r["status"] for r in await self.slots()}
        self.assertEqual(rows[slot], "AVAILABLE")
        conn = await self.db.connect()
        try:
            status = await conn.fetchval("SELECT status FROM appointments WHERE id = $1", appointment_id)
            audit_old = await conn.fetchval(
                "SELECT old_data->>'status' FROM audit_logs WHERE record_id = $1 AND action_type = 'DELETE' ORDER BY performed_at DESC LIMIT 1",
                appointment_id,
            )
        finally:
            await conn.close()
        self.assertEqual(status, "CANCELLED")
        self.assertEqual(audit_old, "CONFIRMED")

    async def test_doctor_can_cancel_only_own_appointments(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        slot = local(timeutils.clinic_today() + timedelta(days=2), 16)
        appointment_id = await self._book("patient1", slot)
        conn = await self.db.connect()
        try:  # a second doctor in the same clinic (reusing the admin user as its login)
            await conn.execute(
                "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Other')",
                self.ids["tenant"], self.ids["admin_user"],
            )
        finally:
            await conn.close()

        async with self.sessions() as s:
            with self.assertRaises(HTTPException) as ctx:
                await delete_appointment(appointment_id=appointment_id, identity=self.identity("admin", "DOCTOR"), db=s)
        self.assertEqual(ctx.exception.status_code, 403)

        async with self.sessions() as s:
            await delete_appointment(appointment_id=appointment_id, identity=self.identity("doctor", "DOCTOR"), db=s)
        rows = {r["slot_time"]: r["status"] for r in await self.slots()}
        self.assertEqual(rows[slot], "AVAILABLE")

    async def _second_doctor(self) -> str:
        """A second doctor in the same clinic (logging in as the admin user), with default slots."""
        conn = await self.db.connect()
        try:
            doctor_id = str(await conn.fetchval(
                "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Other') RETURNING id",
                self.ids["tenant"], self.ids["admin_user"],
            ))
        finally:
            await conn.close()
        async with self.sessions() as s:
            other = (await s.execute(select(Doctor).where(Doctor.id == doctor_id))).scalar_one()
            await ensure_default_slots(s, other)
        return doctor_id

    async def _slot_status(self, doctor_id: str, slot: datetime) -> str:
        conn = await self.db.connect()
        try:
            return await conn.fetchval(
                "SELECT status FROM doctor_availability WHERE doctor_id = $1 AND slot_time = $2", doctor_id, slot
            )
        finally:
            await conn.close()

    async def test_reschedule_rejects_same_time_and_inactive_appointments(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        day = timeutils.clinic_today() + timedelta(days=2)
        same = await self._book("patient1", local(day, 9))
        completed = await self._book("patient1", local(day, 13))
        cancelled = await self._book("patient2", local(day, 17))
        conn = await self.db.connect()
        try:
            await conn.execute("UPDATE appointments SET status = 'COMPLETED' WHERE id = $1", completed)
        finally:
            await conn.close()
        async with self.sessions() as s:
            await delete_appointment(appointment_id=cancelled, identity=self.identity("patient2", "PATIENT"), db=s)

        cases = [
            (same, local(day, 9), "patient1", 400),  # already at that time
            (completed, local(day, 14), "patient1", 400),  # completed visits can't move
            (cancelled, local(day, 18), "patient2", 404),  # cancelled visits are soft-deleted
        ]
        for appointment_id, slot, who, expected in cases:
            with self.subTest(expected=expected, slot=slot):
                with self.assertRaises(HTTPException) as ctx:
                    await self._reschedule(appointment_id, slot, who, "PATIENT")
                self.assertEqual(ctx.exception.status_code, expected)
        self.assertEqual(await self._slot_status(self.ids["doctor"], local(day, 14)), "AVAILABLE")
        self.assertEqual(await self._slot_status(self.ids["doctor"], local(day, 18)), "AVAILABLE")

    async def test_doctor_cannot_reschedule_another_doctors_appointment(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        await self._second_doctor()
        day = timeutils.clinic_today() + timedelta(days=2)
        appointment_id = await self._book("patient1", local(day, 10))

        with self.assertRaises(HTTPException) as ctx:
            await self._reschedule(appointment_id, local(day, 12), "admin", "DOCTOR")  # the other doctor's login
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(await self._slot_status(self.ids["doctor"], local(day, 10)), "BOOKED")

    async def test_reschedule_rejects_time_the_patient_has_booked_with_another_doctor(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        other_doctor = await self._second_doctor()
        day = timeutils.clinic_today() + timedelta(days=2)
        mine = await self._book("patient1", local(day, 10))
        payload = CreateAppointmentRequest(doctor_id=other_doctor, slot=local(day, 15).isoformat(), reason="Second opinion")
        async with self.sessions() as s:
            await create_appointment(payload=payload, identity=self.identity("patient1", "PATIENT"), db=s)

        # The first doctor is free at 3 PM, but patient1 is already with the other doctor then.
        with self.assertRaises(HTTPException) as ctx:
            await self._reschedule(mine, local(day, 15), "doctor", "DOCTOR")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(await self._slot_status(self.ids["doctor"], local(day, 10)), "BOOKED")  # rolled back
        self.assertEqual(await self._slot_status(self.ids["doctor"], local(day, 15)), "AVAILABLE")

    async def test_reschedule_writes_audit_log_with_old_and_new_time(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        day = timeutils.clinic_today() + timedelta(days=3)
        appointment_id = await self._book("patient1", local(day, 8))
        await self._reschedule(appointment_id, local(day, 22), "patient1", "PATIENT")

        conn = await self.db.connect()
        try:
            # The DB audit trigger also logs a full-row UPDATE (it has an "id" key); pick the app's entry.
            row = await conn.fetchrow(
                """SELECT old_data->>'appointment_time' AS old, new_data->>'appointment_time' AS new, performed_by
                   FROM audit_logs WHERE record_id = $1 AND action_type = 'UPDATE'
                     AND new_data ? 'appointment_time' AND NOT new_data ? 'id'""",
                appointment_id,
            )
        finally:
            await conn.close()
        self.assertEqual(datetime.fromisoformat(row["old"]), local(day, 8))
        self.assertEqual(datetime.fromisoformat(row["new"]), local(day, 22))
        self.assertEqual(str(row["performed_by"]), self.ids["patient1_user"])

    # --- clinic-local day and week views -----------------------------------------------------

    async def _insert_appointments(self, *times: datetime) -> None:
        conn = await self.db.connect()
        try:
            for t in times:
                await conn.execute(
                    "INSERT INTO appointments (tenant_id, doctor_id, patient_id, appointment_time, notes) VALUES ($1, $2, $3, $4, 'x')",
                    self.ids["tenant"], self.ids["doctor"], self.ids["patient1"], t,
                )
        finally:
            await conn.close()

    async def test_doctor_today_uses_clinic_day_late_in_the_evening(self):
        today = date(2030, 6, 14)
        await self._insert_appointments(local(today, 8), local(today, 23), local(today + timedelta(days=1), 9))
        late_evening = datetime(2030, 6, 15, 3, 30, tzinfo=UTC)  # 11:30 PM EDT on Jun 14 (already Jun 15 in UTC)

        with patch.object(timeutils, "utc_now", return_value=late_evening):
            async with self.sessions() as s:
                result = await doctor_appointments_today(identity=self.identity("doctor", "DOCTOR"), db=s)

        times = sorted(datetime.fromisoformat(a["time"]) for a in result)
        self.assertEqual(times, [local(today, 8), local(today, 23)])
        # The reschedule dialog needs the doctor's id and the visit reason.
        self.assertTrue(all(a["doctor_id"] == self.ids["doctor"] and a["reason"] == "x" for a in result))

    async def test_doctor_week_is_monday_to_sunday_clinic_time(self):
        monday = date(2030, 6, 10)
        sunday_11pm = local(monday + timedelta(days=6), 23)  # Monday 03:00 UTC of the next week
        next_monday_8am = local(monday + timedelta(days=7), 8)
        await self._insert_appointments(local(monday, 8), sunday_11pm, next_monday_8am)

        async with self.sessions() as s:
            result = await doctor_all_appointments(from_date=monday + timedelta(days=2), identity=self.identity("doctor", "DOCTOR"), db=s)

        times = sorted(datetime.fromisoformat(a["time"]) for a in result)
        self.assertEqual(times, [local(monday, 8), sunday_11pm])
        self.assertTrue(all(a["doctor_id"] == self.ids["doctor"] for a in result))

    # --- migration 004 -------------------------------------------------------------------------

    async def test_backfill_004_adds_evening_slots_once(self):
        conn = await self.db.connect()
        try:
            # The doctor has the old 8 AM-4 PM schedule for the next 7 days (relative to real now()).
            await conn.execute(
                """INSERT INTO doctor_availability (tenant_id, doctor_id, slot_time, status)
                   SELECT $1, $2, ((((now() AT TIME ZONE $3)::date + o) + make_interval(hours => h)) AT TIME ZONE $3), 'AVAILABLE'
                   FROM generate_series(1, 6) o, generate_series(8, 16) h""",
                self.ids["tenant"], self.ids["doctor"], CLINIC_TZ,
            )
            other = await conn.fetchval(  # a second doctor with no slots must not be touched
                "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Empty') RETURNING id",
                self.ids["tenant"], self.ids["admin_user"],
            )
        finally:
            await conn.close()

        settings = {"migration.clinic_timezone": CLINIC_TZ}
        await self.db.run_migration("004_backfill_evening_availability_slots.sql", settings)
        after_first = await self.slots()
        await self.db.run_migration("004_backfill_evening_availability_slots.sql", settings)
        after_second = await self.slots()

        evening = [r for r in after_first if r["slot_time"].astimezone(NY).hour >= 17]
        self.assertGreaterEqual(len(evening), 6 * 7)  # 5-11 PM on days +1..+6 (plus any left today)
        self.assertTrue(all(17 <= r["slot_time"].astimezone(NY).hour <= 23 for r in evening))
        self.assertEqual(len(after_second), len(after_first))
        conn = await self.db.connect()
        try:
            self.assertEqual(await conn.fetchval("SELECT count(*) FROM doctor_availability WHERE doctor_id = $1", other), 0)
        finally:
            await conn.close()


if __name__ == "__main__":
    unittest.main()
