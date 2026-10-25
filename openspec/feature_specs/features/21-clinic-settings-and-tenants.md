# Feature 21 — Clinic Settings (Time Zone) and Tenant API

**Roles:** A (change), all signed-in (read) · **Route:** `/admin/clinic-settings` ·
**API:** `GET /tenants/current`, `PATCH /tenants/current`, `GET /tenants/{id}` · **Depends on:** F05, 08 ·
**Traces to:** `ADM-CLINIC-*`, `BR-TIME-06`, `SEC-TEN-05`

## 1. Purpose

An admin sets the clinic's IANA time zone. Office hours, "today", weeks and every time in the app follow it.
Changing it keeps doctors' open and blocked slots at the same local hours; booked appointments keep their exact
instant.

## 2. UI (`/admin/clinic-settings`)

- `h2` "Clinic Settings"; error and success `StatusMessage`s below it. "Loading clinic settings..." while
  `GET /tenants/current` loads.
- Card: `h3` clinic name; note "Office hours (8 AM - 11 PM), today's and weekly schedules, and every time in the app
  use the clinic's time zone, whatever time zone a patient or staff member is in."
- **Clinic Time Zone** select (id `clinic-timezone`): `supportedTimeZones(saved or browser zone)`, labels with `_`
  replaced by spaces, preset to the saved zone; disabled while saving; changing it clears the success message.
- Note "Clinic time now: <Thu, Oct 22, 9:41 AM PDT> (<abbr>)" for the chosen zone.
- When the browser zone differs from the chosen one: "Your computer is set to <zone>. " + link-button "Use it" that
  selects it.
- When the choice differs from the saved zone, an amber note: "Doctors' open and blocked slots will keep their
  local hours. Booked appointments keep their exact time, so they will show at a different local hour; reschedule
  any that no longer suit."
- **"Save Time Zone"** (primary; "Saving..."; disabled while saving or unchanged) →
  `confirm("Change the clinic's time zone from <old> to <new>?\n\nDoctors' open and blocked slots keep their local
  hours (a 9 AM slot stays 9 AM). Booked appointments keep their exact time, so they will show at a different local
  hour.")` → `PATCH /tenants/current {timezone}`.
- Success: saved zone updated; **the admin's session switches to the new zone immediately** (`clinicTimezone`);
  message "Clinic time zone set to <zone>. <n> upcoming slot(s) kept their local hours.". Other signed-in users
  pick it up at their next sign-in. Failure: the server message.

## 3. Zone-change algorithm (`BR-TIME-06`, `keep_slot_hours_in_new_zone`)

Inside one transaction, with the tenant row locked (`FOR UPDATE`):

1. If the new zone equals the old one → nothing moves (`slots_moved = 0`).
2. Load every slot of the tenant with `slot_time > now`.
3. Split into **booked** (`BOOKED`) and **movable** (`AVAILABLE`, `BLOCKED`).
4. Build new rows: for each movable slot, same status and `block_reason`, at
   `same_wall_clock(slot_time, old_tz, new_tz)`; for each booked slot, an `AVAILABLE` row (no reason) at the same
   local hour in the new zone — so the doctor's working hours are unchanged while the booked slot stays at its
   exact instant.
5. Drop new rows that would be in the past.
6. Delete the movable slots; insert the new rows in batches of 1,000 (`ON CONFLICT DO NOTHING`, so a new row that
   collides with an existing slot — e.g. a booked one — is dropped).
7. `slots_moved` = rows actually inserted. Update `tenants.timezone`. Audit `tenants` UPDATE
   `{timezone: old}` → `{timezone: new, slots_moved}`. Commit.

Other clinics are never touched.

## 4. API

### `GET /tenants/current` — any signed-in role
`{id, name, domain, timezone}` of the caller's tenant; 404 "Tenant not found." if missing. Used by the header
(clinic name) and this page.

### `PATCH /tenants/current` — A
Request `{"timezone": str (1..64)}` (trimmed). Unknown zone → **422 "Unknown time zone. Pick one from the list (for
example America/Chicago)."**. Response `{id, name, domain, timezone, slots_moved}`.

### `GET /tenants/{tenant_id}` — A
Only the caller's own tenant; any other id → **404 "Tenant not found."**. `{id, name, domain, timezone}`.

There is **no** tenant-creation endpoint (clinics are created by the platform operator).

## 5. Acceptance criteria

- **F21-AC-01** Given a New York clinic with a blocked 10 AM ET slot ("Vacation") and a booked 2 PM ET appointment,
  When changed to `America/Los_Angeles`, Then the blocked slot is at 10 AM PT with its reason, the appointment keeps
  its instant (11 AM PT), and a 2 PM PT slot is `AVAILABLE`.
- **F21-AC-02** Given `Mars/Olympus_Mons`, Then 422 and nothing changes.
- **F21-AC-03** Given clinic B, When clinic A changes zone, Then B's slots and zone are unchanged.
- **F21-AC-04** Given success, Then every time on the admin's screens immediately uses the new zone.
- **F21-AC-05** Given a non-admin, When calling `PATCH /tenants/current`, Then 403.
- **F21-AC-06** Given an admin asking for another tenant's id, Then 404.

## 6. Reference implementation

`frontend/src/components/pages/AdminClinicSettingsPage.tsx` (+ test), `backend/app/api/routes/tenants.py`,
`services/tenant_service.py` (`set_clinic_timezone`), `services/availability_service.py`
(`keep_slot_hours_in_new_zone`), `tests/integration/test_clinic_timezones.py`.
