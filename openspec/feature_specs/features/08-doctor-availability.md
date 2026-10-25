# Feature 08 — Doctor Availability and Slots

**Roles:** D (own slots), S (any doctor of the clinic); all signed-in roles read ·
**Routes:** `/doctors/manage-availability`, `/support/doctor-availability` ·
**API:** `GET /doctors`, `GET /doctors/me`, `GET /doctor/availability/{doctor_id}/all`, `POST /doctor/availability`,
`DELETE /doctor/availability/{doctor_id}` ·
**Depends on:** F02, F03, F05, 15 (doctor search) · **Traces to:** `BR-SLOT-*`, `DOC-AVAIL-*`, `SUP-AV-*`

## 1. Purpose

Each doctor has one row per bookable clinic hour. Slots are generated automatically for the coming week, and the
doctor (or support staff on their behalf) can block, unblock, add and delete individual hours.

## 2. Business rules

- **BR-SLOT-01 Default generation.** Whenever `GET /doctor/availability/{doctor_id}/all` is called, for each of the
  next 7 clinic-local days (today included) that has **no slot at all** for that doctor (any status, past or
  future, within `[clinic today 00:00, today+7 00:00)`), insert the full set of office-hour slots (8:00–23:00
  local, F05) that are strictly in the future, all `AVAILABLE`.
- **BR-SLOT-02** A day that already has at least one slot is left untouched, so a doctor's manual changes
  (deleted or blocked hours) are never overwritten.
- **BR-SLOT-03** Generation is concurrency-safe: `INSERT … ON CONFLICT DO NOTHING` on `(doctor_id, slot_time)`;
  a failure is rolled back, logged ("Failed to create default availability slots for doctor <id>") and SHALL NOT
  fail the read.
- **BR-SLOT-04 Change window.** Any slot change (add, block, unblock, delete) is refused for slot times before now
  (**400 "Cannot update slots earlier than now."**) or more than 30 days ahead
  (**400 "Cannot update slots beyond 30 days."**).
- **BR-SLOT-05 Booked slots are protected.** A `BOOKED` slot is never blocked, unblocked, re-added or deleted:
  **400 "Cannot modify a patient-booked slot."**. It changes only through booking, cancellation or rescheduling.
- **BR-SLOT-06 Transitions** of `POST /doctor/availability {slot, is_available, block_reason?}`:

  | `is_available` | Existing slot | Result | Message |
  |----------------|---------------|--------|---------|
  | true | none | create `AVAILABLE`, `block_reason=NULL` | "Availability added successfully" |
  | true | `BLOCKED` | → `AVAILABLE`, clear `block_reason` | "Slot unblocked successfully" |
  | true | `AVAILABLE` | no change | "Availability updated." |
  | false | none | create `BLOCKED` with reason | "Slot blocked successfully" |
  | false | `AVAILABLE` or `BLOCKED` | → `BLOCKED`, reason = new reason | "Slot blocked successfully" |
  | any | `BOOKED` | refuse | 400 "Cannot modify a patient-booked slot." |

- **BR-SLOT-07 Who.** A doctor changes only their own slots (profile from token; a `doctor_id` naming another
  doctor → **403 "Not allowed to change another doctor's availability."**). Support staff SHALL name the doctor
  (`doctor_id`, else **422 "doctor_id is required."**), which must be a non-deleted doctor of the tenant
  (else **404 "Doctor profile not found."**). Other roles → 403 "Forbidden for this role.".
- **BR-SLOT-08 Effective status.** When listing a doctor's slots, a slot with a live (non-cancelled, non-deleted)
  appointment at its time is reported as `BOOKED`, whatever its stored status.
- **BR-SLOT-09** The listing defaults to the next 30 days; the booking horizon in the UI is 5 weeks.
- **BR-SLOT-10** Each change writes an audit row on `doctor_availability` (`INSERT` / `UPDATE` / `DELETE`,
  `old {status}`, `new {status, slot_time}`).
- **BR-SLOT-11** Patients see slot states only — never block reasons or who booked a slot.

## 3. API

### 3.1 `GET /doctors` — any signed-in role
Non-deleted doctors of the caller's tenant **whose login is active and not deleted** (so doctors awaiting
approval aren't offered to patients), ordered by
`full_name` asc: `[{id, name, specialty, license_number}]`.

### 3.2 `GET /doctors/me` — D
`{id, name, specialty, license_number}` of the caller's profile; 404 "Doctor not found".

### 3.3 `GET /doctor/availability/{doctor_id}/all?days=30` — any signed-in role
1. Doctor must be non-deleted and in the tenant, else return `[]` (not 404).
2. Run default generation (BR-SLOT-01) in the clinic zone.
3. Return every slot (any status) with `now ≤ slot_time ≤ now + days`, ordered by time:
   `[{"slot_time": "<ISO>", "status": "AVAILABLE" | "BOOKED" | "BLOCKED"}]`, with BR-SLOT-08 applied (live
   appointments of that doctor at those times, `status <> CANCELLED`, `deleted_at IS NULL`).

### 3.4 `POST /doctor/availability` — D (own), S (with `doctor_id`)
Request `{"slot": "<ISO>", "is_available": bool = true, "block_reason": str?, "doctor_id": str?}`.
Order: resolve the doctor (BR-SLOT-07) → parse `slot` (422 "Invalid slot timestamp.") → window check
(BR-SLOT-04) → transition (BR-SLOT-06) → audit → commit → `{"message": …}`.

