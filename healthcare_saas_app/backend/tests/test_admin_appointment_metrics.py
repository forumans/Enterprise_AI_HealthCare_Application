import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend.app.api.routes.admin import _appointment_window_starts, admin_appointment_metrics
from backend.app.core import timeutils


class _FakeMappingResult:
    def __init__(self, data: dict):
        self._data = data

    def one(self):
        return self._data


class _FakeExecuteResult:
    def __init__(self, data: dict):
        self._data = data

    def mappings(self):
        return _FakeMappingResult(self._data)


class _FakeDbSession:
    def __init__(self, data: dict):
        self._data = data

    async def execute(self, _stmt):
        return _FakeExecuteResult(self._data)


class AdminAppointmentMetricsTests(unittest.IsolatedAsyncioTestCase):
    def test_appointment_window_starts_are_clinic_local_midnights(self):
        # Pin the clinic zone so the test doesn't depend on the CLINIC_TIMEZONE env var.
        with patch.object(timeutils, "CLINIC_TZ", ZoneInfo("America/New_York")):
            windows = _appointment_window_starts(datetime(2026, 3, 22, 18, 45, 30, tzinfo=UTC))  # 2:45 PM EDT

        self.assertEqual(windows["today"], datetime(2026, 3, 22, 4, tzinfo=UTC))  # midnight EDT
        self.assertEqual(windows["week"], datetime(2026, 3, 16, 4, tzinfo=UTC))   # Monday, EDT
        self.assertEqual(windows["month"], datetime(2026, 3, 1, 5, tzinfo=UTC))   # before DST: EST
        self.assertEqual(windows["year"], datetime(2026, 1, 1, 5, tzinfo=UTC))

    def test_today_window_follows_clinic_date_late_in_the_evening(self):
        # 11:30 PM EDT on Oct 22 is already Oct 23 in UTC; "today" must still be Oct 22 locally.
        with patch.object(timeutils, "CLINIC_TZ", ZoneInfo("America/New_York")):
            windows = _appointment_window_starts(datetime(2026, 10, 23, 3, 30, tzinfo=UTC))

        self.assertEqual(windows["today"], datetime(2026, 10, 22, 4, tzinfo=UTC))

    async def test_admin_appointment_metrics_response_shape(self):
        identity = SimpleNamespace(tenant_id="tenant-1")
        db = _FakeDbSession(
            {
                "total_appointments_to_date": 120,
                "total_appointments_year_to_date": 55,
                "total_appointments_this_month": 20,
                "total_appointments_this_week": 6,
                "total_appointments_today": 2,
            }
        )

        payload = await admin_appointment_metrics(identity=identity, db=db)

        self.assertEqual(
            payload,
            {
                "total_appointments_to_date": 120,
                "total_appointments_year_to_date": 55,
                "total_appointments_this_month": 20,
                "total_appointments_this_week": 6,
                "total_appointments_today": 2,
            },
        )


if __name__ == "__main__":
    unittest.main()
