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
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.datastructures import Headers

from backend.app.api.routes import patient as patient_routes
from backend.app.api.routes.admin import admin_create_user, soft_delete_user
from backend.app.api.routes.audit_logs import list_audit_logs
from backend.app.api.routes.appointments import (
    CreateAppointmentRequest,
    confirm_appointment,
    create_appointment,
    delete_appointment,
    list_all_appointments,
)
from backend.app.api.routes.auth import LoginRequest, login
from backend.app.api.routes.doctor import (
    AdminRegisterRequest,
    DoctorRegisterRequest,
    UpsertDoctorAvailabilityRequest,
    doctor_all_appointments,
    doctor_get_appointment_details,
    list_doctors,
    register_admin,
    register_doctor,
    update_doctor_profile,
    upsert_doctor_availability,
)
from backend.app.api.routes.documents import create_document, list_documents
from backend.app.api.routes.medical_records import (
    CreateMedicalRecordRequest,
    create_medical_record,
    get_medical_record_by_appointment,
)
from backend.app.api.routes.prescriptions import CreatePrescriptionRequest, create_prescription, get_prescription
from backend.app.api.routes.support import support_list_appointments, support_search_doctors
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

    async def fetchrow(self, sql: str, *args):
        conn = await self.db.connect()
        try:
            return await conn.fetchrow(sql, *args)
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

    async def test_s8_patient_profile_update_cannot_change_the_login_email(self):
        payload = {"fullName": "Patient One", "phone": "555-010-2030", "email": "admin@example.test"}
        async with self.sessions() as s:
            await patient_routes.update_patient_profile(payload=payload, identity=self.identity("patient1", "PATIENT"), db=s)
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

    # --- S11 + S15: availability endpoint -------------------------------------------------------------

    async def test_s11_availability_endpoint_enforces_the_change_window_and_audits(self):
        doctor = self.identity("doctor", "DOCTOR")
        past = (datetime.now(UTC) - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
        far = (datetime.now(UTC) + timedelta(days=45)).replace(minute=0, second=0, microsecond=0)
        for when in (past, far):
            async with self.sessions() as s:
                await self.expect_status(400, upsert_doctor_availability(
                    payload=UpsertDoctorAvailabilityRequest(slot=when.isoformat(), is_available=False), identity=doctor, db=s,
                ))
        soon = local(timeutils.clinic_today(NY) + timedelta(days=3), 9)
        async with self.sessions() as s:
            await upsert_doctor_availability(
                payload=UpsertDoctorAvailabilityRequest(slot=soon.isoformat(), is_available=False), identity=doctor, db=s,
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

    # --- GAP-02: only the appointment's own doctor confirms it ---------------------------------------

    async def test_gap02_only_the_owning_doctor_confirms_an_appointment(self):
        appointment_id = await self.book("patient1", 15)
        async with self.sessions() as s:
            error = await self.expect_status(403, confirm_appointment(appointment_id=appointment_id, identity=self.identity("doctor2", "DOCTOR"), db=s))
        self.assertEqual(error.detail, "Not allowed to change this appointment.")
        self.assertEqual(await self.fetchval("SELECT status::text FROM appointments WHERE id = $1", appointment_id), "SCHEDULED")
        async with self.sessions() as s:
            await confirm_appointment(appointment_id=appointment_id, identity=self.identity("doctor", "DOCTOR"), db=s)
        self.assertEqual(await self.fetchval("SELECT status::text FROM appointments WHERE id = $1", appointment_id), "CONFIRMED")

    # --- GAP-03: doctors awaiting approval aren't listed or bookable ----------------------------------

    async def test_gap03_deactivated_doctors_are_not_listed_or_bookable(self):
        await self.fetchval("UPDATE users SET is_active = false WHERE id = $1 RETURNING id", self.ids["doctor2_user"])
        async with self.sessions() as s:
            names = [d["name"] for d in await list_doctors(identity=self.identity("patient1", "PATIENT"), db=s)]
        self.assertEqual(names, ["Dr Test"])

        with self.assertRaises(HTTPException) as ctx:
            await self.book("patient1", 16, doctor="doctor2")
        self.assertEqual((ctx.exception.status_code, ctx.exception.detail), (409, "This doctor isn't accepting appointments."))
        self.assertEqual(await self.fetchval("SELECT count(*) FROM appointments WHERE doctor_id = $1", self.ids["doctor2"]), 0)

        # Support staff still find them (to manage existing appointments), flagged as inactive
        staff = SimpleNamespace(user_id=self.ids["admin_user"], tenant_id=self.ids["tenant"], role="SUPPORT_STAFF", clinic_tz=NY)
        async with self.sessions() as s:
            found = {d["name"]: d["is_active"] for d in await support_search_doctors(q="*", identity=staff, db=s)}
        self.assertEqual(found, {"Dr Second": False, "Dr Test": True})

        # Once an admin activates the doctor, booking works
        await self.fetchval("UPDATE users SET is_active = true WHERE id = $1 RETURNING id", self.ids["doctor2_user"])
        self.assertTrue(await self.book("patient1", 16, doctor="doctor2"))

    async def test_gap03_unknown_or_other_clinic_doctors_are_not_found(self):
        other_user = await self.fetchval(
            "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, 'far@example.test', 'x', 'DOCTOR') RETURNING id", self.ids["other_tenant"],
        )
        other_doctor = str(await self.fetchval(
            "INSERT INTO doctors (tenant_id, user_id, full_name) VALUES ($1, $2, 'Dr Far') RETURNING id", self.ids["other_tenant"], other_user,
        ))
        slot = local(timeutils.clinic_today(NY) + timedelta(days=2), 10)
        payload = CreateAppointmentRequest(doctor_id=other_doctor, slot=slot.isoformat(), reason="Regular checkup")
        async with self.sessions() as s:
            error = await self.expect_status(404, create_appointment(payload=payload, identity=self.identity("patient1", "PATIENT"), db=s))
        self.assertEqual(error.detail, "Doctor not found.")

    # --- GAP-04: admin-created users are audited ----------------------------------------------------

    async def test_gap04_admin_created_users_get_an_audit_row_naming_the_admin(self):
        body = {"role": "PATIENT", "full_name": "Pat New", "email": "pat.new@example.test", "password": "Secret123",
                "phone": "555-123-4567", "gender": "Female", "date_of_birth": "1990-05-01"}
        async with self.sessions() as s:
            created = await admin_create_user(request=SimpleNamespace(json=AsyncMock(return_value=body)), identity=self.identity("admin", "ADMIN"), db=s)
        row = await self.fetchrow(
            "SELECT action_type, performed_by, new_data->>'email' AS email, new_data->>'role' AS role FROM audit_logs "
            "WHERE table_name = 'users' AND record_id = $1 AND performed_by = $2",
            created["id"], self.ids["admin_user"],
        )
        self.assertEqual((row["action_type"], row["email"], row["role"]), ("INSERT", "pat.new@example.test", "PATIENT"))
        # GAP-07: the gender is stored as the enum value whatever case the form sent
        self.assertEqual(await self.fetchval("SELECT gender FROM patients WHERE user_id = $1", created["id"]), "FEMALE")

    # --- GAP-05: soft delete records who deleted the login --------------------------------------------

    async def test_gap05_soft_delete_sets_deleted_by_on_the_user(self):
        async with self.sessions() as s:
            await soft_delete_user(user_id=self.ids["patient2_user"], identity=self.identity("admin", "ADMIN"), db=s)
        row = await self.fetchrow("SELECT deleted_at, deleted_by, is_active FROM users WHERE id = $1", self.ids["patient2_user"])
        self.assertIsNotNone(row["deleted_at"])
        self.assertEqual(str(row["deleted_by"]), self.ids["admin_user"])
        self.assertFalse(row["is_active"])

    # --- GAP-15: patient profile is validated and optional fields can be cleared -----------------------

    async def test_gap15_patient_profile_clears_optional_fields_and_rejects_bad_values(self):
        me = self.identity("patient1", "PATIENT")
        async with self.sessions() as s:
            await patient_routes.update_patient_profile(payload={"city": "Austin", "insuranceProvider": "Acme", "gender": "male"}, identity=me, db=s)
        self.assertEqual(
            tuple(await self.fetchrow("SELECT city, insurance_provider, gender FROM patients WHERE id = $1", self.ids["patient1"])),
            ("Austin", "Acme", "MALE"),
        )
        async with self.sessions() as s:  # an empty value clears it; an empty name or phone keeps the stored one
            await patient_routes.update_patient_profile(payload={"city": "", "insuranceProvider": "  ", "fullName": "", "phone": ""}, identity=me, db=s)
        row = await self.fetchrow("SELECT city, insurance_provider, full_name FROM patients WHERE id = $1", self.ids["patient1"])
        self.assertEqual((row["city"], row["insurance_provider"], row["full_name"]), (None, None, "Patient 1"))

        for bad in ({"phone": "12345"}, {"fullName": "Al"}, {"gender": "unknown"}, {"dateOfBirth": "2999-01-01"}, {"city": "x" * 101}):
            async with self.sessions() as s:
                await self.expect_status(422, patient_routes.update_patient_profile(payload=bad, identity=me, db=s))
        self.assertEqual(await self.fetchval("SELECT full_name FROM patients WHERE id = $1", self.ids["patient1"]), "Patient 1")

    # --- GAP-16: doctor profile is validated and trimmed -----------------------------------------------

    async def test_gap16_doctor_profile_is_validated_and_trimmed(self):
        doctor = self.identity("doctor", "DOCTOR")
        async with self.sessions() as s:
            await update_doctor_profile(payload={"fullName": "  Dr Test Renamed ", "phone": "555-123-4567", "specialty": " Cardiology "}, identity=doctor, db=s)
        row = await self.fetchrow("SELECT full_name, phone, specialty FROM doctors WHERE id = $1", self.ids["doctor"])
        self.assertEqual(tuple(row), ("Dr Test Renamed", "555-123-4567", "Cardiology"))
        for bad in ({"phone": "123"}, {"fullName": "Dr"}, {"licenseNumber": "L" * 101}):
            async with self.sessions() as s:
                await self.expect_status(422, update_doctor_profile(payload=bad, identity=doctor, db=s))

    # --- GAP-17: bad audit-log date filters ----------------------------------------------------------------

    async def test_gap17_bad_audit_log_dates_are_a_422(self):
        async with self.sessions() as s:
            error = await self.expect_status(422, list_audit_logs(table="", date_from="yesterday", date_to="", identity=self.identity("admin", "ADMIN"), db=s))
        self.assertEqual(error.detail, "Invalid datetime format.")

    # --- GAP-18: support lists leave out deleted doctors ------------------------------------------------

    async def test_gap18_support_appointment_list_leaves_out_deleted_doctors(self):
        kept = await self.book("patient1", 9)
        dropped = await self.book("patient1", 10, doctor="doctor2")
        await self.fetchval("UPDATE doctors SET deleted_at = now() WHERE id = $1 RETURNING id", self.ids["doctor2"])
        staff = SimpleNamespace(user_id=self.ids["admin_user"], tenant_id=self.ids["tenant"], role="SUPPORT_STAFF", clinic_tz=NY)
        async with self.sessions() as s:
            ids = [r["id"] for r in await support_list_appointments(patient_id=self.ids["patient1"], doctor_id=None, identity=staff, db=s)]
        self.assertIn(kept, ids)
        self.assertNotIn(dropped, ids)

    # --- GAP-24: appointment ids must be UUIDs -------------------------------------------------------------

    async def test_gap24_non_uuid_appointment_ids_are_refused_before_the_database(self):
        doctor = self.identity("doctor", "DOCTOR")
        for bad in ("all", "x" * 36, "12345678-1234-1234-1234-12345678901z"):
            async with self.sessions() as s:
                error = await self.expect_status(400, doctor_get_appointment_details(appointment_id=bad, identity=doctor, db=s))
            self.assertEqual(error.detail, "Invalid appointment ID")
        appointment_id = await self.book("patient1", 11)
        async with self.sessions() as s:
            details = await doctor_get_appointment_details(appointment_id=appointment_id, identity=doctor, db=s)
        self.assertEqual(details["id"], appointment_id)

    # --- GAP-13: cancelled appointments can be listed ------------------------------------------------------

    async def test_gap13_cancelled_appointments_are_listed_on_request(self):
        kept = await self.book("patient1", 12)
        cancelled = await self.book("patient1", 13)
        async with self.sessions() as s:
            await delete_appointment(appointment_id=cancelled, identity=self.identity("patient1", "PATIENT"), db=s)
        patient = self.identity("patient1", "PATIENT")
        async with self.sessions() as s:
            default = {a["id"]: a["status"] for a in await list_all_appointments(include_cancelled=False, identity=patient, db=s)}
            with_cancelled = {a["id"]: a["status"] for a in await list_all_appointments(include_cancelled=True, identity=patient, db=s)}
        self.assertEqual(default, {kept: "SCHEDULED"})
        self.assertEqual(with_cancelled, {kept: "SCHEDULED", cancelled: "CANCELLED"})

        # The doctor's week shows it too, and other patients' lists never do
        week_day = timeutils.clinic_today(NY) + timedelta(days=2)
        async with self.sessions() as s:
            week = {a["id"]: a["status"] for a in await doctor_all_appointments(
                from_date=week_day, include_cancelled=True, identity=self.identity("doctor", "DOCTOR"), db=s,
            )}
            other = await list_all_appointments(include_cancelled=True, identity=self.identity("patient2", "PATIENT"), db=s)
        self.assertEqual(week.get(cancelled), "CANCELLED")
        self.assertEqual(other, [])

    # --- GAP-25: rate limits are shared by every instance ----------------------------------------------------

    async def test_gap25_failed_logins_are_counted_in_the_database(self):
        async def fail() -> int:
            async with self.sessions() as s:
                with self.assertRaises(HTTPException) as ctx:
                    await login(request=LoginRequest(email="Patient1@Example.test", password="wrong-password"), http_request=FAKE_HTTP, db=s)
            return ctx.exception.status_code

        for attempt in range(10):
            self.assertEqual(await fail(), 401, attempt)
            rate_limit.reset_all()  # a different Lambda instance each time: no in-process memory to rely on
        self.assertEqual(await fail(), 429)

        # Only hashes are stored, never the email or address itself
        stored = await self.fetchval("SELECT string_agg(key_hash, ',') FROM rate_limit_events WHERE limit_name = 'login-email'")
        self.assertNotIn("patient1", stored)
        self.assertEqual(len(stored.split(",")[0]), 64)

        # Old rows are cleaned up as new events are recorded
        await self.fetchval("UPDATE rate_limit_events SET created_at = now() - interval '2 hours' RETURNING 1")
        async with self.sessions() as s:
            await rate_limit.record(s, "register-ip", "203.0.113.50")
        self.assertEqual(await self.fetchval("SELECT count(*) FROM rate_limit_events WHERE created_at < now() - interval '1 hour'"), 0)

    async def test_gap25_reset_requests_are_limited_across_instances(self):
        from backend.app.api.routes.auth import ForgotPasswordRequest, forgot_password

        for _ in range(5):
            rate_limit.reset_all()
            async with self.sessions() as s:
                await forgot_password(request=ForgotPasswordRequest(email="nobody@example.test"), http_request=FAKE_HTTP, db=s)
        async with self.sessions() as s:
            await self.expect_status(429, forgot_password(request=ForgotPasswordRequest(email="nobody@example.test"), http_request=FAKE_HTTP, db=s))

    # --- Migration 009: gender values -----------------------------------------------------------------------

    async def test_migration_009_stores_gender_as_the_enum_value(self):
        await self.fetchval("UPDATE patients SET gender = 'Male' WHERE id = $1 RETURNING 1", self.ids["patient1"])
        await self.fetchval("UPDATE patients SET gender = 'prefer not to say' WHERE id = $1 RETURNING 1", self.ids["patient2"])
        await self.db.run_migration("009_rate_limits_and_gender_values.sql")  # idempotent: safe to run again
        self.assertEqual(await self.fetchval("SELECT gender FROM patients WHERE id = $1", self.ids["patient1"]), "MALE")
        self.assertEqual(await self.fetchval("SELECT gender FROM patients WHERE id = $1", self.ids["patient2"]), "PREFER_NOT_TO_SAY")


if __name__ == "__main__":
    unittest.main()
