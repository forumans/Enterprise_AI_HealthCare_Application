"""PostgreSQL integration tests for the access-control, audit and upload safeguards.

Each test is tagged with the safeguard it covers (S1, S2, ...): admin bootstrap, document/record/prescription
ownership, upload limits, tenant endpoints, availability window, audit entries and delete protections.
Run with HC_TEST_PG_ADMIN_URL pointing at a disposable server.
"""

from __future__ import annotations

import io
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.datastructures import Headers

from backend.app.api.routes import patient as patient_routes
from backend.app.api.routes.admin import soft_delete_user
from backend.app.api.routes.appointments import CreateAppointmentRequest, create_appointment
from backend.app.api.routes.auth import LoginRequest, login
from backend.app.api.routes.doctor import (
    AdminRegisterRequest,
    DoctorRegisterRequest,
    UpsertAvailabilityRequest,
    register_admin,
    register_doctor,
    update_doctor_profile,
    upsert_availability,
)
from backend.app.api.routes.documents import create_document, list_documents
from backend.app.api.routes.medical_records import (
    CreateMedicalRecordRequest,
    create_medical_record,
    get_medical_record_by_appointment,
)
from backend.app.api.routes.prescriptions import CreatePrescriptionRequest, create_prescription, get_prescription
from backend.app.api.routes.tenants import get_tenant
from backend.app.core import rate_limit, storage, timeutils
from backend.app.main import app
from backend.app.models import Doctor
from backend.app.services.availability_service import ensure_default_slots
from backend.tests.integration._pg import CLINIC_TZ, FAKE_HTTP, TempDatabase, http_from, require_pg, seed_clinic

NY = ZoneInfo(CLINIC_TZ)


def local(day, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=NY).astimezone(UTC)


def upload(name: str, content_type: str, data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=name, headers=Headers({"content-type": content_type}))


class HardeningTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        require_pg()
        rate_limit.reset_all()
        self.db = await TempDatabase().create(migrate=True)
        conn = await self.db.connect()
        try:
            self.ids = await seed_clinic(conn)
            t = self.ids["tenant"]
            await conn.execute("UPDATE tenants SET domain = 'clinic.test' WHERE id = $1", t)
            await conn.execute("INSERT INTO admins (tenant_id, user_id, full_name) VALUES ($1, $2, 'Ada Admin')", t, self.ids["admin_user"])
            self.ids["doctor2_user"] = str(await conn.fetchval(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'doc2@example.test', 'x', 'DOCTOR') RETURNING id", t,
            ))
            self.ids["doctor2"] = str(await conn.fetchval(
                "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Second') RETURNING id", t, self.ids["doctor2_user"],
            ))
            self.ids["pharmacy"] = str(await conn.fetchval("INSERT INTO pharmacies (tenant_id, name) VALUES ($1, 'Main St Pharmacy') RETURNING id", t))
            self.ids["other_tenant"] = str(await conn.fetchval("INSERT INTO tenants (name, domain) VALUES ('Other Clinic', 'other.test') RETURNING id"))
            self.ids["other_pharmacy"] = str(await conn.fetchval(
                "INSERT INTO pharmacies (tenant_id, name) VALUES ($1, 'Elsewhere Pharmacy') RETURNING id", self.ids["other_tenant"],
            ))
        finally:
            await conn.close()
        self.engine = create_async_engine(self.db.sqlalchemy_url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def asyncTearDown(self):
        await self.engine.dispose()
        await self.db.drop()

    def identity(self, who: str, role: str):
        return SimpleNamespace(user_id=self.ids[f"{who}_user"], tenant_id=self.ids["tenant"], role=role, clinic_tz=NY)

    async def fetchval(self, sql: str, *args):
        conn = await self.db.connect()
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    async def book(self, who: str, hour: int, day_offset: int = 2, doctor: str = "doctor") -> str:
        async with self.sessions() as s:
            await ensure_default_slots(s, (await s.execute(select(Doctor).where(Doctor.id == self.ids[doctor]))).scalar_one(), NY)
        slot = local(timeutils.clinic_today(NY) + timedelta(days=day_offset), hour)
        payload = CreateAppointmentRequest(doctor_id=self.ids[doctor], slot=slot.isoformat(), reason="Regular checkup")
        async with self.sessions() as s:
            return (await create_appointment(payload=payload, identity=self.identity(who, "PATIENT"), db=s))["id"]

    async def confirmed(self, who: str, hour: int, day_offset: int = 2) -> str:
        appointment_id = await self.book(who, hour, day_offset)
        await self.fetchval("UPDATE appointments SET status = 'CONFIRMED' WHERE id = $1 RETURNING id", appointment_id)
        return appointment_id

    async def record_for(self, appointment_id: str, who: str = "doctor") -> str:
        payload = CreateMedicalRecordRequest(appointment_id=appointment_id, diagnosis="Flu", notes="Fever and cough")
        async with self.sessions() as s:
            return (await create_medical_record(payload=payload, identity=self.identity(who, "DOCTOR"), db=s))["id"]

    async def expect_status(self, code: int, coro):
        with self.assertRaises(HTTPException) as ctx:
            await coro
        self.assertEqual(ctx.exception.status_code, code, ctx.exception.detail)
        return ctx.exception

    # --- S1: admin bootstrap ------------------------------------------------------------------------

    async def test_s1_admin_bootstrap_is_refused_once_an_admin_exists(self):
        payload = AdminRegisterRequest(full_name="Mallory", email="mallory@example.test", password="Takeover123")
        async with self.sessions() as s:
            await self.expect_status(403, register_admin(payload=payload, http_request=FAKE_HTTP, db=s))
        self.assertIsNone(await self.fetchval("SELECT id FROM users WHERE email = 'mallory@example.test'"))

    async def test_s1_bootstrap_creates_the_first_admin_with_a_profile(self):
        await self.fetchval("UPDATE users SET is_active = false WHERE id = $1 RETURNING id", self.ids["admin_user"])
        payload = AdminRegisterRequest(full_name="First Admin", email="first@example.test", password="Bootstrap123")
        async with self.sessions() as s:
            await register_admin(payload=payload, http_request=http_from("clinic.test"), db=s)
        user_id = await self.fetchval("SELECT id FROM users WHERE email = 'first@example.test' AND role = 'ADMIN'")
        self.assertEqual(await self.fetchval("SELECT full_name FROM admins WHERE user_id = $1", user_id), "First Admin")

    # --- S17: doctor self-registration needs activation ---------------------------------------------

    async def test_s17_self_registered_doctors_cannot_sign_in_until_activated(self):
        payload = DoctorRegisterRequest(full_name="Dr New", email="new.doc@example.test", password="Doctor1234")
        async with self.sessions() as s:
            reply = await register_doctor(payload=payload, http_request=http_from("clinic.test"), db=s)
        self.assertIn("administrator must activate", reply["message"])
        self.assertFalse(await self.fetchval("SELECT is_active FROM users WHERE email = 'new.doc@example.test'"))
        async with self.sessions() as s:
            await self.expect_status(401, login(request=LoginRequest(email="new.doc@example.test", password="Doctor1234"), http_request=FAKE_HTTP, db=s))

    # --- S2 + S13: documents ------------------------------------------------------------------------

    async def test_s2_patients_reach_only_their_own_documents(self):
        with patch.object(storage, "upload_document", return_value="key"), patch.object(storage, "generate_presigned_url", return_value="https://signed"):
            async with self.sessions() as s:
                await create_document(
                    patient_id=self.ids["patient1"], file=upload("scan.pdf", "application/pdf", b"%PDF"), identity=self.identity("patient1", "PATIENT"), db=s,
                )
            async with self.sessions() as s:
                self.assertEqual(len(await list_documents(patient_id=self.ids["patient1"], identity=self.identity("patient1", "PATIENT"), db=s)), 1)
            async with self.sessions() as s:
                await self.expect_status(404, list_documents(patient_id=self.ids["patient1"], identity=self.identity("patient2", "PATIENT"), db=s))
            async with self.sessions() as s:
                await self.expect_status(404, create_document(
                    patient_id=self.ids["patient1"], file=upload("x.pdf", "application/pdf", b"%PDF"), identity=self.identity("patient2", "PATIENT"), db=s,
                ))
            async with self.sessions() as s:  # clinical staff still can
                self.assertEqual(len(await list_documents(patient_id=self.ids["patient1"], identity=self.identity("doctor", "DOCTOR"), db=s)), 1)

    async def test_s13_uploads_are_type_and_size_limited_and_names_sanitized(self):
        me = self.identity("patient1", "PATIENT")
        with patch.object(storage, "upload_document", return_value="key") as stored:
            async with self.sessions() as s:
                await self.expect_status(415, create_document(patient_id=self.ids["patient1"], file=upload("a.html", "text/html", b"<script>"), identity=me, db=s))
            with patch.object(storage, "settings", SimpleNamespace(max_upload_size=10, s3_bucket_name="b")):
                async with self.sessions() as s:
                    await self.expect_status(413, create_document(
                        patient_id=self.ids["patient1"], file=upload("big.pdf", "application/pdf", b"x" * 11), identity=me, db=s,
                    ))
            async with self.sessions() as s:
                await create_document(
                    patient_id=self.ids["patient1"], file=upload("../../etc/pass wd<1>.pdf", "application/pdf", b"%PDF"), identity=me, db=s,
                )
        key = stored.call_args.args[1]
        self.assertTrue(key.startswith(f"documents/{self.ids['tenant']}/{self.ids['patient1']}/"))
        self.assertTrue(key.endswith("_pass_wd_1_.pdf"), key)

    async def test_s13_storage_errors_are_not_returned_to_the_client(self):
        with patch.object(storage, "upload_document", side_effect=RuntimeError("bucket arn:aws:s3:::secret-bucket denied")):
            async with self.sessions() as s:
                error = await self.expect_status(500, create_document(
                    patient_id=self.ids["patient1"], file=upload("a.pdf", "application/pdf", b"%PDF"), identity=self.identity("patient1", "PATIENT"), db=s,
                ))
        self.assertNotIn("secret-bucket", error.detail)

    # --- S3 + F1: medical records -------------------------------------------------------------------

    async def test_f1_the_record_attaches_to_the_consulted_appointment(self):
        consulted = await self.confirmed("patient1", 9, day_offset=2)
        await self.book("patient1", 15, day_offset=4)  # a later appointment with the same doctor
        record_id = await self.record_for(consulted)
        self.assertEqual(str(await self.fetchval("SELECT appointment_id FROM medical_records WHERE id = $1", record_id)), consulted)

    async def test_f1_only_the_owning_doctor_records_a_confirmed_appointment(self):
        scheduled = await self.book("patient1", 10)
        await self.expect_status(400, self.record_for(scheduled))
        confirmed = await self.confirmed("patient2", 11)
        await self.expect_status(404, self.record_for(confirmed, who="doctor2"))

    async def test_s3_medical_records_are_readable_only_by_their_patient_doctor_or_admin(self):
        appointment = await self.confirmed("patient1", 12)
        await self.record_for(appointment)

        async def read(who: str, role: str):
            async with self.sessions() as s:
                return await get_medical_record_by_appointment(appointment_id=appointment, identity=self.identity(who, role), db=s)

        self.assertEqual((await read("patient1", "PATIENT"))["diagnosis"], "Flu")
        self.assertEqual((await read("doctor", "DOCTOR"))["diagnosis"], "Flu")
        self.assertEqual((await read("admin", "ADMIN"))["diagnosis"], "Flu")
        await self.expect_status(404, read("patient2", "PATIENT"))
        await self.expect_status(404, read("doctor2", "DOCTOR"))

    async def test_s19_staff_reads_of_clinical_records_are_audited(self):
        appointment = await self.confirmed("patient1", 13)
        await self.record_for(appointment)
        async with self.sessions() as s:
            await get_medical_record_by_appointment(appointment_id=appointment, identity=self.identity("admin", "ADMIN"), db=s)
        reads = await self.fetchval(
            "SELECT count(*) FROM audit_logs WHERE action_type = 'READ' AND table_name = 'medical_records' AND performed_by = $1", self.ids["admin_user"],
        )
        self.assertEqual(reads, 1)

    # --- S4 + S5: prescriptions ---------------------------------------------------------------------

    async def test_s5_prescriptions_need_the_owning_doctor_and_a_clinic_pharmacy(self):
        record_id = await self.record_for(await self.confirmed("patient1", 14))

        async def prescribe(who: str, pharmacy: str | None = None):
            payload = CreatePrescriptionRequest(medical_record_id=record_id, medication_details="Rest - 1 week. Take as prescribed", pharmacy_id=pharmacy)
            async with self.sessions() as s:
                return await create_prescription(payload=payload, identity=self.identity(who, "DOCTOR"), db=s)

        await self.expect_status(404, prescribe("doctor2"))
        await self.expect_status(404, prescribe("doctor", self.ids["other_pharmacy"]))
        prescription_id = (await prescribe("doctor", self.ids["pharmacy"]))["id"]

        async def read(who: str):
            async with self.sessions() as s:
                return await get_prescription(prescription_id=prescription_id, identity=self.identity(who, "PATIENT"), db=s)

        self.assertEqual((await read("patient1"))["pharmacy_id"], self.ids["pharmacy"])
        await self.expect_status(404, read("patient2"))  # S4

    # --- S8: patients can't change their login email -------------------------------------------------

    async def test_s8_patient_profile_patch_cannot_change_the_login_email(self):
        endpoint = next(r.endpoint for r in patient_routes.router.routes if r.path == "/patient/profile" and "PATCH" in r.methods)
        payload = patient_routes.UpdateProfileRequest.model_validate(
            {"full_name": "Patient One", "phone": "555-010-2030", "email": "admin@example.test"}
        )
        async with self.sessions() as s:
            await endpoint(payload=payload, identity=self.identity("patient1", "PATIENT"), db=s)
        self.assertEqual(await self.fetchval("SELECT email FROM users WHERE id = $1", self.ids["patient1_user"]), "patient1@example.test")
        self.assertEqual(await self.fetchval("SELECT full_name FROM patients WHERE id = $1", self.ids["patient1"]), "Patient One")

    # --- S9: tenants ----------------------------------------------------------------------------------

    async def test_s9_admins_see_only_their_own_tenant_and_cannot_create_tenants(self):
        async with self.sessions() as s:
            self.assertEqual((await get_tenant(tenant_id=self.ids["tenant"], identity=self.identity("admin", "ADMIN"), db=s))["name"], "Test Clinic")
        async with self.sessions() as s:
            await self.expect_status(404, get_tenant(tenant_id=self.ids["other_tenant"], identity=self.identity("admin", "ADMIN"), db=s))
        routes = {(r.path, m) for r in app.routes if hasattr(r, "methods") for m in r.methods}
        for path in ("/tenants", "/api/tenants"):
            self.assertNotIn((path, "POST"), routes)
        self.assertNotIn(("/api/tenants/debug", "GET"), routes)

    # --- S11 + S15: legacy availability endpoint ------------------------------------------------------

    async def test_s11_legacy_availability_endpoint_enforces_the_change_window_and_audits(self):
        doctor = self.identity("doctor", "DOCTOR")
        past = (datetime.now(UTC) - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
        far = (datetime.now(UTC) + timedelta(days=45)).replace(minute=0, second=0, microsecond=0)
        for when in (past, far):
            async with self.sessions() as s:
                await self.expect_status(400, upsert_availability(
                    doctor_id=self.ids["doctor"], payload=UpsertAvailabilityRequest(slot_time=when.isoformat(), is_available=False), identity=doctor, db=s,
                ))
        soon = local(timeutils.clinic_today(NY) + timedelta(days=3), 9)
        async with self.sessions() as s:
            await upsert_availability(
                doctor_id=self.ids["doctor"], payload=UpsertAvailabilityRequest(slot_time=soon.isoformat(), is_available=False), identity=doctor, db=s,
            )
        self.assertGreaterEqual(await self.fetchval(
            "SELECT count(*) FROM audit_logs WHERE table_name = 'doctor_availability' AND performed_by = $1 AND action_type IN ('INSERT', 'UPDATE')",
            self.ids["doctor_user"],
        ), 1)

    async def test_s15_doctor_profile_changes_are_audited(self):
        async with self.sessions() as s:
            await update_doctor_profile(payload={"specialty": "Cardiology"}, identity=self.identity("doctor", "DOCTOR"), db=s)
        new_data = await self.fetchval(
            "SELECT new_data::text FROM audit_logs WHERE table_name = 'doctors' AND performed_by = $1 AND action_type = 'UPDATE' ORDER BY performed_at DESC LIMIT 1",
            self.ids["doctor_user"],
        )
        self.assertIn("Cardiology", new_data)

    # --- S16: soft delete safeguards ------------------------------------------------------------------

    async def test_s16_admins_cannot_delete_themselves_or_the_last_active_admin(self):
        admin = self.identity("admin", "ADMIN")
        async with self.sessions() as s:
            await self.expect_status(400, soft_delete_user(user_id=self.ids["admin_user"], identity=admin, db=s))
        # Another (deactivated) admin's still-valid token can't delete the only active admin
        other_admin = str(await self.fetchval(
            "INSERT INTO users (tenant_id, email, password_hash, role, is_active) VALUES ($1, 'admin2@example.test', 'x', 'ADMIN', false) RETURNING id",
            self.ids["tenant"],
        ))
        async with self.sessions() as s:
            await self.expect_status(409, soft_delete_user(
                user_id=self.ids["admin_user"], identity=SimpleNamespace(user_id=other_admin, tenant_id=self.ids["tenant"], role="ADMIN"), db=s,
            ))
        self.assertIsNone(await self.fetchval("SELECT deleted_at FROM users WHERE id = $1", self.ids["admin_user"]))
        # Deleting a non-admin still works
        async with self.sessions() as s:
            await soft_delete_user(user_id=self.ids["patient2_user"], identity=admin, db=s)
        self.assertIsNotNone(await self.fetchval("SELECT deleted_at FROM users WHERE id = $1", self.ids["patient2_user"]))


if __name__ == "__main__":
    unittest.main()
