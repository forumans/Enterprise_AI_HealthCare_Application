import unittest
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.app.core.timeutils import (
    DEFAULT_CLINIC_TIMEZONE,
    clinic_day_bounds,
    clinic_today,
    clinic_week_bounds,
    clinic_zone,
    default_slot_times,
    is_valid_timezone,
    office_hour_slots_in_range,
    parse_client_datetime,
    same_wall_clock,
    to_utc,
    utc_day_start,
)

NEW_YORK = ZoneInfo("America/New_York")
LOS_ANGELES = ZoneInfo("America/Los_Angeles")
KOLKATA = ZoneInfo("Asia/Kolkata")


class DefaultSlotTimesTests(unittest.TestCase):
    def test_hourly_slots_8am_through_11pm_for_seven_days(self):
        now = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)  # 5 AM EDT, before any slot today
        slots = default_slot_times(NEW_YORK, now)

        self.assertEqual(len(slots), 7 * 16)
        local_hours = sorted({s.astimezone(NEW_YORK).hour for s in slots})
        self.assertEqual(local_hours, list(range(8, 24)))
        self.assertTrue(all(s.tzinfo is not None and s.utcoffset() == timedelta(0) for s in slots))

    def test_local_hours_stay_fixed_across_dst_end(self):
        # DST ends Sunday 2026-11-01 in America/New_York (UTC-4 -> UTC-5).
        now = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)  # 6 AM EDT
        slots = default_slot_times(NEW_YORK, now)

        self.assertEqual(slots[0], datetime(2026, 10, 31, 12, 0, tzinfo=UTC))   # 8 AM EDT
        self.assertIn(datetime(2026, 11, 1, 13, 0, tzinfo=UTC), slots)          # 8 AM EST
        self.assertNotIn(datetime(2026, 11, 1, 12, 0, tzinfo=UTC), slots)       # would be 7 AM EST
        self.assertEqual(slots[-1], datetime(2026, 11, 7, 4, 0, tzinfo=UTC))    # 11 PM EST on Nov 6
        self.assertEqual({s.astimezone(NEW_YORK).hour for s in slots}, set(range(8, 24)))

    def test_local_hours_stay_fixed_across_dst_start(self):
        # DST starts Sunday 2026-03-08 in America/New_York (UTC-5 -> UTC-4).
        slots = default_slot_times(NEW_YORK, datetime(2026, 3, 7, 10, 0, tzinfo=UTC))

        self.assertIn(datetime(2026, 3, 7, 13, 0, tzinfo=UTC), slots)  # 8 AM EST
        self.assertIn(datetime(2026, 3, 8, 12, 0, tzinfo=UTC), slots)  # 8 AM EDT

    def test_only_future_slots_are_returned(self):
        now = datetime(2026, 10, 20, 20, 30, tzinfo=UTC)  # 4:30 PM EDT
        slots = default_slot_times(NEW_YORK, now)

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
    def test_clinic_today_uses_local_date_late_in_the_evening(self):
        # 11 PM EDT Oct 22 = 03:00 UTC Oct 23.
        self.assertEqual(clinic_today(NEW_YORK, datetime(2026, 10, 23, 3, 0, tzinfo=UTC)), date(2026, 10, 22))

    def test_day_bounds_cover_evening_appointments(self):
        start, end = clinic_day_bounds(date(2026, 10, 22), NEW_YORK)
        self.assertEqual(start, datetime(2026, 10, 22, 4, tzinfo=UTC))
        self.assertEqual(end, datetime(2026, 10, 23, 4, tzinfo=UTC))
        eleven_pm = datetime(2026, 10, 23, 3, 0, tzinfo=UTC)
        self.assertTrue(start <= eleven_pm < end)

    def test_day_bounds_on_dst_change_days(self):
        fall_start, fall_end = clinic_day_bounds(date(2026, 11, 1), NEW_YORK)
        spring_start, spring_end = clinic_day_bounds(date(2026, 3, 8), NEW_YORK)
        self.assertEqual(fall_end - fall_start, timedelta(hours=25))
        self.assertEqual(spring_end - spring_start, timedelta(hours=23))

    def test_week_bounds_monday_to_monday_local(self):
        start, end = clinic_week_bounds(date(2026, 11, 4), NEW_YORK)  # Wednesday, week spans DST end
        self.assertEqual(start, datetime(2026, 11, 2, 5, tzinfo=UTC))  # Mon Nov 2, midnight EST
        self.assertEqual(end, datetime(2026, 11, 9, 5, tzinfo=UTC))
        self.assertEqual(clinic_week_bounds(date(2026, 10, 26), NEW_YORK)[1], datetime(2026, 11, 2, 5, tzinfo=UTC))


