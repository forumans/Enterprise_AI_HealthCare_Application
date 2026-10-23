import unittest
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.app.core import timeutils
from backend.app.core.timeutils import (
    clinic_day_bounds,
    clinic_today,
    clinic_week_bounds,
    default_slot_times,
    parse_client_datetime,
    to_utc,
    utc_day_start,
)

NEW_YORK = ZoneInfo("America/New_York")


class DefaultSlotTimesTests(unittest.TestCase):
    def setUp(self):
        # Pin the clinic zone so the tests don't depend on the CLINIC_TIMEZONE env var.
        self._orig_tz = timeutils.CLINIC_TZ
        timeutils.CLINIC_TZ = NEW_YORK

    def tearDown(self):
        timeutils.CLINIC_TZ = self._orig_tz

    def test_hourly_slots_8am_through_11pm_for_seven_days(self):
        now = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)  # 5 AM EDT, before any slot today
        slots = default_slot_times(now)

        self.assertEqual(len(slots), 7 * 16)
        local_hours = sorted({s.astimezone(NEW_YORK).hour for s in slots})
        self.assertEqual(local_hours, list(range(8, 24)))
        self.assertTrue(all(s.tzinfo is not None and s.utcoffset() == timedelta(0) for s in slots))

    def test_local_hours_stay_fixed_across_dst_end(self):
        # DST ends Sunday 2026-11-01 in America/New_York (UTC-4 -> UTC-5).
        now = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)  # 6 AM EDT
        slots = default_slot_times(now)

        self.assertEqual(slots[0], datetime(2026, 10, 31, 12, 0, tzinfo=UTC))   # 8 AM EDT
        self.assertIn(datetime(2026, 11, 1, 13, 0, tzinfo=UTC), slots)          # 8 AM EST
        self.assertNotIn(datetime(2026, 11, 1, 12, 0, tzinfo=UTC), slots)       # would be 7 AM EST
        self.assertEqual(slots[-1], datetime(2026, 11, 7, 4, 0, tzinfo=UTC))    # 11 PM EST on Nov 6
        self.assertEqual({s.astimezone(NEW_YORK).hour for s in slots}, set(range(8, 24)))

    def test_local_hours_stay_fixed_across_dst_start(self):
        # DST starts Sunday 2026-03-08 in America/New_York (UTC-5 -> UTC-4).
        slots = default_slot_times(datetime(2026, 3, 7, 10, 0, tzinfo=UTC))

        self.assertIn(datetime(2026, 3, 7, 13, 0, tzinfo=UTC), slots)  # 8 AM EST
        self.assertIn(datetime(2026, 3, 8, 12, 0, tzinfo=UTC), slots)  # 8 AM EDT

    def test_only_future_slots_are_returned(self):
        now = datetime(2026, 10, 20, 20, 30, tzinfo=UTC)  # 4:30 PM EDT
        slots = default_slot_times(now)

        self.assertTrue(all(s > now for s in slots))
        today_local = [s for s in slots if s.astimezone(NEW_YORK).date() == date(2026, 10, 20)]
        self.assertEqual([s.astimezone(NEW_YORK).hour for s in today_local], list(range(17, 24)))


class ConversionHelperTests(unittest.TestCase):
    def test_naive_values_are_treated_as_utc(self):
        self.assertEqual(to_utc(datetime(2026, 1, 1, 12)), datetime(2026, 1, 1, 12, tzinfo=UTC))

    def test_aware_values_are_converted_to_utc(self):
        eastern = datetime(2026, 1, 1, 7, tzinfo=timezone(timedelta(hours=-5)))
        self.assertEqual(to_utc(eastern), datetime(2026, 1, 1, 12, tzinfo=UTC))

    def test_parse_client_datetime_accepts_z_offset_and_naive(self):
        expected = datetime(2026, 6, 23, 12, tzinfo=UTC)
        self.assertEqual(parse_client_datetime("2026-06-23T12:00:00.000Z"), expected)
        self.assertEqual(parse_client_datetime("2026-06-23T08:00:00-04:00"), expected)
        self.assertEqual(parse_client_datetime("2026-06-23T12:00:00"), expected)
        with self.assertRaises(ValueError):
            parse_client_datetime("not-a-date")

    def test_utc_day_start(self):
        self.assertEqual(utc_day_start(date(2026, 3, 8)), datetime(2026, 3, 8, tzinfo=UTC))



class ClinicCalendarTests(unittest.TestCase):
    def setUp(self):
        self._orig_tz = timeutils.CLINIC_TZ
        timeutils.CLINIC_TZ = NEW_YORK

    def tearDown(self):
        timeutils.CLINIC_TZ = self._orig_tz

    def test_clinic_today_uses_local_date_late_in_the_evening(self):
        # 11 PM EDT Oct 22 = 03:00 UTC Oct 23.
        self.assertEqual(clinic_today(datetime(2026, 10, 23, 3, 0, tzinfo=UTC)), date(2026, 10, 22))

    def test_day_bounds_cover_evening_appointments(self):
        start, end = clinic_day_bounds(date(2026, 10, 22))
        self.assertEqual(start, datetime(2026, 10, 22, 4, tzinfo=UTC))
        self.assertEqual(end, datetime(2026, 10, 23, 4, tzinfo=UTC))
        eleven_pm = datetime(2026, 10, 23, 3, 0, tzinfo=UTC)
        self.assertTrue(start <= eleven_pm < end)

    def test_day_bounds_on_dst_change_days(self):
        fall_start, fall_end = clinic_day_bounds(date(2026, 11, 1))
        spring_start, spring_end = clinic_day_bounds(date(2026, 3, 8))
        self.assertEqual(fall_end - fall_start, timedelta(hours=25))
        self.assertEqual(spring_end - spring_start, timedelta(hours=23))

    def test_week_bounds_monday_to_monday_local(self):
        start, end = clinic_week_bounds(date(2026, 11, 4))  # Wednesday, week spans DST end
        self.assertEqual(start, datetime(2026, 11, 2, 5, tzinfo=UTC))  # Mon Nov 2, midnight EST
        self.assertEqual(end, datetime(2026, 11, 9, 5, tzinfo=UTC))
        self.assertEqual(clinic_week_bounds(date(2026, 10, 26))[1], datetime(2026, 11, 2, 5, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()
