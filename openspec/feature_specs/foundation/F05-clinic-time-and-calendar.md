# F05 — Clinic Time, Office Hours and the Calendar

Every clinic runs on its own IANA time zone. All scheduling rules, "today", weeks, office hours and every time
shown in the browser use **clinic time**, whatever zone the server or the viewer's device is in.

## 1. Rules (`BR-TIME`)

- **BR-TIME-01** Instants are stored and exchanged in UTC (ISO-8601). Responses include an offset (`+00:00`).
  Clients treat a timestamp without an offset as UTC; the server treats a naive input as UTC.
- **BR-TIME-02** Each clinic's zone is `tenants.timezone` (e.g. `America/Chicago`, `Europe/London`,
  `Asia/Kolkata`). DST follows IANA rules: 8 AM stays 8 AM local all year; a DST day is 23 or 25 hours long.
  `CLINIC_TIMEZONE` (default `America/New_York`) is only the zone given to a clinic created without one, and the
  fallback for an unknown stored name.
- **BR-TIME-03** A clinic week runs Monday 00:00 to the next Monday 00:00, clinic time.
- **BR-TIME-04** The browser shows every time, and lays out every grid, in clinic time. Login returns
  `clinic_timezone`; the SPA provides it through `ClinicTimeZoneContext` (default `America/New_York` before
  sign-in). Every calendar shows the note "All times are clinic time: <abbr> (<zone with spaces>)", e.g.
  "All times are clinic time: EDT (America/New York)".
- **BR-TIME-05 Office hours.** Hourly slots starting 8:00 AM through the slot starting 11:00 PM clinic time:
  16 slots/day, 7 days/week, 60 minutes each. Constants `WORKDAY_FIRST_SLOT_HOUR = 8`,
  `WORKDAY_LAST_SLOT_HOUR = 23`, `SLOT_DURATION_MINUTES = 60` defined once per tier and kept in sync.
- **BR-TIME-06** When a clinic's zone changes, future open and blocked slots move to the same local date and hour
  in the new zone; booked slots keep their instant ([21](../features/21-clinic-settings-and-tenants.md)).
- **BR-TIME-07** Booking horizon shown to users: 5 weeks (current week + 4). Slot changes: now … now+30 days.
  Default generation: next 7 clinic days ([08](../features/08-doctor-availability.md)).

## 2. Backend helpers (`app/core/timeutils.py`)

| Function | Contract |
|----------|----------|
| `is_valid_timezone(name)` | `name in zoneinfo.available_timezones()` (cached) |
| `clinic_zone(name)` | `ZoneInfo(name)` if valid else `ZoneInfo(DEFAULT_CLINIC_TIMEZONE)` (LRU-cached) |
| `utc_now()` | aware UTC now |
| `to_utc(dt)` | naive → attach UTC; aware → convert to UTC |
| `parse_client_datetime(s)` | `datetime.fromisoformat(s.replace("Z", "+00:00"))` → `to_utc`; raises `ValueError` |
| `clinic_today(tz, now=None)` | today's date in `tz` |
| `clinic_date(dt, tz)` | local date of an instant |
| `clinic_day_start(day, tz)` | UTC instant of local midnight starting `day` |
| `clinic_day_bounds(day, tz)` | `[start, next-day start)` |
| `clinic_week_bounds(anchor, tz)` | Monday-to-Monday local range containing `anchor`, as UTC |
| `same_wall_clock(dt, old_tz, new_tz)` | instant showing the same local date/time in `new_tz` |
| `default_slot_times(tz, now=None, days=7)` | for `d` in 0..days-1, for hour 8..23: `datetime(y,m,d,hour,tzinfo=tz).astimezone(UTC)`, keeping only slots strictly after `now` |

Never build naive datetimes for queries.

## 3. Frontend helpers (`src/utils/index.ts`)

Calendar days are plain `{year, month (1-12), day}` objects so no `Date` round-trip can shift them.

