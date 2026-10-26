import unittest
from collections import Counter

from backend.app.main import app
from backend.tests.route_helpers import handler_for


def _handler_for(path: str, method: str = "GET") -> str | None:
    return handler_for(app, path, method)


class RouteRegistrationTests(unittest.TestCase):
    def test_no_method_and_path_is_registered_twice(self):
        # A duplicate registration silently shadows the later handler.
        operations = Counter(
            (method, path)
            for path, methods in app.openapi()["paths"].items()
            for method in methods
        )
        duplicates = [op for op, count in operations.items() if count > 1]
        self.assertEqual(duplicates, [])

    def test_static_doctor_appointment_routes_are_not_shadowed_by_the_id_route(self):
        self.assertEqual(_handler_for("/api/doctor/appointments/today"), "doctor_appointments_today")
        self.assertEqual(_handler_for("/api/doctor/appointments/all"), "doctor_all_appointments")
        self.assertEqual(_handler_for("/api/doctor/appointments/3f1c-uuid"), "doctor_get_appointment_details")

    def test_reschedule_and_cancel_routes_are_registered(self):
        self.assertEqual(_handler_for("/api/appointments/3f1c-uuid/reschedule", "POST"), "reschedule_appointment_route")
        self.assertEqual(_handler_for("/api/appointments/3f1c-uuid", "DELETE"), "delete_appointment")

    def test_range_block_routes_are_registered(self):
        doctor = "/api/doctor/availability/3f1c-uuid"
        self.assertEqual(_handler_for(f"{doctor}/blocks/preview", "POST"), "preview_block_range")
        self.assertEqual(_handler_for(f"{doctor}/blocks", "POST"), "block_range")
        self.assertEqual(_handler_for(f"{doctor}/blocks", "GET"), "list_block_ranges")
        self.assertEqual(_handler_for(f"{doctor}/unblock/preview", "POST"), "preview_unblock_range")
        self.assertEqual(_handler_for(f"{doctor}/unblock", "POST"), "unblock_range")
        self.assertEqual(_handler_for(f"{doctor}/all"), "list_all_availability")
        self.assertEqual(_handler_for("/api/support/reschedule-queue"), "reschedule_queue")

    def test_duplicate_and_legacy_endpoints_are_gone(self):
        # GAP-22: endpoints no screen used, each duplicating a supported one, were removed
        paths = app.openapi()["paths"]
        removed = [
            ("get", "/availability/{doctor_id}"),
            ("get", "/doctor/availability/{doctor_id}/ndays"),
            ("post", "/doctor/availability/{doctor_id}"),
            ("get", "/doctor/appointments"),
            ("get", "/doctor/appointments/upcoming"),
            ("get", "/patient/medical-history"),
            ("get", "/patient/appointments/upcoming"),
            ("patch", "/patient/profile"),
            ("get", "/patients"),
            ("post", "/patients"),
            ("get", "/patients/{patient_id}/prescriptions"),
            ("post", "/doctors"),
            ("post", "/admin/reset-password"),
            ("post", "/admin/change-email"),
        ]
        for method, path in removed:
            for prefix in ("", "/api"):
                with self.subTest(method=method, path=prefix + path):
                    self.assertNotIn(method, paths.get(prefix + path, {}))

    def test_supported_api_only_endpoints_stay(self):
        # Kept on purpose: deleting a slot and the admin's full appointment history have no other endpoint
        paths = app.openapi()["paths"]
        self.assertIn("delete", paths["/api/doctor/availability/{doctor_id}"])
        self.assertIn("get", paths["/api/admin/appointments"])
        self.assertIn("get", paths["/api/doctors"])  # GET /doctors stays; only POST /doctors was removed


if __name__ == "__main__":
    unittest.main()
