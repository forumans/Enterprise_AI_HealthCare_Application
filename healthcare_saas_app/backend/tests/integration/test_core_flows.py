"""Core scheduling flows against a real, migrated PostgreSQL database.

Exercises the backend's own service/route functions (not HTTP) together with the real schema:
slot generation, the booking trigger, the double-booking indexes, cancel/rebook, rescheduling,
patient and doctor cancellation, the clinic-local "today"/week views, and backfill migration 004.
"""

import asyncio
import unittest
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.api.routes.admin import admin_create_user, admin_list_users, soft_delete_user
from backend.app.api.routes.admin_password_reset import (
    ChangeEmailRequest,
    NewEmailRequest,
    NewPasswordRequest,
    activate_user,
    change_email_by_id,
    change_user_email,
    deactivate_user,
    reset_password_by_id,
    search_users,
)
from backend.app.core.security import verify_password
from backend.app.api.routes.appointments import (
    CreateAppointmentRequest,
    RescheduleAppointmentRequest,
    UpdateAppointmentRequest,
    confirm_appointment,
    create_appointment,
    delete_appointment,
    reschedule_appointment_route,
    update_appointment,
)
from backend.app.api.routes.doctor import (
    UpsertAvailabilityRequest,
    UpsertDoctorAvailabilityRequest,
    doctor_all_appointments,
    doctor_appointments_today,
    upsert_availability,
    upsert_doctor_availability,
)
from backend.app.api.routes.auth import LoginRequest, login
from backend.app.api.routes.patients import search_patients
from backend.app.api.routes.support import (
    UpdateSupportProfileRequest,
    get_support_profile,
    support_list_appointments,
    support_search_doctors,
    support_search_patients,
    update_support_profile,
)
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

    # --- support staff -------------------------------------------------------------------------

    async def _register_support_staff(self) -> str:
        """Register a support staff member through the admin endpoint; returns their user id."""
        body = {"role": "SUPPORT_STAFF", "full_name": "Sam Support", "email": "sam@example.test", "password": "secret123", "phone": "5551234567"}
        request = SimpleNamespace(json=AsyncMock(return_value=body))
        async with self.sessions() as s:
            created = await admin_create_user(request=request, identity=self.identity("admin", "ADMIN"), db=s)
        self.ids["staff_user"] = created["id"]
        return created["id"]

    def staff(self):
        return self.identity("staff", "SUPPORT_STAFF")

    async def test_admin_registers_lists_and_deactivates_support_staff(self):
        user_id = await self._register_support_staff()

        async with self.sessions() as s:
            users = await admin_list_users(page=1, page_size=50, identity=self.identity("admin", "ADMIN"), db=s)
        listed = next(u for u in users if u["id"] == user_id)
        self.assertEqual((listed["role"], listed["name"]), ("SUPPORT_STAFF", "Sam Support"))

        async with self.sessions() as s:
            await soft_delete_user(user_id=user_id, identity=self.identity("admin", "ADMIN"), db=s)
        conn = await self.db.connect()
        try:
            user = await conn.fetchrow("SELECT is_active, deleted_at FROM users WHERE id = $1", user_id)
            profile_deleted = await conn.fetchval("SELECT deleted_at FROM support_staff WHERE user_id = $1", user_id)
        finally:
            await conn.close()
        self.assertFalse(user["is_active"])
        self.assertIsNotNone(user["deleted_at"])
        self.assertIsNotNone(profile_deleted)

    async def test_support_staff_books_on_behalf_of_a_patient(self):
        await self._register_support_staff()
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        slot = local(timeutils.clinic_today() + timedelta(days=2), 9)

        payload = CreateAppointmentRequest(doctor_id=self.ids["doctor"], slot=slot.isoformat(), reason="Booked by phone", patient_id=self.ids["patient2"])
        async with self.sessions() as s:
            booked = await create_appointment(payload=payload, identity=self.staff(), db=s)
        conn = await self.db.connect()
        try:
            stored = await conn.fetchrow("SELECT patient_id, notes FROM appointments WHERE id = $1", booked["id"])
        finally:
            await conn.close()
        self.assertEqual((str(stored["patient_id"]), stored["notes"]), (self.ids["patient2"], "Booked by phone"))
        self.assertEqual(await self._slot_status(self.ids["doctor"], slot), "BOOKED")

        cases = [
            (None, local(timeutils.clinic_today() + timedelta(days=2), 10), 422),  # patient_id missing
            ("00000000-0000-0000-0000-000000000000", local(timeutils.clinic_today() + timedelta(days=2), 10), 404),
            (self.ids["patient1"], timeutils.utc_now() - timedelta(hours=1), 400),  # in the past
        ]
        for patient_id, when, expected in cases:
            with self.subTest(expected=expected):
                bad = CreateAppointmentRequest(doctor_id=self.ids["doctor"], slot=when.isoformat(), reason="Booked by phone", patient_id=patient_id)
                async with self.sessions() as s:
                    with self.assertRaises(HTTPException) as ctx:
                        await create_appointment(payload=bad, identity=self.staff(), db=s)
                self.assertEqual(ctx.exception.status_code, expected)

    async def test_support_staff_updates_reschedules_and_cancels_any_appointment(self):
        await self._register_support_staff()
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        day = timeutils.clinic_today() + timedelta(days=2)
        appointment_id = await self._book("patient1", local(day, 10), reason="Original reason")

        async with self.sessions() as s:
            updated = await update_appointment(
                appointment_id=appointment_id, payload=UpdateAppointmentRequest(reason="Updated by support"), identity=self.staff(), db=s
            )
        self.assertEqual(updated["reason"], "Updated by support")

        await self._reschedule(appointment_id, local(day, 19), "staff", "SUPPORT_STAFF")
        self.assertEqual(await self._slot_status(self.ids["doctor"], local(day, 10)), "AVAILABLE")
        self.assertEqual(await self._slot_status(self.ids["doctor"], local(day, 19)), "BOOKED")

        async with self.sessions() as s:
            await delete_appointment(appointment_id=appointment_id, identity=self.staff(), db=s)
        self.assertEqual(await self._slot_status(self.ids["doctor"], local(day, 19)), "AVAILABLE")

        conn = await self.db.connect()
        try:
            stored = await conn.fetchrow("SELECT notes, status FROM appointments WHERE id = $1", appointment_id)
        finally:
            await conn.close()
        self.assertEqual((stored["notes"], stored["status"]), ("Updated by support", "CANCELLED"))

    async def test_support_staff_cannot_update_completed_appointment(self):
        await self._register_support_staff()
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        appointment_id = await self._book("patient1", local(timeutils.clinic_today() + timedelta(days=2), 11))
        conn = await self.db.connect()
        try:
            await conn.execute("UPDATE appointments SET status = 'COMPLETED' WHERE id = $1", appointment_id)
        finally:
            await conn.close()
        async with self.sessions() as s:
            with self.assertRaises(HTTPException) as ctx:
                await update_appointment(
                    appointment_id=appointment_id, payload=UpdateAppointmentRequest(reason="Too late now"), identity=self.staff(), db=s
                )
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_support_staff_lists_appointments_by_patient_or_doctor(self):
        await self._register_support_staff()
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        other_doctor = await self._second_doctor()
        day = timeutils.clinic_today() + timedelta(days=2)
        first = await self._book("patient1", local(day, 9))
        await self._book("patient2", local(day, 10))
        payload = CreateAppointmentRequest(doctor_id=other_doctor, slot=local(day, 12).isoformat(), reason="Second opinion")
        async with self.sessions() as s:
            await create_appointment(payload=payload, identity=self.identity("patient1", "PATIENT"), db=s)

        async with self.sessions() as s:
            by_patient = await support_list_appointments(patient_id=self.ids["patient1"], doctor_id=None, identity=self.staff(), db=s)
            by_doctor = await support_list_appointments(patient_id=None, doctor_id=self.ids["doctor"], identity=self.staff(), db=s)
        self.assertEqual([a["doctor_id"] for a in by_patient], [self.ids["doctor"], other_doctor])
        self.assertEqual([a["patient_name"] for a in by_doctor], ["Patient 1", "Patient 2"])
        self.assertEqual(by_patient[0]["id"], first)

        for patient_id, doctor_id in ((None, None), (self.ids["patient1"], self.ids["doctor"])):
            async with self.sessions() as s:
                with self.assertRaises(HTTPException) as ctx:
                    await support_list_appointments(patient_id=patient_id, doctor_id=doctor_id, identity=self.staff(), db=s)
            self.assertEqual(ctx.exception.status_code, 422)

    async def test_admin_changes_a_users_login_email(self):
        await self._register_support_staff()
        conn = await self.db.connect()
        try:
            other_tenant = await conn.fetchval("INSERT INTO tenants (name) VALUES ('Other Clinic') RETURNING id")
            await conn.execute(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'elsewhere@example.test', 'x', 'PATIENT')", other_tenant
            )
            await conn.execute(  # a deleted account in another clinic doesn't block reuse
                "INSERT INTO users (tenant_id, email, password_hash, role, deleted_at) VALUES ($1, 'freed@example.test', 'x', 'PATIENT', now())",
                other_tenant,
            )
            await conn.execute(  # a deleted account in this clinic still holds the (tenant, email) unique key
                "INSERT INTO users (tenant_id, email, password_hash, role, deleted_at) VALUES ($1, 'oldstaff@example.test', 'x', 'PATIENT', now())",
                self.ids["tenant"],
            )
        finally:
            await conn.close()

        async def change(email: str, role: str, new_email: str) -> dict:
            async with self.sessions() as s:
                return await change_user_email(
                    request=ChangeEmailRequest(email=email, role=role, new_email=new_email), identity=self.identity("admin", "ADMIN"), db=s
                )

        result = await change("patient1@example.test", "PATIENT", "  Patient.One@NEW.example.test ")
        self.assertEqual((result["old_email"], result["new_email"]), ("patient1@example.test", "patient.one@new.example.test"))
        await change("sam@example.test", "SUPPORT_STAFF", "freed@example.test")

        cases = [
            ("patient2@example.test", "PATIENT", "patient2@example.test", 400),  # unchanged
            ("patient2@example.test", "DOCTOR", "p2@example.test", 404),  # wrong role
            ("patient2@example.test", "PATIENT", "doc@example.test", 409),  # taken in this clinic
            ("patient2@example.test", "PATIENT", "elsewhere@example.test", 409),  # active in another clinic
            ("patient2@example.test", "PATIENT", "oldstaff@example.test", 409),  # deleted, but same clinic
        ]
        for email, role, new_email, expected in cases:
            with self.subTest(new_email=new_email, expected=expected):
                with self.assertRaises(HTTPException) as ctx:
                    await change(email, role, new_email)
                self.assertEqual(ctx.exception.status_code, expected)

        conn = await self.db.connect()
        try:
            emails = dict(await conn.fetch("SELECT id::text, email FROM users WHERE id = ANY($1::uuid[])",
                                           [self.ids["patient1_user"], self.ids["patient2_user"], self.ids["staff_user"]]))
            audit = await conn.fetchrow(
                """SELECT old_data->>'email' AS old, new_data->>'email' AS new FROM audit_logs
                   WHERE record_id = $1 AND table_name = 'users' AND NOT new_data ? 'id'""",
                self.ids["patient1_user"],
            )
        finally:
            await conn.close()
        self.assertEqual(emails[self.ids["patient1_user"]], "patient.one@new.example.test")
        self.assertEqual(emails[self.ids["staff_user"]], "freed@example.test")
        self.assertEqual(emails[self.ids["patient2_user"]], "patient2@example.test")
        self.assertEqual((audit["old"], audit["new"]), ("patient1@example.test", "patient.one@new.example.test"))

    async def test_admin_searches_users_by_role_then_acts_by_id(self):
        await self._register_support_staff()
        conn = await self.db.connect()
        try:
            await conn.execute(
                "UPDATE patients SET phone = '(555) 600-7000', address_line1 = '1 Main St', city = 'Austin', state = 'TX' WHERE id = $1",
                self.ids["patient1"],
            )
            await conn.execute("UPDATE doctors SET specialty = 'Cardiology' WHERE id = $1", self.ids["doctor"])
            await conn.execute("INSERT INTO admins (tenant_id, user_id, full_name) VALUES ($1, $2, 'Ada Admin')", self.ids["tenant"], self.ids["admin_user"])
            other_tenant = await conn.fetchval("INSERT INTO tenants (name) VALUES ('Other Clinic') RETURNING id")
            outsider = str(await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'outsider@example.test', 'x', 'PATIENT') RETURNING id",
                other_tenant,
            ))
        finally:
            await conn.close()
        admin = self.identity("admin", "ADMIN")

        async def search(role: str, q: str) -> list[dict]:
            async with self.sessions() as s:
                return await search_users(role=role, q=q, identity=admin, db=s)

        self.assertEqual([u["name"] for u in await search("PATIENT", "patient")], ["Patient 1", "Patient 2"])
        self.assertEqual([u["name"] for u in await search("PATIENT", "PATIENT2@EXAMPLE")], ["Patient 2"])  # by email
        hit = (await search("PATIENT", "600-70"))[0]  # by phone
        self.assertEqual(
            (hit["user_id"], hit["email"], hit["address"]), (self.ids["patient1_user"], "patient1@example.test", "1 Main St, Austin, TX")
        )
        self.assertEqual([(u["name"], u["specialty"]) for u in await search("DOCTOR", "test")], [("Dr Test", "Cardiology")])
        self.assertEqual([u["email"] for u in await search("SUPPORT_STAFF", "sam")], ["sam@example.test"])
        self.assertEqual([u["name"] for u in await search("ADMIN", "ada")], ["Ada Admin"])
        self.assertEqual(await search("DOCTOR", "patient"), [])  # only the chosen role
        with self.assertRaises(HTTPException) as ctx:
            await search("NURSE", "patient")
        self.assertEqual(ctx.exception.status_code, 400)

        async with self.sessions() as s:
            result = await reset_password_by_id(
                user_id=self.ids["staff_user"], request=NewPasswordRequest(new_password="BrandNew123"), identity=admin, db=s
            )
        self.assertEqual(result["user_email"], "sam@example.test")
        async with self.sessions() as s:
            result = await change_email_by_id(
                user_id=self.ids["patient1_user"], request=NewEmailRequest(new_email="P1@New.Example.test"), identity=admin, db=s
            )
        self.assertEqual((result["old_email"], result["new_email"]), ("patient1@example.test", "p1@new.example.test"))

        conn = await self.db.connect()
        try:
            staff_hash = await conn.fetchval("SELECT password_hash FROM users WHERE id = $1", self.ids["staff_user"])
            p1_email = await conn.fetchval("SELECT email FROM users WHERE id = $1", self.ids["patient1_user"])
            password_audit = await conn.fetchval(
                "SELECT new_data::text FROM audit_logs WHERE record_id = $1 AND new_data ? 'password_reset'", self.ids["staff_user"]
            )
        finally:
            await conn.close()
        self.assertTrue(verify_password("BrandNew123", staff_hash))
        self.assertEqual(p1_email, "p1@new.example.test")
        self.assertNotIn("BrandNew123", password_audit)  # the audit records that it happened, never the password

        cases = [
            (outsider, "PATIENT"),  # another clinic's user
            ("00000000-0000-0000-0000-000000000000", "PATIENT"),
        ]
        for user_id, _ in cases:
            with self.subTest(user_id=user_id):
                async with self.sessions() as s:
                    with self.assertRaises(HTTPException) as ctx:
                        await reset_password_by_id(user_id=user_id, request=NewPasswordRequest(new_password="Whatever123"), identity=admin, db=s)
                self.assertEqual(ctx.exception.status_code, 404)
        async with self.sessions() as s:
            with self.assertRaises(HTTPException) as ctx:
                await reset_password_by_id(user_id=self.ids["staff_user"], request=NewPasswordRequest(new_password="short"), identity=admin, db=s)
        self.assertEqual(ctx.exception.status_code, 400)
        async with self.sessions() as s:
            with self.assertRaises(HTTPException) as ctx:
                await change_email_by_id(user_id=self.ids["patient2_user"], request=NewEmailRequest(new_email="doc@example.test"), identity=admin, db=s)
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_admin_deactivates_and_activates_accounts(self):
        await self._register_support_staff()
        conn = await self.db.connect()
        try:
            second_admin = str(await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'admin2@example.test', 'x', 'ADMIN') RETURNING id",
                self.ids["tenant"],
            ))
            await conn.execute("INSERT INTO admins (tenant_id, user_id, full_name) VALUES ($1, $2, 'Ada Admin')", self.ids["tenant"], self.ids["admin_user"])
            await conn.execute("INSERT INTO admins (tenant_id, user_id, full_name) VALUES ($1, $2, 'Bob Admin')", self.ids["tenant"], second_admin)
        finally:
            await conn.close()
        admin = self.identity("admin", "ADMIN")
        bob = SimpleNamespace(user_id=second_admin, tenant_id=self.ids["tenant"], role="ADMIN")

        async def set_active(identity, user_id: str, active: bool) -> dict:
            async with self.sessions() as s:
                return await (activate_user if active else deactivate_user)(user_id=user_id, identity=identity, db=s)

        async def can_log_in(email: str) -> bool:
            async with self.sessions() as s:
                try:
                    await login(request=LoginRequest(email=email, password="Secret12345"), db=s)
                    return True
                except HTTPException as exc:
                    self.assertEqual(exc.status_code, 401)
                    return False

        async with self.sessions() as s:  # give the staff account a real password to log in with
            await reset_password_by_id(user_id=self.ids["staff_user"], request=NewPasswordRequest(new_password="Secret12345"), identity=admin, db=s)
        self.assertTrue(await can_log_in("sam@example.test"))

        result = await set_active(admin, self.ids["staff_user"], False)
        self.assertFalse(result["is_active"])
        self.assertFalse(await can_log_in("sam@example.test"))
        async with self.sessions() as s:
            listed = (await search_users(role="SUPPORT_STAFF", q="*", identity=admin, db=s))[0]
        self.assertEqual((listed["is_active"], listed["is_self"]), (False, False))  # still listed, shown as deactivated

        await set_active(admin, self.ids["staff_user"], True)
        self.assertTrue(await can_log_in("sam@example.test"))

        cases = [
            (admin, self.ids["admin_user"], False, 400),  # can't deactivate yourself
            (admin, self.ids["staff_user"], True, 400),  # already active
            (admin, "00000000-0000-0000-0000-000000000000", False, 404),
        ]
        for identity, user_id, active, expected in cases:
            with self.subTest(user_id=user_id, active=active):
                with self.assertRaises(HTTPException) as ctx:
                    await set_active(identity, user_id, active)
                self.assertEqual(ctx.exception.status_code, expected)

        # Admins can deactivate another admin, but a deactivated admin can't act (even with a valid
        # token), so two admins can never deactivate each other and leave none active.
        await set_active(admin, second_admin, False)
        with self.assertRaises(HTTPException) as ctx:
            await set_active(bob, self.ids["admin_user"], False)
        self.assertEqual(ctx.exception.status_code, 403)
        async with self.sessions() as s:
            me = [u for u in await search_users(role="ADMIN", q="*", identity=admin, db=s) if u["is_self"]]
        self.assertEqual([(u["user_id"], u["is_active"]) for u in me], [(self.ids["admin_user"], True)])

        conn = await self.db.connect()
        try:
            audits = await conn.fetch(
                """SELECT new_data->>'is_active' AS active FROM audit_logs
                   WHERE record_id = $1 AND new_data ? 'is_active' AND NOT new_data ? 'id' ORDER BY performed_at""",
                self.ids["staff_user"],
            )
        finally:
            await conn.close()
        self.assertEqual([a["active"] for a in audits], ["false", "true"])

    async def test_star_lists_everyone_of_the_role_on_every_search(self):
        await self._register_support_staff()
        other_doctor = await self._second_doctor()
        conn = await self.db.connect()
        try:
            # More patients than the normal 50-result cap, plus one deleted patient that must stay hidden
            for n in range(3, 56):
                user_id = await conn.fetchval(
                    "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, $2, 'x', 'PATIENT') RETURNING id",
                    self.ids["tenant"], f"bulk{n}@example.test",
                )
                await conn.execute(
                    "INSERT INTO patients (tenant_id, user_id, full_name, deleted_at) VALUES ($1, $2, $3, $4)",
                    self.ids["tenant"], user_id, f"Bulk Patient {n:02d}", datetime.now(UTC) if n == 55 else None,
                )
        finally:
            await conn.close()
        admin, staff = self.identity("admin", "ADMIN"), self.staff()
        expected_patients = 2 + 52  # Patient 1/2 + Bulk 03..54

        async with self.sessions() as s:
            support_patients = await support_search_patients(q="*", identity=staff, db=s)
            support_doctors = await support_search_doctors(q=" * ", identity=staff, db=s)
            admin_patients = await search_users(role="PATIENT", q="*", identity=admin, db=s)
            admin_doctors = await search_users(role="DOCTOR", q="*", identity=admin, db=s)
            admin_staff = await search_users(role="SUPPORT_STAFF", q="*", identity=admin, db=s)
            doctor_view = await search_patients(q="*", identity=self.identity("doctor", "DOCTOR"), db=s)

        self.assertEqual(len(support_patients), expected_patients)
        self.assertEqual(len(admin_patients), expected_patients)
        self.assertEqual({d["id"] for d in support_doctors}, {self.ids["doctor"], other_doctor})
        # Dr Other's login is the ADMIN user, so the DOCTOR-role search lists only Dr Test's account
        self.assertEqual([d["user_id"] for d in admin_doctors], [self.ids["doctor_user"]])
        self.assertEqual([u["email"] for u in admin_staff], ["sam@example.test"])  # only the chosen role
        self.assertEqual(len({p["id"] for p in doctor_view}), expected_patients)
        self.assertNotIn("Bulk Patient 55", [p["name"] for p in support_patients])

        async with self.sessions() as s:  # a normal search still stops at 50
            capped = await support_search_patients(q="bulk", identity=staff, db=s)
        self.assertEqual(len(capped), 50)

    async def test_support_staff_views_and_updates_own_profile(self):
        user_id = await self._register_support_staff()
        async with self.sessions() as s:
            profile = await get_support_profile(identity=self.staff(), db=s)
        self.assertEqual((profile["full_name"], profile["phone"], profile["email"]), ("Sam Support", "5551234567", "sam@example.test"))

        async with self.sessions() as s:
            updated = await update_support_profile(
                payload=UpdateSupportProfileRequest(full_name="Samantha Support", phone="+1 555-765-4321"), identity=self.staff(), db=s
            )
        self.assertEqual((updated["full_name"], updated["phone"], updated["email"]), ("Samantha Support", "+1 555-765-4321", "sam@example.test"))

        conn = await self.db.connect()
        try:
            stored = await conn.fetchrow("SELECT full_name, phone FROM support_staff WHERE user_id = $1", user_id)
            audit = await conn.fetchrow(
                """SELECT old_data->>'full_name' AS old, new_data->>'full_name' AS new, performed_by FROM audit_logs
                   WHERE table_name = 'support_staff' AND action_type = 'UPDATE' AND NOT new_data ? 'id'""",
            )
        finally:
            await conn.close()
        self.assertEqual((stored["full_name"], stored["phone"]), ("Samantha Support", "+1 555-765-4321"))
        self.assertEqual((audit["old"], audit["new"], str(audit["performed_by"])), ("Sam Support", "Samantha Support", user_id))

        # Someone without a support staff profile (e.g. a doctor's login) has none to read
        async with self.sessions() as s:
            with self.assertRaises(HTTPException) as ctx:
                await get_support_profile(identity=self.identity("doctor", "SUPPORT_STAFF"), db=s)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_support_staff_searches_patients_by_name_or_phone(self):
        await self._register_support_staff()
        conn = await self.db.connect()
        try:
            await conn.execute("UPDATE patients SET phone = '(555) 123-4567', city = 'Austin' WHERE id = $1", self.ids["patient1"])
            await conn.execute("UPDATE patients SET phone = '555.987.0000' WHERE id = $1", self.ids["patient2"])
            deleted = await conn.fetchval(
                "INSERT INTO patients (tenant_id, user_id, full_name, phone, deleted_at) VALUES ($1, $2, 'Patient Gone', '5551234567', now()) RETURNING id",
                self.ids["tenant"], self.ids["admin_user"],
            )
        finally:
            await conn.close()

        async def search(q: str) -> list[dict]:
            async with self.sessions() as s:
                return await support_search_patients(q=q, identity=self.staff(), db=s)

        self.assertEqual([p["name"] for p in await search("patient")], ["Patient 1", "Patient 2"])  # case-insensitive
        self.assertEqual([p["name"] for p in await search("555-123")], ["Patient 1"])  # formatting ignored
        self.assertEqual([p["name"] for p in await search("9870")], ["Patient 2"])
        self.assertEqual(await search("nobody here"), [])

        hit = (await search("Patient 1"))[0]
        self.assertEqual((hit["id"], hit["phone"], hit["city"], hit["email"]), (self.ids["patient1"], "(555) 123-4567", "Austin", "patient1@example.test"))
        self.assertNotIn(str(deleted), [p["id"] for p in await search("555")])  # soft-deleted patients are hidden
        self.assertNotIn("diagnosis", hit)  # contact details only

        with self.assertRaises(HTTPException) as ctx:
            await search(" p ")
        self.assertEqual(ctx.exception.status_code, 422)

    async def test_support_staff_searches_doctors_by_name_or_phone(self):
        await self._register_support_staff()
        other_doctor = await self._second_doctor()
        conn = await self.db.connect()
        try:
            await conn.execute(
                "UPDATE doctors SET phone = '(555) 444-1212', specialty = 'Cardiology', license_number = 'LIC-1' WHERE id = $1",
                self.ids["doctor"],
            )
            await conn.execute("UPDATE doctors SET phone = '555-777-8888' WHERE id = $1", other_doctor)
            gone_user = await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'gone@example.test', 'x', 'DOCTOR') RETURNING id",
                self.ids["tenant"],
            )
            await conn.execute(
                "INSERT INTO doctors (tenant_id, user_id, full_name, phone, deleted_at) VALUES ($1, $2, 'Dr Gone', '5554441212', now())",
                self.ids["tenant"], gone_user,
            )
        finally:
            await conn.close()

        async def search(q: str) -> list[dict]:
            async with self.sessions() as s:
                return await support_search_doctors(q=q, identity=self.staff(), db=s)

        self.assertEqual([d["name"] for d in await search("dr")], ["Dr Other", "Dr Test"])
        self.assertEqual([d["name"] for d in await search("444-12")], ["Dr Test"])  # formatting ignored, deleted doctor hidden
        self.assertEqual([d["name"] for d in await search("7778888")], ["Dr Other"])
        hit = (await search("Dr Test"))[0]
        self.assertEqual(
            (hit["id"], hit["specialty"], hit["license_number"], hit["email"]),
            (self.ids["doctor"], "Cardiology", "LIC-1", "doc@example.test"),
        )
        with self.assertRaises(HTTPException) as ctx:
            await search("d")
        self.assertEqual(ctx.exception.status_code, 422)

    async def test_support_staff_blocks_and_unblocks_a_doctors_slot(self):
        await self._register_support_staff()
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        slot = local(timeutils.clinic_today() + timedelta(days=2), 15)

        async def change(available: bool, identity, doctor_id=None):
            payload = UpsertDoctorAvailabilityRequest(slot=slot.isoformat(), is_available=available, block_reason="Staff meeting", doctor_id=doctor_id)
            async with self.sessions() as s:
                return await upsert_doctor_availability(payload=payload, identity=identity, db=s)

        await change(False, self.staff(), self.ids["doctor"])
        self.assertEqual(await self._slot_status(self.ids["doctor"], slot), "BLOCKED")
        await change(True, self.staff(), self.ids["doctor"])
        self.assertEqual(await self._slot_status(self.ids["doctor"], slot), "AVAILABLE")

        cases = [
            (self.staff(), None, 422),  # support staff must name the doctor
            (self.identity("patient1", "PATIENT"), self.ids["doctor"], 403),
        ]
        for identity, doctor_id, expected in cases:
            with self.subTest(role=identity.role):
                with self.assertRaises(HTTPException) as ctx:
                    await change(False, identity, doctor_id)
                self.assertEqual(ctx.exception.status_code, expected)
        self.assertEqual(await self._slot_status(self.ids["doctor"], slot), "AVAILABLE")

    async def test_slot_changes_by_path_respect_doctor_ownership_and_bookings(self):
        async with self.sessions() as s:
            await ensure_default_slots(s, await self.doctor(s))
        other_doctor = await self._second_doctor()
        day = timeutils.clinic_today() + timedelta(days=2)
        booked = local(day, 16)
        await self._book("patient1", booked)

        async def change(doctor_id: str, identity, when: datetime):
            payload = UpsertAvailabilityRequest(slot_time=when.isoformat(), is_available=False)
            async with self.sessions() as s:
                return await upsert_availability(doctor_id=doctor_id, payload=payload, identity=identity, db=s)

        cases = [
            (other_doctor, self.identity("doctor", "DOCTOR"), local(day, 17), 403),  # another doctor's slots
            (self.ids["doctor"], self.identity("patient1", "PATIENT"), local(day, 17), 403),
            (self.ids["doctor"], self.identity("doctor", "DOCTOR"), booked, 400),  # patient-booked slot
        ]
        for doctor_id, identity, when, expected in cases:
            with self.subTest(expected=expected, role=identity.role):
                with self.assertRaises(HTTPException) as ctx:
                    await change(doctor_id, identity, when)
                self.assertEqual(ctx.exception.status_code, expected)

        await change(self.ids["doctor"], self.identity("doctor", "DOCTOR"), local(day, 17))  # own free slot is fine
        self.assertEqual(await self._slot_status(self.ids["doctor"], local(day, 17)), "BLOCKED")
        self.assertEqual(await self._slot_status(self.ids["doctor"], booked), "BOOKED")


if __name__ == "__main__":
    unittest.main()
