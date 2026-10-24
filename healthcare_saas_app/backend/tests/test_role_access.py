"""Which roles each appointment/support route admits (require_roles), and JWT role validation.

The integration tests call route functions directly, which bypasses FastAPI dependencies, so the
role guards are checked here against the registered app routes.
"""

import asyncio
import inspect
import unittest

from fastapi import HTTPException

from backend.app.api.routes.admin_password_reset import ChangeEmailRequest, get_available_roles
from backend.app.main import app
from backend.app.middleware.tenant_middleware import _as_role
from backend.app.models import User


def _allowed_roles(path: str, method: str) -> set[str] | None:
    for route in app.router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            for dependency in route.dependant.dependencies:
                if dependency.call.__name__ == "_checker":
                    return set(inspect.getclosurevars(dependency.call).nonlocals["normalized_roles"])
            return None  # route has no role guard
    raise AssertionError(f"{method} {path} is not registered")


class RoleAccessTests(unittest.TestCase):
    def test_support_staff_can_manage_appointments(self):
        self.assertEqual(_allowed_roles("/api/appointments", "POST"), {"PATIENT", "SUPPORT_STAFF"})
        self.assertEqual(_allowed_roles("/api/appointments/{appointment_id}/reschedule", "POST"), {"PATIENT", "DOCTOR", "SUPPORT_STAFF"})
        self.assertEqual(_allowed_roles("/api/appointments/{appointment_id}", "PATCH"), {"SUPPORT_STAFF"})
        self.assertEqual(_allowed_roles("/api/support/appointments", "GET"), {"SUPPORT_STAFF"})
        self.assertEqual(_allowed_roles("/api/support/patients", "GET"), {"SUPPORT_STAFF"})
        self.assertEqual(_allowed_roles("/api/support/doctors", "GET"), {"SUPPORT_STAFF"})
        self.assertEqual(_allowed_roles("/api/support/profile", "GET"), {"SUPPORT_STAFF"})
        self.assertEqual(_allowed_roles("/api/support/profile", "PUT"), {"SUPPORT_STAFF"})
        self.assertIn("SUPPORT_STAFF", _allowed_roles("/api/patients", "GET"))

    def test_only_admins_change_passwords_and_emails(self):
        self.assertEqual(_allowed_roles("/api/admin/reset-password", "POST"), {"ADMIN"})
        self.assertEqual(_allowed_roles("/api/admin/change-email", "POST"), {"ADMIN"})
        self.assertEqual(_allowed_roles("/api/admin/users/search", "GET"), {"ADMIN"})
        self.assertEqual(_allowed_roles("/api/admin/users/{user_id}/reset-password", "POST"), {"ADMIN"})
        self.assertEqual(_allowed_roles("/api/admin/users/{user_id}/change-email", "POST"), {"ADMIN"})
        self.assertEqual(_allowed_roles("/api/admin/users/{user_id}/deactivate", "POST"), {"ADMIN"})
        self.assertEqual(_allowed_roles("/api/admin/users/{user_id}/activate", "POST"), {"ADMIN"})

    def test_change_email_request_normalizes_and_validates(self):
        request = ChangeEmailRequest(email=" A@Example.com ", role="PATIENT", new_email="New.Person@Example.ORG")
        self.assertEqual((request.email, request.new_email), ("a@example.com", "new.person@example.org"))
        with self.assertRaises(ValueError):
            ChangeEmailRequest(email="a@example.com", role="PATIENT", new_email="not-an-email")

    def test_confirming_stays_doctor_only(self):
        self.assertEqual(_allowed_roles("/api/appointments/{appointment_id}/confirm", "POST"), {"DOCTOR"})

    def test_admin_can_reset_passwords_for_every_role(self):
        roles = asyncio.run(get_available_roles(identity=None))
        self.assertEqual({r["value"] for r in roles}, set(User.__table__.c.role.type.enums))
        self.assertIn({"value": "SUPPORT_STAFF", "label": "Support Staff"}, roles)

    def test_middleware_accepts_support_staff_tokens(self):
        self.assertEqual(_as_role("support_staff"), "SUPPORT_STAFF")
        with self.assertRaises(HTTPException):
            _as_role("RECEPTIONIST")


if __name__ == "__main__":
    unittest.main()