class ClinicZoneTests(unittest.TestCase):
    """Each clinic has its own zone; the same helpers must work for any of them."""

    def test_default_slots_follow_each_clinics_own_zone(self):
        now = datetime(2026, 10, 20, 6, 0, tzinfo=UTC)  # before 8 AM in New York and Los Angeles
        for zone in (NEW_YORK, LOS_ANGELES, KOLKATA):
            with self.subTest(zone=zone.key):
                slots = default_slot_times(zone, now)
                self.assertEqual({s.astimezone(zone).hour for s in slots}, set(range(8, 24)))
                self.assertTrue(all(s > now for s in slots))

    def test_same_local_day_is_a_different_utc_range_per_clinic(self):
        day = date(2026, 10, 22)
        self.assertEqual(clinic_day_bounds(day, LOS_ANGELES)[0], datetime(2026, 10, 22, 7, tzinfo=UTC))
        self.assertEqual(clinic_day_bounds(day, KOLKATA)[0], datetime(2026, 10, 21, 18, 30, tzinfo=UTC))

    def test_clinic_today_differs_by_zone_at_the_same_instant(self):
        instant = datetime(2026, 10, 22, 20, 0, tzinfo=UTC)  # 4 PM New York, 1:30 AM next day Kolkata
        self.assertEqual(clinic_today(NEW_YORK, instant), date(2026, 10, 22))
        self.assertEqual(clinic_today(KOLKATA, instant), date(2026, 10, 23))

    def test_same_wall_clock_keeps_local_hour_when_the_zone_changes(self):
        nine_am_new_york = datetime(2026, 10, 22, 13, tzinfo=UTC)
        moved = same_wall_clock(nine_am_new_york, NEW_YORK, LOS_ANGELES)
        self.assertEqual(moved, datetime(2026, 10, 22, 16, tzinfo=UTC))
        self.assertEqual(moved.astimezone(LOS_ANGELES).hour, 9)

    def test_zone_names_are_validated(self):
        self.assertTrue(is_valid_timezone("America/Chicago"))
        self.assertTrue(is_valid_timezone("Asia/Calcutta"))  # legacy alias some browsers report
        self.assertFalse(is_valid_timezone("Mars/Olympus_Mons"))
        self.assertFalse(is_valid_timezone(""))
        self.assertEqual(clinic_zone("Europe/London").key, "Europe/London")
        self.assertEqual(clinic_zone("not-a-zone").key, DEFAULT_CLINIC_TIMEZONE)
        self.assertEqual(clinic_zone(None).key, DEFAULT_CLINIC_TIMEZONE)


class OfficeHourSlotsInRangeTests(unittest.TestCase):
    @staticmethod
    def ny(day: int, hour: int, month: int = 11) -> datetime:
        return datetime(2026, month, day, hour, tzinfo=NEW_YORK).astimezone(UTC)

    def local_hours(self, slots):
        return [(s.astimezone(NEW_YORK).day, s.astimezone(NEW_YORK).hour) for s in slots]

    def test_end_is_excluded(self):
        slots = office_hour_slots_in_range(self.ny(3, 9), self.ny(3, 12), NEW_YORK)
        self.assertEqual(self.local_hours(slots), [(3, 9), (3, 10), (3, 11)])

    def test_multi_day_range_keeps_to_office_hours(self):
        slots = office_hour_slots_in_range(self.ny(3, 14), self.ny(5, 10), NEW_YORK)
        expected = [(3, h) for h in range(14, 24)] + [(4, h) for h in range(8, 24)] + [(5, 8), (5, 9)]
        self.assertEqual(self.local_hours(slots), expected)

    def test_hours_outside_office_hours_are_never_returned(self):
        self.assertEqual(office_hour_slots_in_range(self.ny(3, 0), self.ny(3, 8), NEW_YORK), [])
        slots = office_hour_slots_in_range(self.ny(3, 22), self.ny(4, 9), NEW_YORK)
        self.assertEqual(self.local_hours(slots), [(3, 22), (3, 23), (4, 8)])

    def test_empty_or_reversed_range(self):
        self.assertEqual(office_hour_slots_in_range(self.ny(3, 9), self.ny(3, 9), NEW_YORK), [])
        self.assertEqual(office_hour_slots_in_range(self.ny(3, 12), self.ny(3, 9), NEW_YORK), [])

    def test_each_office_hour_once_across_the_autumn_dst_change(self):
        # DST ends Sunday 2026-11-01 in America/New_York; Nov 1 8 AM -> Nov 2 8 AM
        slots = office_hour_slots_in_range(self.ny(1, 8), self.ny(2, 8), NEW_YORK)
        self.assertEqual(self.local_hours(slots), [(1, h) for h in range(8, 24)])
        self.assertEqual(len(set(slots)), 16)
        self.assertEqual(slots[0], datetime(2026, 11, 1, 13, 0, tzinfo=UTC))  # 8 AM EST
        # Across Oct 31 -> Nov 1 the UTC offset changes but each local hour still appears once
        slots = office_hour_slots_in_range(self.ny(31, 8, month=10), self.ny(2, 0), NEW_YORK)
        self.assertEqual(len(slots), 32)
        self.assertEqual(slots[0], datetime(2026, 10, 31, 12, 0, tzinfo=UTC))  # 8 AM EDT
        self.assertTrue(all(s.tzinfo is not None and s.utcoffset() == timedelta(0) for s in slots))


if __name__ == "__main__":
    unittest.main()
