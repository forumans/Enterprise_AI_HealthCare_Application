"""Row-level security (migration 007) and choosing the clinic at self-registration.

These tests connect as a non-superuser role that doesn't own the tables (like healthcare_user on RDS),
so PostgreSQL enforces the tenant policies. Run with HC_TEST_PG_ADMIN_URL pointing at a disposable server.
"""

from __future__ import annotations

import unittest
from datetime import timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.api.routes.admin import admin_list_users
from backend.app.api.routes.auth import LoginRequest, RegisterRequest, login, register
from backend.app.api.routes.doctor import admin_setup_status
from backend.app.api.routes.support import reschedule_queue
from backend.app.core import cross_tenant, rate_limit, timeutils
from backend.app.core.security import hash_password
from backend.app.middleware.request_context import RequestContext, reset_request_context, set_request_context
from backend.app.models import Patient, User
from backend.tests.integration._pg import FAKE_HTTP, TempDatabase, http_from, require_pg, seed_clinic


class RowLevelSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        require_pg()
        rate_limit.reset_all()
        cross_tenant._functions_available = False
        self.db = await TempDatabase().create(migrate=True)
        conn = await self.db.connect()
        try:
            self.ids = await seed_clinic(conn)
            await conn.execute("UPDATE tenants SET domain = 'clinic.test' WHERE id = $1", self.ids["tenant"])
            self.ids["other_tenant"] = str(await conn.fetchval("INSERT INTO tenants (name, domain) VALUES ('Other Clinic', 'other.test') RETURNING id"))
            self.ids["other_user"] = str(await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'other.patient@example.test', $2, 'PATIENT') RETURNING id",
                self.ids["other_tenant"], hash_password("OtherPass123"),
            ))
            self.ids["other_patient"] = str(await conn.fetchval(
                "INSERT INTO patients (tenant_id, user_id, full_name) VALUES ($1, $2, 'Other Patient') RETURNING id",
                self.ids["other_tenant"], self.ids["other_user"],
            ))
        finally:
            await conn.close()
        self.engine = create_async_engine(await self.db.app_role_url(), poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def asyncTearDown(self):
        await self.engine.dispose()
        await self.db.drop()

    def acting_as(self, tenant_id: str, user_id: str = "00000000-0000-0000-0000-000000000001"):
        """Simulate the JWT middleware: the request's verified tenant and user."""
        token = set_request_context(RequestContext(request_id="test", tenant_id=tenant_id, user_id=user_id, role="ADMIN"))
        self.addCleanup(reset_request_context, token)

    # --- isolation inside PostgreSQL ------------------------------------------------------------------

    async def test_a_query_without_a_tenant_filter_still_sees_only_its_own_tenant(self):
        self.acting_as(self.ids["tenant"], self.ids["admin_user"])
        async with self.sessions() as s:
            names = (await s.execute(select(Patient.full_name))).scalars().all()  # deliberately no tenant filter
        self.assertEqual(sorted(names), ["Patient 1", "Patient 2"])

    async def test_with_no_signed_in_tenant_the_tables_look_empty(self):
        async with self.sessions() as s:
            self.assertEqual((await s.execute(text("SELECT count(*) FROM users"))).scalar(), 0)
            self.assertEqual((await s.execute(text("SELECT count(*) FROM patients"))).scalar(), 0)

    async def test_rows_cannot_be_written_into_another_tenant(self):
        self.acting_as(self.ids["tenant"], self.ids["admin_user"])
        async with self.sessions() as s:
            s.add(Patient(tenant_id=self.ids["other_tenant"], user_id=self.ids["other_user"], full_name="Smuggled"))
            with self.assertRaises(DBAPIError) as ctx:
                await s.flush()
        self.assertIn("row-level security", str(ctx.exception.orig))

    async def test_another_tenants_rows_cannot_be_updated_by_id(self):
        self.acting_as(self.ids["tenant"], self.ids["admin_user"])
        async with self.sessions() as s:
            result = await s.execute(text("UPDATE patients SET full_name = 'Hijacked' WHERE id = :id"), {"id": self.ids["other_patient"]})
            await s.commit()
        self.assertEqual(result.rowcount, 0)
        conn = await self.db.connect()
        try:
            self.assertEqual(await conn.fetchval("SELECT full_name FROM patients WHERE id = $1", self.ids["other_patient"]), "Other Patient")
        finally:
            await conn.close()

    async def test_admin_user_list_runs_under_rls(self):
        self.acting_as(self.ids["tenant"], self.ids["admin_user"])
        identity = SimpleNamespace(user_id=self.ids["admin_user"], tenant_id=self.ids["tenant"], role="ADMIN")
        async with self.sessions() as s:
            emails = {row["email"] for row in await admin_list_users(page=1, page_size=50, identity=identity, db=s)}
        self.assertIn("patient1@example.test", emails)
        self.assertNotIn("other.patient@example.test", emails)

    async def _flagged_appointment(self, tenant_id: str, user_id: str, patient_id: str, hours_ahead: int) -> str:
        """A booked slot inside a range block, with its appointment (written as the table owner)."""
        when = (timeutils.utc_now() + timedelta(hours=hours_ahead)).replace(minute=0, second=0, microsecond=0)
        conn = await self.db.connect()
        try:
            doctor_id = await conn.fetchval(
                "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Blocked') RETURNING id", tenant_id, user_id
            )
            block_id = await conn.fetchval(
                "INSERT INTO schedule_blocks (tenant_id, doctor_id, start_time, end_time, reason_category) "
                "VALUES ($1, $2, $3, $4, 'SICK') RETURNING id",
                tenant_id, doctor_id, when, when + timedelta(hours=1),
            )
            await conn.execute(
                "INSERT INTO doctor_availability (tenant_id, doctor_id, slot_time, status, block_id) VALUES ($1, $2, $3, 'AVAILABLE', $4)",
                tenant_id, doctor_id, when, block_id,
            )
            return str(await conn.fetchval(
                "INSERT INTO appointments (tenant_id, doctor_id, patient_id, appointment_time) VALUES ($1, $2, $3, $4) RETURNING id",
                tenant_id, doctor_id, patient_id, when,
            ))
        finally:
            await conn.close()

    async def test_reschedule_queue_lists_only_its_own_clinic(self):
        mine = await self._flagged_appointment(self.ids["tenant"], self.ids["admin_user"], self.ids["patient1"], 30)
        await self._flagged_appointment(self.ids["other_tenant"], self.ids["other_user"], self.ids["other_patient"], 40)
        self.acting_as(self.ids["tenant"], self.ids["admin_user"])
        identity = SimpleNamespace(user_id=self.ids["admin_user"], tenant_id=self.ids["tenant"], role="SUPPORT_STAFF")
        async with self.sessions() as s:
            queue = await reschedule_queue(doctor_id=None, identity=identity, db=s)
        self.assertEqual([item["id"] for item in queue], [mine])
        self.assertEqual(queue[0]["reason_label"], "Sick")

    # --- the narrow cross-tenant lookups ----------------------------------------------------------------

    async def test_login_finds_an_account_in_any_tenant_and_scopes_the_session_to_it(self):
        async with self.sessions() as s:
            reply = await login(request=LoginRequest(email="Other.Patient@example.test", password="OtherPass123"), http_request=FAKE_HTTP, db=s)
            self.assertEqual(reply["tenant_id"], self.ids["other_tenant"])
            # The rest of the request sees that tenant only (the patient's name came through RLS)
            self.assertEqual(reply["user_name"], "Other Patient")
            self.assertEqual((await s.execute(select(User.email))).scalars().all(), ["other.patient@example.test"])

    async def test_email_uniqueness_is_checked_across_tenants(self):
        async with self.sessions() as s:
            self.assertTrue(await cross_tenant.email_in_use(s, "other.patient@example.test", self.ids["tenant"]))
            self.assertFalse(await cross_tenant.email_in_use(s, "nobody@example.test", self.ids["tenant"]))

    async def test_setup_status_sees_admins_of_every_tenant(self):
        async with self.sessions() as s:
            self.assertEqual(await admin_setup_status(db=s), {"setup_required": False})

    # --- choosing the clinic at self-registration (F8) -----------------------------------------------

    async def _register(self, email: str, request) -> None:
        payload = RegisterRequest(full_name="New Patient", email=email, password="NewPass1234")
        async with self.sessions() as s:
            await register(request=payload, http_request=request, db=s)

    async def _tenant_of(self, email: str) -> str:
        conn = await self.db.connect()
        try:
            return str(await conn.fetchval("SELECT tenant_id FROM users WHERE email = $1", email))
        finally:
            await conn.close()

    async def test_registration_joins_the_clinic_whose_address_the_browser_was_on(self):
        await self._register("a@example.test", http_from("clinic.test"))
        await self._register("b@example.test", http_from("Other.Test"))
        self.assertEqual(await self._tenant_of("a@example.test"), self.ids["tenant"])
        self.assertEqual(await self._tenant_of("b@example.test"), self.ids["other_tenant"])

    async def test_registration_is_refused_when_the_clinic_cannot_be_told_apart(self):
        for request in (FAKE_HTTP, http_from("unknown.example")):
            with self.assertRaises(HTTPException) as ctx:
                await self._register("c@example.test", request)
            self.assertEqual(ctx.exception.status_code, 400)
        conn = await self.db.connect()
        try:
            self.assertIsNone(await conn.fetchval("SELECT id FROM users WHERE email = 'c@example.test'"))
        finally:
            await conn.close()


class SingleClinicRegistrationTests(unittest.IsolatedAsyncioTestCase):
    """A deployment with one clinic needs no domain configuration."""

    async def asyncSetUp(self):
        require_pg()
        rate_limit.reset_all()
        self.db = await TempDatabase().create(migrate=True)
        conn = await self.db.connect()
        try:
            self.ids = await seed_clinic(conn)
        finally:
            await conn.close()
        self.engine = create_async_engine(await self.db.app_role_url(), poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def asyncTearDown(self):
        await self.engine.dispose()
        await self.db.drop()

    async def test_registration_joins_the_only_clinic_from_any_address(self):
        payload = RegisterRequest(full_name="Solo Patient", email="solo@example.test", password="SoloPass123")
        async with self.sessions() as s:
            await register(request=payload, http_request=http_from("anything.example"), db=s)
        conn = await self.db.connect()
        try:
            self.assertEqual(str(await conn.fetchval("SELECT tenant_id FROM users WHERE email = 'solo@example.test'")), self.ids["tenant"])
            # The patient profile and the audit entries were written under RLS for that tenant
            self.assertEqual(await conn.fetchval("SELECT count(*) FROM patients WHERE full_name = 'Solo Patient'"), 1)
        finally:
            await conn.close()


if __name__ == "__main__":
    unittest.main()
