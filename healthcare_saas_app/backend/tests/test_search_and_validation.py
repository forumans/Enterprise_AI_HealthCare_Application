"""Unit tests (no database) for the shared people search and the new request models' validation."""

import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from backend.app.api.routes.admin_password_reset import NewEmailRequest, NewPasswordRequest
from backend.app.api.routes.appointments import CreateAppointmentRequest, RescheduleAppointmentRequest, UpdateAppointmentRequest
from backend.app.api.routes.doctor import UpsertDoctorAvailabilityRequest
from backend.app.api.routes.support import UpdateSupportProfileRequest
from backend.app.api.search_utils import SEARCH_LIMIT, is_wildcard, name_phone_or_email_matches, search_limit
from backend.app.models import Patient, User


def _sql(clause) -> str:
    return str(clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


class SearchHelperTests(unittest.TestCase):
    def test_star_is_the_wildcard_and_lifts_the_cap(self):
        for q in ("*", " * "):
            with self.subTest(q=q):
                self.assertTrue(is_wildcard(q))
                self.assertIsNone(search_limit(q))
                self.assertEqual(_sql(name_phone_or_email_matches(q, Patient)), "true")
        self.assertFalse(is_wildcard("**"))
        self.assertEqual(search_limit("steve"), SEARCH_LIMIT)

    def test_short_queries_are_rejected(self):
        for q in ("", " ", "s", " a "):
            with self.subTest(q=q):
                with self.assertRaises(HTTPException) as ctx:
                    name_phone_or_email_matches(q, Patient)
                self.assertEqual(ctx.exception.status_code, 422)

    def test_name_email_and_phone_matching(self):
        name_only = _sql(name_phone_or_email_matches("St", Patient))
        self.assertIn("ILIKE '%%St%%'", name_only)
        self.assertNotIn("regexp_replace", name_only)  # under 3 digits: no phone match

        with_phone = _sql(name_phone_or_email_matches("(555) 12", Patient))
        self.assertIn("regexp_replace", with_phone)
        self.assertIn("LIKE '%%55512%%'", with_phone)  # formatting stripped from the query too

        with_email = _sql(name_phone_or_email_matches("sam@", Patient, User.email))
        self.assertIn("users.email ILIKE '%%sam@%%'", with_email)


class RequestValidationTests(unittest.TestCase):
    def test_support_profile_requires_name_and_phone_shape(self):
        ok = UpdateSupportProfileRequest(full_name="Sam Support", phone="+1 555-123-4567")
        self.assertEqual(ok.phone, "+1 555-123-4567")
        for bad in ({"full_name": "Sa", "phone": "5551234567"}, {"full_name": "Sam Support", "phone": "12"}, {"full_name": "Sam Support", "phone": "555-CALL-NOW"}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    UpdateSupportProfileRequest(**bad)

    def test_new_email_is_normalized_and_validated(self):
        self.assertEqual(NewEmailRequest(new_email="  New.Person@Example.ORG ").new_email, "new.person@example.org")
        with self.assertRaises(ValidationError):
            NewEmailRequest(new_email="no-at-sign.example.org")
        self.assertEqual(NewPasswordRequest(new_password="x").new_password, "x")  # length is checked by the route (400)

    def test_appointment_requests(self):
        own = CreateAppointmentRequest(doctor_id="d", slot="2030-01-01T15:00:00Z", reason="Checkup visit")
        self.assertIsNone(own.patient_id)  # patients book for themselves
        on_behalf = CreateAppointmentRequest(doctor_id="d", slot="2030-01-01T15:00:00Z", reason="Checkup visit", patient_id="p")
        self.assertEqual(on_behalf.patient_id, "p")
        with self.assertRaises(ValidationError):
            CreateAppointmentRequest(doctor_id="d", slot="2030-01-01T15:00:00Z", reason="Hi")
        with self.assertRaises(ValidationError):
            UpdateAppointmentRequest(reason="Hi")
        self.assertEqual(RescheduleAppointmentRequest(slot="2030-01-01T15:00:00Z").slot, "2030-01-01T15:00:00Z")

    def test_availability_request_doctor_id_is_optional(self):
        self.assertIsNone(UpsertDoctorAvailabilityRequest(slot="2030-01-01T15:00:00Z").doctor_id)  # doctors act for themselves
        self.assertEqual(UpsertDoctorAvailabilityRequest(slot="2030-01-01T15:00:00Z", doctor_id="d").doctor_id, "d")


if __name__ == "__main__":
    unittest.main()
