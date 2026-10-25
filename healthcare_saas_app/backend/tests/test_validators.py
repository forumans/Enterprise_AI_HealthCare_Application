"""Field rules shared by registration, admin user creation and profile updates (api/validators.py)."""

import unittest
from datetime import date, timedelta
from unittest.mock import patch

from pydantic import ValidationError

from backend.app.api import validators
from backend.app.api.routes.admin import AdminCreateUserRequest
from backend.app.api.routes.auth import RegisterRequest
from backend.app.api.routes.doctor import DoctorRegisterRequest

TODAY = date(2026, 10, 25)


def years_ago(years: int, days: int = 0) -> date:
    return TODAY.replace(year=TODAY.year - years) - timedelta(days=days)


class FieldRuleTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(validators, "today", return_value=TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_email(self):
        self.assertEqual(validators.valid_email("  jane@example.com "), "jane@example.com")
        for bad in ("jane", "jane@example", "jane @example.com", ""):
            with self.assertRaises(ValueError, msg=bad):
                validators.valid_email(bad)

    def test_phone_is_optional_but_must_match_when_given(self):
        self.assertIsNone(validators.valid_phone(None))
        self.assertIsNone(validators.valid_phone("   "))
        self.assertEqual(validators.valid_phone(" +1 555-123-4567 "), "+1 555-123-4567")
        for bad in ("12345", "555-CALL-NOW", "1" * 16):
            with self.assertRaises(ValueError, msg=bad):
                validators.valid_phone(bad)

    def test_gender_is_normalized_to_the_enum_value(self):
        self.assertEqual(validators.valid_gender("Male"), "MALE")
        self.assertEqual(validators.valid_gender("prefer not to say"), "PREFER_NOT_TO_SAY")
        self.assertIsNone(validators.valid_gender(""))
        with self.assertRaises(ValueError):
            validators.valid_gender("unknown")

    def test_birth_date_not_in_future_and_at_most_120_years_ago(self):
        self.assertEqual(validators.valid_birth_date(years_ago(120)), years_ago(120))
        with self.assertRaises(ValueError):
            validators.valid_birth_date(TODAY + timedelta(days=1))
        with self.assertRaises(ValueError):
            validators.valid_birth_date(years_ago(121))

    def test_doctor_must_be_at_least_18(self):
        self.assertEqual(validators.valid_doctor_birth_date(years_ago(18)), years_ago(18))
        self.assertIsNone(validators.valid_doctor_birth_date(None))
        with self.assertRaises(ValueError):
            validators.valid_doctor_birth_date(years_ago(18) + timedelta(days=1))

    def test_optional_text_and_full_name(self):
        self.assertIsNone(validators.optional_text("  ", 10))
        self.assertEqual(validators.optional_text(" Austin ", 10), "Austin")
        with self.assertRaises(ValueError):
            validators.optional_text("x" * 11, 10)
        with self.assertRaises(ValueError):
            validators.optional_text(42, 10)
        self.assertIsNone(validators.valid_full_name(""))
        self.assertEqual(validators.valid_full_name(" Ann Lee "), "Ann Lee")
        with self.assertRaises(ValueError):
            validators.valid_full_name("Al")


class RequestModelTests(unittest.TestCase):
    """The request models apply the rules, so bad input gets the generic 422 (GAP-06, GAP-07)."""

    base = {"full_name": "Jane Doe", "email": "jane@example.com", "password": "Secret123"}

    def test_patient_registration_rejects_bad_fields(self):
        RegisterRequest(**self.base, phone="555-123-4567", gender="female", date_of_birth="1985-03-07")
        for field, value in (("email", "not-an-email"), ("phone", "12345"), ("gender", "x"), ("date_of_birth", "2999-01-01")):
            with self.assertRaises(ValidationError, msg=field):
                RegisterRequest(**{**self.base, field: value})

    def test_patient_registration_stores_the_gender_enum_value(self):
        self.assertEqual(RegisterRequest(**self.base, gender="Prefer not to say").gender, "PREFER_NOT_TO_SAY")

    def test_doctor_registration_rejects_bad_fields_and_minors(self):
        DoctorRegisterRequest(**self.base, phone="555-123-4567", date_of_birth="1980-01-01")
        for field, value in (("email", "doc@"), ("phone", "12"), ("date_of_birth", (date.today() - timedelta(days=365 * 10)).isoformat())):
            with self.assertRaises(ValidationError, msg=field):
                DoctorRegisterRequest(**{**self.base, field: value})

    def test_admin_created_users_follow_the_same_rules(self):
        self.assertEqual(AdminCreateUserRequest(**self.base, role="PATIENT", gender="Male").gender, "MALE")
        with self.assertRaises(ValidationError):
            AdminCreateUserRequest(**self.base, role="PATIENT", gender="Martian")
        with self.assertRaises(ValidationError):
            AdminCreateUserRequest(**self.base, role="ADMIN", phone="123")
        with self.assertRaises(ValidationError):  # doctors must be 18+
            AdminCreateUserRequest(**self.base, role="DOCTOR", date_of_birth=(date.today() - timedelta(days=365 * 16)).isoformat())
        self.assertEqual(AdminCreateUserRequest(**self.base, role="ADMIN").phone, "")


if __name__ == "__main__":
    unittest.main()
