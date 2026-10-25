"""End-to-end HTTP tests: the real backend (uvicorn) against a throwaway, migrated PostgreSQL database.

Unlike test_core_flows (which calls route functions directly), these go through the whole stack -
JWT login, the tenant middleware, FastAPI role guards and request validation - so they catch
regressions in wiring as well as in logic. Covers support staff, admin account management
(search, change email, reset password, deactivate/activate) and the permission boundaries.

Skipped unless HC_TEST_PG_ADMIN_URL is set (see _pg.py). Starts uvicorn on a free local port.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import asyncpg
import jwt

from backend.app.core.security import hash_password
from backend.tests.integration._pg import CLINIC_TZ, TempDatabase, require_pg

APP_ROOT = Path(__file__).resolve().parents[3]  # healthcare_saas_app/ - the folder containing backend/
PASSWORD = "Password123"
JWT_SECRET = "http-flow-tests-secret-not-real-0123456789"  # the test server signs tokens with this


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class HttpFlowTests(unittest.TestCase):
    db: TempDatabase
    server: subprocess.Popen
    base: str

    @classmethod
    def setUpClass(cls):
        require_pg()
        cls.db = asyncio.run(TempDatabase().create(migrate=True))
        try:
            asyncio.run(cls._seed())
            port = _free_port()
            cls.base = f"http://127.0.0.1:{port}/api"
            env = {
                **os.environ,
                "DATABASE_URL": cls.db.sqlalchemy_url,
                "DB_SCHEMA_INIT_ON_STARTUP": "false",
                "JWT_SECRET": JWT_SECRET,
                "JWT_ALGORITHM": "HS256",
                "ACCESS_TOKEN_MINUTES": "60",
                "CORS_ORIGINS": "http://localhost:5173",
                "APP_ENV": "dev",
                "LOG_LEVEL": "WARNING",
                "MAX_UPLOAD_SIZE": "10485760",
                "CLINIC_TIMEZONE": CLINIC_TZ,
            }
            cls.server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", str(port), "--log-level", "warning"],
                cwd=APP_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            cls._wait_until_up()
        except BaseException:
            cls._cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls._cleanup()

    @classmethod
    def _cleanup(cls):
        server = getattr(cls, "server", None)
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        if getattr(cls, "db", None) is not None:
            asyncio.run(cls.db.drop())

    @classmethod
    def _wait_until_up(cls):
        for _ in range(120):
            try:
                urllib.request.urlopen(f"{cls.base}/health", timeout=2)
                return
            except Exception:
                if cls.server.poll() is not None:
                    raise RuntimeError(f"backend exited during startup:\n{cls.server.stderr.read()[-3000:]}")
                time.sleep(0.5)
        raise RuntimeError("backend did not start within 60s")

    @classmethod
    async def _seed(cls):
        password_hash = hash_password(PASSWORD)
        conn = await cls.db.connect()
        try:
            tenant = await conn.fetchval("INSERT INTO tenants (name) VALUES ('HTTP Clinic') RETURNING id")

            async def user(email: str, role: str):
                return await conn.fetchval(
                    "INSERT INTO users (tenant_id, email, password_hash, role) VALUES ($1, $2, $3, $4) RETURNING id",
                    tenant, email, password_hash, role,
                )

            admin = await user("admin@http.test", "ADMIN")
            await conn.execute("INSERT INTO admins (tenant_id, user_id, full_name) VALUES ($1, $2, 'Ada Admin')", tenant, admin)
            for email, name, phone in (("doc1@http.test", "Dr One", "555-0100"), ("doc2@http.test", "Dr Two", "(555) 0199")):
                await conn.execute(
                    "INSERT INTO doctors (tenant_id, user_id, full_name, phone) VALUES ($1, $2, $3, $4)", tenant, await user(email, "DOCTOR"), name, phone
                )
            for email, name, phone in (("steve@http.test", "Steve Works", "(555) 010-2030"), ("paula@http.test", "Paula Patient", "555-404-5050")):
                await conn.execute(
                    "INSERT INTO patients (tenant_id, user_id, full_name, phone, city) VALUES ($1, $2, $3, $4, 'Austin')",
                    tenant, await user(email, "PATIENT"), name, phone,
                )
        finally:
            await conn.close()

    # --- HTTP helpers --------------------------------------------------------------------------

    def call(self, method: str, path: str, token: str | None = None, body: dict | None = None) -> tuple[int, object]:
        request = urllib.request.Request(self.base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")

    def ok(self, method: str, path: str, token: str | None = None, body: dict | None = None, expected: int = 200):
        status, payload = self.call(method, path, token, body)
        self.assertEqual(status, expected, f"{method} {path} -> {status} {payload}")
        return payload

    def login_status(self, email: str, password: str = PASSWORD) -> int:
        return self.call("POST", "/auth/login", body={"email": email, "password": password})[0]

    def login(self, email: str, password: str = PASSWORD) -> str:
        return self.ok("POST", "/auth/login", body={"email": email, "password": password})["access_token"]

    def register_staff(self, admin: str, email: str, name: str = "Sam Support") -> str:
        """Register a support staff member via the admin API; returns their user id."""
        return self.ok("POST", "/admin/users", admin, {"role": "SUPPORT_STAFF", "full_name": name, "email": email, "password": PASSWORD, "phone": "5551234567"}, 201)["id"]

    def doctor_id(self, token: str, name: str) -> str:
        return next(d["id"] for d in self.ok("GET", "/support/doctors?q=*", token) if d["name"] == name)

    def free_slots(self, token: str, doctor_id: str) -> list[str]:
        slots = self.ok("GET", f"/doctor/availability/{doctor_id}/all?days=30", token)
        return [s["slot_time"] for s in slots if s["status"] == "AVAILABLE"]

    def slot_status(self, token: str, doctor_id: str, slot: str) -> str:
        return {s["slot_time"]: s["status"] for s in self.ok("GET", f"/doctor/availability/{doctor_id}/all?days=30", token)}.get(slot, "")

    # --- tests ---------------------------------------------------------------------------------

    def test_support_staff_manages_appointments_and_availability_end_to_end(self):
        admin = self.login("admin@http.test")
        self.register_staff(admin, "sam@http.test")
        status, body = self.call("POST", "/auth/login", body={"email": "sam@http.test", "password": PASSWORD})
        self.assertEqual((status, body["role"]), (200, "SUPPORT_STAFF"))
        staff = body["access_token"]

        # Own profile: read, update, invalid input rejected by request validation
        self.assertEqual(self.ok("GET", "/support/profile", staff)["email"], "sam@http.test")
        self.assertEqual(self.ok("PUT", "/support/profile", staff, {"full_name": "Samuel Support", "phone": "555 222 3333"})["full_name"], "Samuel Support")
        self.assertEqual(self.call("PUT", "/support/profile", staff, {"full_name": "Sa", "phone": "12"})[0], 422)

        # Searches: name, formatting-free phone, email (any case), "*" for everyone, too-short query
        self.assertEqual([p["name"] for p in self.ok("GET", "/support/patients?q=steve", staff)], ["Steve Works"])
        self.assertEqual([p["name"] for p in self.ok("GET", "/support/patients?q=555-010", staff)], ["Steve Works"])
        self.assertEqual([p["name"] for p in self.ok("GET", "/support/patients?q=PAULA@http", staff)], ["Paula Patient"])
        self.assertEqual([p["name"] for p in self.ok("GET", "/support/patients?q=*", staff)], ["Paula Patient", "Steve Works"])
        self.assertEqual([d["name"] for d in self.ok("GET", "/support/doctors?q=%2A", staff)], ["Dr One", "Dr Two"])
        self.assertEqual([d["name"] for d in self.ok("GET", "/support/doctors?q=555-0199", staff)], ["Dr Two"])
        self.assertEqual([d["name"] for d in self.ok("GET", "/support/doctors?q=doc1@", staff)], ["Dr One"])
        self.assertEqual(self.call("GET", "/support/patients?q=s", staff)[0], 422)

        patient_id = self.ok("GET", "/support/patients?q=steve", staff)[0]["id"]
        doctor_id = self.doctor_id(staff, "Dr One")
        first, second, third = self.free_slots(staff, doctor_id)[10:13]

        # Book on behalf of the patient, then find it by patient and by doctor
        appointment = self.ok("POST", "/appointments", staff, {"doctor_id": doctor_id, "patient_id": patient_id, "slot": first, "reason": "Booked by phone call"}, 201)["id"]
        self.assertEqual([r["id"] for r in self.ok("GET", f"/support/appointments?patient_id={patient_id}", staff)], [appointment])
        self.assertEqual(self.ok("GET", f"/support/appointments?doctor_id={doctor_id}", staff)[0]["patient_name"], "Steve Works")
        self.assertEqual(self.call("GET", "/support/appointments", staff)[0], 422)  # needs exactly one filter

        # Update reason, reschedule (old slot freed), block/unblock another slot, booked slot is protected
        self.assertEqual(self.ok("PATCH", f"/appointments/{appointment}", staff, {"reason": "Follow-up on blood work"})["reason"], "Follow-up on blood work")
        self.ok("POST", f"/appointments/{appointment}/reschedule", staff, {"slot": second})
        self.assertEqual((self.slot_status(staff, doctor_id, first), self.slot_status(staff, doctor_id, second)), ("AVAILABLE", "BOOKED"))
        self.assertIn("blocked", self.ok("POST", "/doctor/availability", staff, {"slot": third, "is_available": False, "block_reason": "Training", "doctor_id": doctor_id})["message"].lower())
        self.assertEqual(self.slot_status(staff, doctor_id, third), "BLOCKED")
        self.assertIn("unblocked", self.ok("POST", "/doctor/availability", staff, {"slot": third, "is_available": True, "doctor_id": doctor_id})["message"].lower())
        self.assertEqual(self.call("POST", "/doctor/availability", staff, {"slot": second, "is_available": False, "doctor_id": doctor_id})[0], 400)

        # Cancel: the slot is free again
        self.ok("DELETE", f"/appointments/{appointment}", staff)
        self.assertEqual(self.slot_status(staff, doctor_id, second), "AVAILABLE")

    def test_permission_boundaries_hold_over_http(self):
        admin = self.login("admin@http.test")
        self.register_staff(admin, "guard@http.test", "Gail Guard")
        staff = self.login("guard@http.test")
        patient = self.login("paula@http.test")
        doctor2 = self.login("doc2@http.test")
        doctor_id = self.doctor_id(staff, "Dr One")
        slot, other = self.free_slots(staff, doctor_id)[20:22]
        appointment = self.ok("POST", "/appointments", patient, {"doctor_id": doctor_id, "slot": slot, "reason": "Annual checkup"}, 201)["id"]

        forbidden = [
            ("patient: support-only reason update", "PATCH", f"/appointments/{appointment}", patient, {"reason": "Patient edit attempt"}),
            ("patient: change an appointment's status", "PATCH", f"/appointments/{appointment}/status", patient, {"status": "COMPLETED"}),
            ("doctor: another doctor's appointment status", "PATCH", f"/appointments/{appointment}/status", doctor2, {"status": "COMPLETED"}),
            ("patient: support listing", "GET", f"/support/appointments?doctor_id={doctor_id}", patient, None),
            ("patient: support patient search", "GET", "/support/patients?q=*", patient, None),
            ("patient: support profile", "GET", "/support/profile", patient, None),
            ("patient: block a doctor's slot", "POST", "/doctor/availability", patient, {"slot": other, "is_available": False, "doctor_id": doctor_id}),
            ("doctor: another doctor's slot", "POST", f"/doctor/availability/{doctor_id}", doctor2, {"slot_time": other, "is_available": False}),
            ("doctor: another doctor's appointment", "POST", f"/appointments/{appointment}/reschedule", doctor2, {"slot": other}),
            ("doctor: cancel another doctor's appointment", "DELETE", f"/appointments/{appointment}", doctor2, None),
            ("support staff: admin user search", "GET", "/admin/users/search?role=PATIENT&q=*", staff, None),
            ("support staff: register users", "POST", "/admin/users", staff, {"role": "ADMIN", "full_name": "Sneaky", "email": "x@http.test", "password": PASSWORD}),
            ("doctor: deactivate an account", "POST", f"/admin/users/{appointment}/deactivate", doctor2, None),
        ]
        for label, method, path, token, body in forbidden:
            with self.subTest(label):
                self.assertEqual(self.call(method, path, token, body)[0], 403)

        # Nothing above changed anything
        self.assertEqual(self.slot_status(staff, doctor_id, slot), "BOOKED")
        self.assertEqual(self.slot_status(staff, doctor_id, other), "AVAILABLE")
        self.assertEqual(self.ok("GET", f"/support/appointments?doctor_id={doctor_id}", staff)[0]["reason"], "Annual checkup")

        # Unauthenticated calls are rejected outright
        self.assertEqual(self.call("GET", "/support/patients?q=*")[0], 401)

        # The doctor list needs a login - and works for logged-in users of every role (it backs the
        # patient booking screen; a 401 here would sign the user out)
        self.assertEqual(self.call("GET", "/doctors")[0], 401)
        for token in (patient, staff, doctor2):
            self.assertEqual([d["name"] for d in self.ok("GET", "/doctors", token)], ["Dr One", "Dr Two"])

    def test_dead_tokens_get_401_so_the_app_signs_the_user_out(self):
        # The frontend signs the user out on a 401 for a request that carried a token, so expired or
        # garbled tokens must produce 401 - not 500 (which they used to, from inside the middleware).
        admin = self.login("admin@http.test")
        claims = jwt.decode(admin, JWT_SECRET, algorithms=["HS256"])
        expired = jwt.encode({**claims, "iat": int(time.time()) - 7200, "exp": int(time.time()) - 3600}, JWT_SECRET, algorithm="HS256")
        wrong_key = jwt.encode(claims, "some-other-secret-0123456789abcdef", algorithm="HS256")
        bad_role = jwt.encode({**claims, "role": "SUPERUSER"}, JWT_SECRET, algorithm="HS256")
        for label, token in (("expired", expired), ("garbled", "not-a-real-token"), ("wrong signing key", wrong_key), ("unknown role", bad_role)):
            with self.subTest(label):
                status, body = self.call("GET", "/doctors", token)
                self.assertEqual(status, 401, body)
                self.assertTrue(body["detail"])
        self.assertEqual(len(self.ok("GET", "/doctors", admin)), 2)  # the real token still works

    def test_admin_account_management_end_to_end(self):
        admin = self.login("admin@http.test")
        self.register_staff(admin, "acct@http.test", "Alex Account")

        # Search by role: "*" for everyone, and by name
        doctors = self.ok("GET", "/admin/users/search?role=DOCTOR&q=*", admin)
        self.assertEqual([u["email"] for u in doctors], ["doc1@http.test", "doc2@http.test"])
        found = self.ok("GET", "/admin/users/search?role=SUPPORT_STAFF&q=alex", admin)
        self.assertEqual([(u["email"], u["is_active"], u["is_self"]) for u in found], [("acct@http.test", True, False)])
        user_id = found[0]["user_id"]
        self.assertEqual(self.call("GET", "/admin/users/search?role=NURSE&q=*", admin)[0], 400)

        # Change email by id: old login stops, new one works with the same password; taken emails refused
        self.assertEqual(self.ok("POST", f"/admin/users/{user_id}/change-email", admin, {"new_email": "Alex.New@HTTP.test"})["new_email"], "alex.new@http.test")
        self.assertEqual(self.login_status("acct@http.test"), 401)
        self.assertEqual(self.login_status("alex.new@http.test"), 200)
        self.assertEqual(self.call("POST", f"/admin/users/{user_id}/change-email", admin, {"new_email": "doc1@http.test"})[0], 409)
        self.assertEqual(self.call("POST", f"/admin/users/{user_id}/change-email", admin, {"new_email": "not-an-email"})[0], 422)

        # Reset password by id
        self.ok("POST", f"/admin/users/{user_id}/reset-password", admin, {"new_password": "Changed4567"})
        self.assertEqual(self.login_status("alex.new@http.test", "Changed4567"), 200)
        self.assertEqual(self.login_status("alex.new@http.test"), 401)
        self.assertEqual(self.call("POST", f"/admin/users/{user_id}/reset-password", admin, {"new_password": "short"})[0], 400)

        # Deactivate / activate, and the self-protection rule. A token issued before deactivation
        # stops working on the very next request, not when it expires.
        staff_session = self.login("alex.new@http.test", "Changed4567")
        self.ok("GET", "/support/profile", staff_session)
        self.assertFalse(self.ok("POST", f"/admin/users/{user_id}/deactivate", admin)["is_active"])
        status, body = self.call("GET", "/support/profile", staff_session)
        self.assertEqual((status, body["detail"]), (401, "Your session is no longer valid. Please sign in again."))
        self.assertEqual(self.login_status("alex.new@http.test", "Changed4567"), 401)
        self.assertFalse(self.ok("GET", "/admin/users/search?role=SUPPORT_STAFF&q=alex", admin)[0]["is_active"])
        self.assertEqual(self.call("POST", f"/admin/users/{user_id}/deactivate", admin)[0], 400)  # already deactivated
        self.assertTrue(self.ok("POST", f"/admin/users/{user_id}/activate", admin)["is_active"])
        self.assertEqual(self.login_status("alex.new@http.test", "Changed4567"), 200)
        self.ok("GET", "/support/profile", staff_session)  # the old session works again once re-activated
        me = next(u for u in self.ok("GET", "/admin/users/search?role=ADMIN&q=*", admin) if u["is_self"])
        self.assertEqual(self.call("POST", f"/admin/users/{me['user_id']}/deactivate", admin)[0], 400)

        # Reset Password roles include support staff; the user list names them; soft delete blocks login
        self.assertIn({"value": "SUPPORT_STAFF", "label": "Support Staff"}, self.ok("GET", "/admin/roles", admin))
        listed = next(u for u in self.ok("GET", "/admin/users?page=1&page_size=50", admin) if u["id"] == user_id)
        self.assertEqual((listed["role"], listed["name"]), ("SUPPORT_STAFF", "Alex Account"))
        self.ok("PATCH", f"/admin/users/{user_id}/soft-delete", admin)
        self.assertEqual(self.login_status("alex.new@http.test", "Changed4567"), 401)


if __name__ == "__main__":
    unittest.main()
