import unittest
from collections import Counter

from starlette.routing import Match

from backend.app.main import app


def _handler_for(path: str, method: str = "GET") -> str | None:
    scope = {"type": "http", "path": path, "method": method, "root_path": ""}
    for route in app.router.routes:
        match, child = route.matches(scope)
        if match == Match.FULL:
            endpoint = child.get("endpoint") or getattr(route, "endpoint", None)
            return getattr(endpoint, "__name__", None)
    return None


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
        self.assertEqual(_handler_for("/api/doctor/appointments/upcoming"), "doctor_appointments_upcoming")
        self.assertEqual(_handler_for("/api/doctor/appointments/today"), "doctor_appointments_today")
        self.assertEqual(_handler_for("/api/doctor/appointments/all"), "doctor_all_appointments")
        self.assertEqual(_handler_for("/api/doctor/appointments/3f1c-uuid"), "doctor_get_appointment_details")


if __name__ == "__main__":
    unittest.main()
