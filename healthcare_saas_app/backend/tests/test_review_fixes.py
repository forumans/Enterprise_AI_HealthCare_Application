"""Database-free regression tests for the review fixes.

- Item 4: no debug logging that can leak personal data (backend print(), frontend console.log or
  dev logs that dump request/response bodies).
- Item 9: every (method, path) is served by exactly one route.
- Item 7: password reset tokens and login tokens can't stand in for each other.
- Items 1/3: the role and login guards on the fixed endpoints.
"""

import ast
import inspect
import re
import unittest
from collections import Counter
from pathlib import Path

from fastapi import HTTPException
from fastapi.routing import APIRoute

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_identity
from backend.app.core.security import (
    create_access_token,
    create_password_reset_token,
    password_reset_token_matches,
    read_password_reset_token,
)
from backend.app.main import app
from backend.app.middleware.tenant_middleware import decode_jwt_claims

APP_ROOT = Path(__file__).resolve().parents[2]  # healthcare_saas_app/
BACKEND_APP = APP_ROOT / "backend" / "app"
FRONTEND_SRC = APP_ROOT / "frontend" / "src"


def _route(path: str, method: str) -> APIRoute:
    return next(r for r in app.routes if isinstance(r, APIRoute) and r.path == path and method in r.methods)


def _depends_on(route: APIRoute, dependency) -> bool:
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if dep.call is dependency:
            return True
        stack.extend(dep.dependencies)
    return False


def _allowed_roles(route: APIRoute) -> set[str] | None:
    for dep in route.dependant.dependencies:
        if getattr(dep.call, "__name__", "") == "_checker":
            return set(inspect.getclosurevars(dep.call).nonlocals["normalized_roles"])
    return None


class NoPersonalDataInLogsTests(unittest.TestCase):
    def test_backend_has_no_print_calls(self):
        offenders = []
        for path in BACKEND_APP.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
                    offenders.append(f"{path.relative_to(APP_ROOT)}:{node.lineno}")
        self.assertEqual(offenders, [], "use logging without personal data instead of print()")

    def test_frontend_has_no_console_log_outside_the_dev_debug_helper(self):
        offenders = []
        for path in FRONTEND_SRC.rglob("*.ts*"):
            if ".test." in path.name or path.parts[-2] == "test":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"console\.(log|info|debug)\(", line) and "console.log(...args)" not in line:
                    offenders.append(f"{path.relative_to(APP_ROOT)}:{number}")
        self.assertEqual(offenders, [])

    def test_dev_debug_logs_never_dump_payloads_or_responses(self):
        api = (FRONTEND_SRC / "api.ts").read_text(encoding="utf-8")
        dumps = [line.strip() for line in api.splitlines() if re.search(r"debugLog\(.*\b(response|payload|requestBody|data)\)", line)]
        self.assertEqual(dumps, [])


class RouteTableTests(unittest.TestCase):
    def test_every_method_and_path_has_exactly_one_handler(self):
        served = Counter((method, route.path) for route in app.routes if isinstance(route, APIRoute) for method in route.methods)
        self.assertEqual([op for op, count in served.items() if count > 1], [])

    def test_patient_search_is_served_by_the_patients_router(self):
        route = _route("/api/patients/search", "GET")
        self.assertEqual(route.endpoint.__module__, "backend.app.api.routes.patients")


class TokenSeparationTests(unittest.TestCase):
    def test_reset_tokens_round_trip_and_are_single_use(self):
        token = create_password_reset_token(user_id="u1", password_hash="hash-A")
        user_id, fingerprint = read_password_reset_token(token)
        self.assertEqual(user_id, "u1")
        self.assertTrue(password_reset_token_matches(fingerprint, "hash-A"))
        self.assertFalse(password_reset_token_matches(fingerprint, "hash-B"))  # password changed -> link dead

    def test_a_login_token_is_not_a_reset_token(self):
        access = create_access_token(user_id="u1", tenant_id="t1", role="PATIENT")
        self.assertIsNone(read_password_reset_token(access))

    def test_a_reset_token_is_not_a_login_token(self):
        reset = create_password_reset_token(user_id="u1", password_hash="hash-A")
        with self.assertRaises(HTTPException) as ctx:
            decode_jwt_claims(reset, settings.jwt_secret, settings.jwt_algorithm)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_expired_reset_tokens_are_rejected(self):
        self.assertIsNone(read_password_reset_token(create_password_reset_token(user_id="u1", password_hash="h", expires_minutes=-1)))


class GuardTests(unittest.TestCase):
    def test_status_changes_are_for_doctors_and_admins(self):
        self.assertEqual(_allowed_roles(_route("/api/appointments/{appointment_id}/status", "PATCH")), {"DOCTOR", "ADMIN"})

    def test_doctor_list_and_availability_require_a_login(self):
        for path in ("/api/doctors", "/api/doctor/availability/{doctor_id}/ndays"):
            with self.subTest(path=path):
                self.assertTrue(_depends_on(_route(path, "GET"), get_current_identity))

    def test_every_logged_in_route_rechecks_the_account(self):
        # get_current_identity looks the account up, so deactivated/deleted users lose access at once
        self.assertIn("db", inspect.signature(get_current_identity).parameters)


if __name__ == "__main__":
    unittest.main()