| Function | Contract |
|----------|----------|
| `parseServerDate(s)` | append `Z` unless the string ends with `Z` or `±hh:mm`/`±hhmm`, then `new Date(...)` |
| `browserTimeZone()` | `Intl.DateTimeFormat().resolvedOptions().timeZone` or default |
| `supportedTimeZones(current)` | `Intl.supportedValuesOf('timeZone')`, with `current` prepended if missing |
| `zonedParts(date, tz)` | `{year, month, day, hour, minute}` via `Intl.DateTimeFormat('en-US', {timeZone, hourCycle:'h23', …}).formatToParts` |
| `zonedTimeToDate(day, hour, tz)` | instant at which `tz` shows `day hour:00`; start from `Date.UTC(...)` and apply two offset corrections (DST-safe) |
| `clinicToday(tz)` | today in `tz` |
| `addDays(day, n)`, `weekdayOf(day)` (0 = Sun), `mondayOf(day)`, `sameDay(a,b)` | pure date arithmetic in UTC |
| `dayKey(day)` | `"YYYY-MM-DD"` |
| `cellKey(day, hour)` | `"YYYY-MM-DDTHH:00:00"` — clinic wall-clock key of an hourly grid cell |
| `clinicSlotKey(date, tz)` | `cellKey` of the cell an instant falls in |
| `slotKeyToDate(key, tz)` | instant a cell key stands for (used before sending to the API: `.toISOString()`) |
| `formatDay(day, opts)` | `toLocaleDateString('en-US', {...opts, timeZone:'UTC'})` at noon UTC |
| `formatInZone(value, tz, opts)` | `toLocaleString('en-US', {...opts, timeZone: tz})` |
| `timeZoneAbbreviation(tz, date)` | short zone name ("PDT", "EST", "GMT+5:30") |
| `clinicTimeNote(tz)` | `All times are clinic time: ${abbr} (${tz.replace(/_/g,' ')})` |
| `OFFICE_HOUR_SLOTS` | `["8:00 AM", "9:00 AM", …, "11:00 AM", "12:00 PM", "1:00 PM", …, "11:00 PM"]` |
| `isAppointmentUpcoming(apt, now)` | false if no time or status `COMPLETED`/`CANCELLED`; else `appointment_time + 60 min > now` |

### 3.1 Matching server slots to grid cells

Grids are laid out in clinic time. A server slot `slot_time` (UTC) is matched to a cell by
`clinicSlotKey(parseServerDate(slot_time), tz) === cellKey(day, hour)`. When the user picks a cell, the client
sends `slotKeyToDate(key, tz).toISOString()` (or `zonedTimeToDate(day, hour, tz).toISOString()`).

### 3.2 Display formats (`UI-DT`)

| Use | Format (en-US, clinic zone) | Example |
|-----|------------------------------|---------|
| Appointment date/time (dialogs, support tables) | weekday short, month short, day, year, `hh:mm AM`, zone short | "Fri, Oct 23, 2026, 03:00 PM PDT" |
| Patient "My Appointments" | weekday long, month long, day, year, `hh:mm`, zone | "Friday, October 23, 2026 at 03:00 PM EDT" |
| Time only (doctor screens) | `hh:mm AM` | "09:00 AM" |
| Date of birth | `MM/DD/YYYY` by string reformatting `YYYY-MM-DD`, never via `Date` | "03/07/1985" |
| Grid column header | weekday short + `MM/DD` (booking) or `MM/DD/YYYY` (availability) | "Mon" / "10/26" |
| Week heading | `Week of M/D - M/D` (booking/availability), `Mon D, YYYY - Mon D, YYYY` (doctor weekly) | "Week of 10/25 - 10/31" |

## 4. Acceptance criteria

- **F05-AC-01** Given a clinic in `America/New_York`, When default slots are generated on 2026-11-01 (DST ends),
  Then 16 slots exist for that local day at 08:00–23:00 local, each exactly once.
- **F05-AC-02** Given a clinic in `Asia/Kolkata` (UTC+5:30), When the 8 AM cell is booked from a browser set to
  `Asia/Tokyo`, Then the API receives `02:30:00Z` that day and every screen shows 8:00 AM.
- **F05-AC-03** Given a clinic in `America/Los_Angeles`, When "today" and "this week" are computed at 11:30 PM PT
  Sunday, Then today = Sunday (PT) and the week is the Monday–Sunday ending that day.
- **F05-AC-04** Given `"2026-06-23T12:00:00"` from the API, When parsed, Then it is 12:00 UTC.
- **F05-AC-05** Frontend tests SHALL run with a browser zone (`Asia/Tokyo`) unlike any test clinic's, so any grid
  or time that follows the viewer's zone fails.

## 5. Reference implementation

`backend/app/core/timeutils.py`, `backend/tests/test_timeutils.py`, `frontend/src/utils/index.ts`,
`frontend/src/contexts/ClinicTimeZoneContext.ts`, `frontend/src/components/common/ClinicTimeNote.tsx`.