### 3.5 `DELETE /doctor/availability/{doctor_id}` — D (own), S (supported API; no UI button)
Request body `{"slot_time": "<ISO>"}`. Parse → resolve doctor → window → missing → 404 "Availability slot not
found." → `BOOKED` → 400 → audit DELETE → hard delete → `{"message": "Availability deleted successfully"}`.
It is the only way to remove an hour from a doctor's schedule, so it stays part of the API.

## 4. UI — Manage Availability grid (`UI-CMP-AVAILGRID`)

Used by the doctor at `/doctors/manage-availability` and embedded by support staff (§5).

### 4.1 Layout

1. Doctor screen only: `h2` "Manage Availability".
2. **Doctor Details** card (`h3` "Doctor Details"): Name, Phone, Specialization ("N/A" if empty), License Number
   ("N/A"). Doctor screen loads `GET /doctor/profile` ("Loading doctor information..." while loading); support
   screen shows Name, Specialization, License Number from the picked doctor (no phone).
3. Grid card:
   - Navigation row: "Previous Week" (disabled and grey at week 0) · "Week of M/D - M/D" with `ClinicTimeNote`
     · "Next Week" (disabled and grey at week 4: slots can be changed only 30 days ahead).
   - Message box (only when set): success = blue text/border `#42b5f5` on `rgba(66,181,245,0.1)`, error = pink.
     Success messages clear after 5 s; errors stay until the next action.
   - "Loading availability..." while loading, else a table:
     - header row: "Time" column, then 7 day columns (week 0 starts **today**, clinic time), each "Mon" over
       `MM/DD/YYYY`;
     - 16 rows, one per office hour ("8:00 AM" … "11:00 PM"), first cell the label;
     - each cell: nothing for past cells (earlier day, or today at or before the current clinic hour), otherwise a
       button by state:

| State | Label | Style | Click |
|-------|-------|-------|-------|
| no slot | "Click to Add" | dashed 2 px `#42b5f5` border, blue tint; hover brighter + scale 1.02 | add as available |
| `AVAILABLE` | "Available" | teal `#49d7c2` text/border, `rgba(73,215,194,0.2)` fill | prompt "Enter reason for blocking this slot:"; Cancel aborts; OK → block with the entered reason |
| `BLOCKED` | "Blocked" | red `#ef4444` text/border, `rgba(239,68,68,0.2)` fill | `confirm("Unblock this slot? Patients will be able to book it again.")`; Cancel aborts; OK → unblock (no reason is asked or sent; unblocking clears it) |
| `BOOKED` | "Patient Booked" | orange `#fb923c`, `not-allowed` cursor, disabled | none |

### 4.2 Data and actions

- Load: target doctor = the support-picked doctor, else `GET /doctors/me`; then
  `GET /doctor/availability/{id}/all?days=30`. Reload on week change and after every action. Load errors show in
  the message box.
- Cells are matched to slots by clinic cell key (F05 §3.1). The action sends
  `POST /doctor/availability {slot: zonedTimeToDate(day, hour, tz).toISOString(), is_available, block_reason,
  doctor_id: <target doctor id>}`.
- Success messages shown: "Slot blocked successfully", "Slot unblocked successfully", "Slot added successfully".
  Failure: the server's message (e.g. "Cannot update slots beyond 30 days.").

## 5. UI — Support staff: Doctor Availability (`/support/doctor-availability`)

- `h2` "Doctor Availability"; muted text "Block or unblock a doctor's slots on their behalf. Patient-booked slots
  can't be changed here."
- `SupportSearchPanel kind="doctor"` (F06 §6.2). Picking a doctor highlights the row and renders the grid of §4
  for that doctor (remounted per doctor), without the "Manage Availability" heading.
- Every change sends `doctor_id` (BR-SLOT-07).

## 6. Acceptance criteria

- **F08-AC-01** Given a doctor with no slots, When the grid opens at 10:20 clinic time, Then today has slots
  11:00–23:00 and each of the next 6 days has 16 slots, all Available.
- **F08-AC-02** Given a day where the doctor blocked 9 AM, When the listing is requested again, Then that day is
  not regenerated (blocked stays blocked, deleted hours stay missing).
- **F08-AC-03** Given an Available slot, When blocked with reason "Conference", Then status `BLOCKED`,
  `block_reason` "Conference", it is not bookable, and unblocking restores `AVAILABLE` with a NULL reason.
- **F08-AC-04** Given a booked slot, When blocked via the API, Then 400 "Cannot modify a patient-booked slot.".
- **F08-AC-05** Given a slot 31 days ahead, When added, Then 400 "Cannot update slots beyond 30 days.".
- **F08-AC-06** Given support staff without `doctor_id`, Then 422 "doctor_id is required."; given a doctor naming
  another doctor's id, Then 403.
- **F08-AC-07** Given a slot whose stored status is `AVAILABLE` but has a live appointment, Then the listing
  reports `BOOKED`.
- **F08-AC-08** Given two concurrent first loads for the same doctor, Then no duplicate slots and no error.
- **F08-AC-09** Given a clinic in `America/New_York` on 2026-03-08 (spring forward), Then 16 slots exist that day
  at 8:00–23:00 local.

## 7. Reference implementation

`backend/app/api/routes/doctor.py` (availability endpoints, `_doctor_for_slot_change`, `_check_slot_window`),
`services/availability_service.py` (`ensure_default_slots`), `frontend/src/components/pages/ManageAvailabilityPage.tsx`,
`SupportDoctorAvailabilityPage.tsx`, tests `ManageAvailabilityPage.test.tsx`, `tests/integration/test_clinic_timezones.py`.
