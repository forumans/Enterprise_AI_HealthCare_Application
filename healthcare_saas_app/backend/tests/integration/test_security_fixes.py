"""Regression tests for the security and correctness fixes (review items 1-9) against a real database.

1. appointment status changes: doctors (own) and admins only; cancelling goes through DELETE
2. appointment lists show patients/doctors only their own appointments
3. the doctor list and doctor availability are limited to the caller's clinic
5. deactivated, deleted or role-changed accounts lose access on their next request
6. restoring a soft-deleted user reactivates the login and the profile
7. self-service forgot/reset password with single-use, expiring links
8. an email can't be registered if another account (any clinic) already uses it
(4 - no personal data in logs - and 9 - no duplicate routes - are covered by database-free tests.)

Skipped unless HC_TEST_PG_ADMIN_URL is set (see _pg.py).
"""

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.api.routes import auth as auth_routes
from backend.app.api.routes.admin import admin_create_user, restore_user, soft_delete_user
from backend.app.api.routes.admin_password_reset import search_users
from backend.app.api.routes.appointments import (
    CreateAppointmentRequest,
    UpdateAppointmentStatusRequest,
    create_appointment,
    list_all_appointments,
    list_appointments,
    list_weekly_appointments,
    update_appointment_status,
)
from backend.app.api.routes.auth import ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest
from backend.app.api.routes.doctor import list_availability_next_30_days, list_doctors
from backend.app.core import timeutils
from backend.app.core.dependencies import SESSION_ENDED, get_current_identity
from backend.app.core.security import create_access_token, create_password_reset_token, hash_password
from backend.app.models import Doctor
from backend.app.services.availability_service import ensure_default_slots
from backend.tests.integration._pg import CLINIC_TZ, TempDatabase, require_pg, seed_clinic

NY = ZoneInfo(CLINIC_TZ)


def local(day, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=NY).astimezone(UTC)


class SecurityFixTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        require_pg()
        self._tz_patch = patch.object(timeutils, "CLINIC_TZ", NY)
        self._tz_patch.start()
        self.db = await TempDatabase().create(migrate=True)
        conn = await self.db.connect()
        try:
            self.ids = await seed_clinic(conn)
            # A second doctor (own login) and a second clinic with its own doctor
            self.ids["doctor2_user"] = str(await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'doc2@example.test', 'x', 'DOCTOR') RETURNING id",
                self.ids["tenant"],
            ))
            self.ids["doctor2"] = str(await conn.fetchval(
                "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Second') RETURNING id", self.ids["tenant"], self.ids["doctor2_user"],
            ))
            self.ids["other_tenant"] = str(await conn.fetchval("INSERT INTO tenants (name) VALUES ('Other Clinic') RETURNING id"))
            self.ids["other_doctor_user"] = str(await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'elsewhere@example.test', 'x', 'DOCTOR') RETURNING id",
                self.ids["other_tenant"],
            ))
            self.ids["other_doctor"] = str(await conn.fetchval(
                "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Elsewhere') RETURNING id",
                self.ids["other_tenant"], self.ids["other_doctor_user"],
            ))
            await conn.execute("INSERT INTO admins (tenant_id, user_id, full_name) VALUES ($1, $2, 'Ada Admin')", self.ids["tenant"], self.ids["admin_user"])
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

    async def _book(self, who: str, doctor: str, hour: int, day_offset: int = 2) -> str:
        async with self.sessions() as s:
            for doctor_id in (self.ids["doctor"], self.ids["doctor2"]):
                await ensure_default_slots(s, (await s.execute(select(Doctor).where(Doctor.id == doctor_id))).scalar_one())
        slot = local(timeutils.clinic_today() + timedelta(days=day_offset), hour)
        payload = CreateAppointmentRequest(doctor_id=self.ids[doctor], slot=slot.isoformat(), reason="Regular checkup")
        async with self.sessions() as s:
            return (await create_appointment(payload=payload, identity=self.identity(who, "PATIENT"), db=s))["id"]

    async def _status_of(self, appointment_id: str) -> tuple[str, bool]:
        conn = await self.db.connect()
        try:
            row = await conn.fetchrow("SELECT status, deleted_at IS NOT NULL AS deleted FROM appointments WHERE id = $1", appointment_id)
        finally:
            await conn.close()
        return row["status"], row["deleted"]

    # --- 1. appointment status ------------------------------------------------------------------

    async def test_1_only_the_owning_doctor_or_an_admin_changes_status(self):
        mine = await self._book("patient1", "doctor", 10)

        async def set_status(identity, value: str):
            async with self.sessions() as s:
                return await update_appointment_status(
                    appointment_id=mine, payload=UpdateAppointmentStatusRequest(status=value), identity=identity, db=s
                )

        with self.assertRaises(HTTPException) as ctx:  # another doctor in the clinic
            await set_status(self.identity("doctor2", "DOCTOR"), "COMPLETED")
        self.assertEqual(ctx.exception.status_code, 403)
        with self.assertRaises(HTTPException) as ctx:  # cancelling must use DELETE (soft delete + free slot)
            await set_status(self.identity("doctor", "DOCTOR"), "CANCELLED")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(await self._status_of(mine), ("SCHEDULED", False))

        await set_status(self.identity("doctor", "DOCTOR"), "COMPLETED")
        self.assertEqual(await self._status_of(mine), ("COMPLETED", False))
        await set_status(self.identity("admin", "ADMIN"), "CONFIRMED")
        self.assertEqual(await self._status_of(mine), ("CONFIRMED", False))

    # --- 2. appointment lists ---------------------------------------------------------------

    async def test_2_lists_show_patients_and_doctors_only_their_own_appointments(self):
        p1_d1 = await self._book("patient1", "doctor", 10)
        p2_d1 = await self._book("patient2", "doctor", 11)
        p2_d2 = await self._book("patient2", "doctor2", 12)
        everyone = {p1_d1, p2_d1, p2_d2}
        from_date = timeutils.clinic_today() + timedelta(days=2)

        cases = [
            (self.identity("patient1", "PATIENT"), {p1_d1}),
            (self.identity("patient2", "PATIENT"), {p2_d1, p2_d2}),
            (self.identity("doctor", "DOCTOR"), {p1_d1, p2_d1}),
            (self.identity("doctor2", "DOCTOR"), {p2_d2}),
            (self.identity("admin", "ADMIN"), everyone),
        ]
        for identity, expected in cases:
            with self.subTest(user=identity.user_id, role=identity.role):
                async with self.sessions() as s:
                    plain = {a["id"] for a in await list_appointments(identity=identity, db=s)}
                    full = {a["id"] for a in await list_all_appointments(identity=identity, db=s)}
                    week = {a["id"] for a in await list_weekly_appointments(from_date=from_date, identity=identity, db=s)}
                self.assertEqual(plain, expected)
                self.assertEqual(full, expected)
                self.assertEqual(week, expected)

        # A login with no patient/doctor profile sees nothing rather than everything
        stranger = SimpleNamespace(user_id=self.ids["admin_user"], tenant_id=self.ids["tenant"], role="PATIENT")
        async with self.sessions() as s:
            self.assertEqual(await list_appointments(identity=stranger, db=s), [])

    # --- 3. clinic boundaries -----------------------------------------------------------------

    async def test_3_doctor_list_and_availability_stay_within_the_clinic(self):
        async with self.sessions() as s:
            names = [d["name"] for d in await list_doctors(identity=self.identity("patient1", "PATIENT"), db=s)]
            await ensure_default_slots(s, (await s.execute(select(Doctor).where(Doctor.id == self.ids["other_doctor"]))).scalar_one())
            other_clinic_slots = await list_availability_next_30_days(
                doctor_id=self.ids["other_doctor"], identity=self.identity("patient1", "PATIENT"), db=s
            )
        self.assertEqual(names, ["Dr Second", "Dr Test"])  # no "Dr Elsewhere" from the other clinic
        self.assertEqual(other_clinic_slots, [])

    # --- 5. sessions end when the account changes --------------------------------------------------

    async def test_5_access_ends_on_the_next_request_after_deactivation_deletion_or_role_change(self):
        def request_for(who: str, role: str):
            return SimpleNamespace(state=SimpleNamespace(tenant_id=self.ids["tenant"], user_id=self.ids[f"{who}_user"], role=role))

        async def check(who: str, role: str):
            async with self.sessions() as s:
                return await get_current_identity(request_for(who, role), db=s)

        self.assertEqual((await check("patient1", "PATIENT")).role, "PATIENT")  # an active account passes

        conn = await self.db.connect()
        try:
            await conn.execute("UPDATE users SET is_active = false WHERE id = $1", self.ids["patient1_user"])
            await conn.execute("UPDATE users SET deleted_at = now() WHERE id = $1", self.ids["patient2_user"])
        finally:
            await conn.close()

        cases = [
            ("patient1", "PATIENT"),  # deactivated
            ("patient2", "PATIENT"),  # soft-deleted
            ("doctor", "ADMIN"),  # token claims a role the account doesn't have
        ]
        for who, role in cases:
            with self.subTest(who=who, role=role):
                with self.assertRaises(HTTPException) as ctx:
                    await check(who, role)
                self.assertEqual((ctx.exception.status_code, ctx.exception.detail), (401, SESSION_ENDED))

        wrong_clinic = SimpleNamespace(state=SimpleNamespace(tenant_id=self.ids["other_tenant"], user_id=self.ids["doctor_user"], role="DOCTOR"))
        async with self.sessions() as s:
            with self.assertRaises(HTTPException) as ctx:
                await get_current_identity(wrong_clinic, db=s)
        self.assertEqual(ctx.exception.status_code, 401)

    # --- 6. restore ------------------------------------------------------------------------------

    async def test_6_restore_brings_back_the_login_and_the_profile(self):
        admin = self.identity("admin", "ADMIN")
        async with self.sessions() as s:  # give patient1 a real password, then soft delete them
            await s.execute(text("UPDATE users SET password_hash = :h WHERE id = :id"),
                            {"h": hash_password("Secret12345"), "id": self.ids["patient1_user"]})
            await s.commit()
        async with self.sessions() as s:
            await soft_delete_user(user_id=self.ids["patient1_user"], identity=admin, db=s)

        async def can_log_in() -> bool:
            async with self.sessions() as s:
                try:
                    await auth_routes.login(request=LoginRequest(email="patient1@example.test", password="Secret12345"), db=s)
                    return True
                except HTTPException:
                    return False

        async def listed() -> bool:
            async with self.sessions() as s:
                return any(u["user_id"] == self.ids["patient1_user"] for u in await search_users(role="PATIENT", q="*", identity=admin, db=s))

        self.assertFalse(await can_log_in())
        self.assertFalse(await listed())

        async with self.sessions() as s:
            await restore_user(user_id=self.ids["patient1_user"], identity=admin, db=s)
        self.assertTrue(await can_log_in())
        self.assertTrue(await listed())

        with self.assertRaises(HTTPException) as ctx:  # restoring an account that isn't deleted
            async with self.sessions() as s:
                await restore_user(user_id=self.ids["patient1_user"], identity=admin, db=s)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_6_restore_is_refused_when_the_email_now_belongs_to_someone_else(self):
        admin = self.identity("admin", "ADMIN")
        async with self.sessions() as s:
            await soft_delete_user(user_id=self.ids["patient2_user"], identity=admin, db=s)
        conn = await self.db.connect()
        try:  # another clinic has since registered the same email
            await conn.execute(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'patient2@example.test', 'x', 'PATIENT')", self.ids["other_tenant"]
            )
        finally:
            await conn.close()
        with self.assertRaises(HTTPException) as ctx:
            async with self.sessions() as s:
                await restore_user(user_id=self.ids["patient2_user"], identity=admin, db=s)
        self.assertEqual(ctx.exception.status_code, 409)

    # --- 7. forgot / reset password ------------------------------------------------------------------

    async def test_7_forgot_and_reset_password_with_a_single_use_link(self):
        conn = await self.db.connect()
        try:
            await conn.execute("UPDATE users SET password_hash = $1 WHERE id = $2", hash_password("OldPass123"), self.ids["patient1_user"])
        finally:
            await conn.close()

        sender = AsyncMock(return_value=True)
        with patch.object(auth_routes, "send_email", sender):
            async with self.sessions() as s:
                unknown = await auth_routes.forgot_password(request=ForgotPasswordRequest(email="nobody@example.test"), db=s)
            self.assertFalse(sender.called)  # nothing sent, but...
            async with self.sessions() as s:
                known = await auth_routes.forgot_password(request=ForgotPasswordRequest(email="Patient1@Example.test"), db=s)
        self.assertEqual(unknown, known)  # ...the reply doesn't reveal which emails exist

        to, subject, body = sender.call_args.args
        self.assertEqual((to, subject), ("patient1@example.test", "Reset your password"))
        token = body.split("/reset-password?token=")[1].split()[0]

        async def reset(tok: str, password: str = "NewPass123"):
            async with self.sessions() as s:
                return await auth_routes.reset_password(request=ResetPasswordRequest(token=tok, new_password=password), db=s)

        async def can_log_in(password: str) -> bool:
            async with self.sessions() as s:
                try:
                    await auth_routes.login(request=LoginRequest(email="patient1@example.test", password=password), db=s)
                    return True
                except HTTPException:
                    return False

        await reset(token)
        self.assertTrue(await can_log_in("NewPass123"))
        self.assertFalse(await can_log_in("OldPass123"))

        async with self.sessions() as s:
            current_hash = (await s.execute(text("SELECT password_hash FROM users WHERE id = :id"), {"id": self.ids["patient1_user"]})).scalar_one()
        bad_tokens = {
            "reused (password already changed)": token,
            "expired": create_password_reset_token(user_id=self.ids["patient1_user"], password_hash=current_hash, expires_minutes=-1),
            "tampered": token[:-2] + ("AA" if not token.endswith("AA") else "BB"),
            "a login token": create_access_token(user_id=self.ids["patient1_user"], tenant_id=self.ids["tenant"], role="PATIENT"),
            "garbage": "not-a-token",
        }
        for label, bad in bad_tokens.items():
            with self.subTest(label):
                with self.assertRaises(HTTPException) as ctx:
                    await reset(bad, "Hijacked123")
                self.assertEqual(ctx.exception.status_code, 400)
        self.assertTrue(await can_log_in("NewPass123"))

    async def test_7_reset_links_are_not_issued_for_deactivated_accounts(self):
        conn = await self.db.connect()
        try:
            await conn.execute("UPDATE users SET is_active = false WHERE id = $1", self.ids["patient1_user"])
        finally:
            await conn.close()
        sender = AsyncMock(return_value=True)
        with patch.object(auth_routes, "send_email", sender):
            async with self.sessions() as s:
                await auth_routes.forgot_password(request=ForgotPasswordRequest(email="patient1@example.test"), db=s)
        self.assertFalse(sender.called)

    # --- 8. emails unique across clinics -----------------------------------------------------------

    async def test_8_new_accounts_cannot_take_an_email_used_in_any_clinic(self):
        # "elsewhere@example.test" is a doctor in the other clinic
        register = RegisterRequest(full_name="Copy Cat", email="Elsewhere@Example.test", password="Secret12345")
        with self.assertRaises(HTTPException) as ctx:
            async with self.sessions() as s:
                await auth_routes.register(request=register, db=s)
        self.assertEqual(ctx.exception.status_code, 409)

        body = {"role": "SUPPORT_STAFF", "full_name": "Copy Cat", "email": "elsewhere@example.test", "password": "Secret12345"}
        with self.assertRaises(HTTPException) as ctx:
            async with self.sessions() as s:
                await admin_create_user(request=SimpleNamespace(json=AsyncMock(return_value=body)), identity=self.identity("admin", "ADMIN"), db=s)
        self.assertEqual(ctx.exception.status_code, 409)

        body["email"] = "brand.new@example.test"  # a free email still works
        async with self.sessions() as s:
            created = await admin_create_user(request=SimpleNamespace(json=AsyncMock(return_value=body)), identity=self.identity("admin", "ADMIN"), db=s)
        self.assertTrue(created["id"])


if __name__ == "__main__":
    unittest.main()
