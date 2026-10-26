# Feature 08 — Doctor Availability and Slots

**Roles:** D (own slots), S (any doctor of the clinic); all signed-in roles read ·
**Routes:** `/doctors/manage-availability`, `/support/doctor-availability` ·
**API:** `GET /doctors`, `GET /doctors/me`, `GET /doctor/availability/{doctor_id}/all`, `POST /doctor/availability`,
`DELETE /doctor/availability/{doctor_id}`, `POST /doctor/availability/{doctor_id}/blocks/preview`,
`POST /doctor/availability/{doctor_id}/blocks`, `POST /doctor/availability/{doctor_id}/unblock/preview`,
`POST /doctor/availability/{doctor_id}/unblock`, `GET /doctor/availability/{doctor_id}/blocks` ·
**Depends on:** F02, F03, F05, 15 (doctor search) · **Traces to:** `BR-SLOT-*`, `DOC-AVAIL-*`, `SUP-AV-*`

## 1. Purpose

Each doctor has one row per bookable clinic hour. Slots are generated automatically for the coming week, and the
doctor (or support staff on their behalf) can block, unblock, add and delete individual hours, and block or
unblock whole ranges (vacations, conferences, sick days) up to 180 days ahead. Booked appointments inside a
blocked range are never cancelled automatically: they stay booked and are flagged "Needs reschedule" for support
staff ([16](16-support-appointments.md) §4a).

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
- **BR-SLOT-05 Booked slots are protected.** A `BOOKED` slot is never blocked, unblocked, re-added or deleted by
  a single-slot change: **400 "Cannot modify a patient-booked slot."**. Its status changes only through booking,
  cancellation or rescheduling; a range block or unblock may set or clear its `block_id` (the "Needs reschedule"
  flag) but never its status (BR-SLOT-17/18).
- **BR-SLOT-06 Transitions** of `POST /doctor/availability {slot, is_available, block_reason?}`:

  | `is_available` | Existing slot | Result | Message |
  |----------------|---------------|--------|---------|
  | true | none | create `AVAILABLE`, `block_reason=NULL` | "Availability added successfully" |
  | true | `BLOCKED` | → `AVAILABLE`, clear `block_reason` and `block_id` | "Slot unblocked successfully" |
  | true | `AVAILABLE` | no change | "Availability updated." |
  | false | none | create `BLOCKED` with reason | "Slot blocked successfully" |
  | false | `AVAILABLE` or `BLOCKED` | → `BLOCKED`, reason = new reason | "Slot blocked successfully" |
  | any | `BOOKED` | refuse | 400 "Cannot modify a patient-booked slot." |

  A single-slot change follows the range rules for one hour: it takes the doctor's schedule lock and locks the
  slot row (BR-SLOT-21), and unblocking (or deleting) the last future hour of a range block releases that block
  (BR-SLOT-20). Single-slot blocks carry no `block_id`. The older `POST /doctor/availability/{doctor_id}` no
  longer exists (GAP-22).

- **BR-SLOT-07 Who.** A doctor changes only their own slots (profile from token; a `doctor_id` naming another
  doctor → **403 "Not allowed to change another doctor's availability."**). Support staff SHALL name the doctor
  (`doctor_id`, else **422 "doctor_id is required."**), which must be a non-deleted doctor of the tenant
  (else **404 "Doctor profile not found."**). Other roles → 403 "Forbidden for this role.".
- **BR-SLOT-08 Effective status.** When listing a doctor's slots, a slot with a live (non-cancelled, non-deleted)
  appointment at its time is reported as `BOOKED`, whatever its stored status.
- **BR-SLOT-09** The listing defaults to the next 30 days; the booking horizon in the UI is 5 weeks.
- **BR-SLOT-10** Each change writes an audit row on `doctor_availability` (`INSERT` / `UPDATE` / `DELETE`,
  `old {status}`, `new {status, slot_time}`).
- **BR-SLOT-11** Patients see slot states only — never block reasons, the "Needs reschedule" flag or who booked
  a slot. `GET /doctor/availability/{id}/all` returns `block_id`, `block_reason` and `needs_reschedule` only to
  DOCTOR, SUPPORT_STAFF and ADMIN callers; nothing is sent to patients about blocks.

### 2.1 Range block and unblock

- **BR-SLOT-12 Range input.** A range is `start` and `end`, each a clinic-local date and whole hour sent as UTC ISO
  datetimes, **half-open**: a slot at `t` is in the range when `start <= t < end`. Only office hours (8 AM–11 PM
  slot starts, clinic time) are affected, walked day by day in the clinic zone (F05 `BR-TIME-08`).
  `end <= start` → **422 "End must be after start."**. A `start` in the past moves forward to the next whole
  hour; if nothing is left → **400 "Range is entirely in the past."**. Unparsable times → 422 "Invalid datetime
  format.".
- **BR-SLOT-13 Horizon.** `end` may be at most 180 days after now → else **400 "Cannot change slots beyond 180
  days."**. Single-slot changes and booking keep their 30-day window (BR-SLOT-04).
- **BR-SLOT-14 Block reason.** A block needs `reason_category` ∈ `VACATION`, `CONFERENCE`, `SICK`, `PERSONAL`,
  `ADMINISTRATIVE`, `OTHER` (missing → 422; unknown → **422 "Please choose a reason."**) and may carry
  `reason_note` ≤ 500 characters; `OTHER` needs a note (**422 "Please describe the reason."**). The reason is
  stored on the block and copied to each blocked slot's `block_reason` as "<Label>" or "<Label>: <note>".
- **BR-SLOT-15 Preview and fingerprint.** Every range action is previewed first (nothing changes). The preview
  carries a `fingerprint` (SHA-256 over the mode, the clamped range, the clinic days that already have slots, each
  in-range slot's `slot_time, status, block_id`, and the live appointment ids in range). Applying requires that
  fingerprint; the server recomputes it under the doctor's lock and, if it differs (a booking, cancellation or
  another range action happened since), refuses with **409 "The schedule changed. Review the changes again."**
  and changes nothing. A missing fingerprint → the same 409.
- **BR-SLOT-16 Fill missing days.** A clinic day in the range that has **no slot at all** for the doctor first
  gets its full default office-hour day (future hours only), so a partial-day block never leaves the rest of the
  day empty (BR-SLOT-02 would otherwise never fill it). On a day that already has slots, a block creates the
  missing in-range hours as `BLOCKED`; an unblock never re-creates hours the doctor deleted.
- **BR-SLOT-17 Applying a block** creates one `schedule_blocks` row (creator = caller, F02) and, in one
  transaction: `AVAILABLE` slots in range → `BLOCKED` with the block's id and reason; already `BLOCKED` slots keep
  their own block and reason; `BOOKED` slots keep `BOOKED` and get the block's id and reason (unless already
  flagged by another block) — their appointments are **not** cancelled, moved or edited and now need rescheduling.
  Repeating a block that changes nothing creates no record and raises no error ("Nothing new to block in this
  range."). Response: the counts plus `block_id` and `needs_reschedule` (appointments in range).
- **BR-SLOT-18 Applying an unblock**, in one transaction: every `BLOCKED` slot in range → `AVAILABLE` with
  `block_id` and `block_reason` cleared (whatever blocked it); every `BOOKED` slot in range loses `block_id` and
  `block_reason` (no longer flagged); appointments are not changed; empty days are filled with `AVAILABLE`
  default slots; deleted hours are not re-created. Response: counts and `released_block_ids`.
- **BR-SLOT-19 Release rule.** When an appointment stops holding a slot (cancel, row delete, reschedule away), the
  slot becomes `BLOCKED` (keeping the block's reason) if it has a `block_id`, else `AVAILABLE` — in the DB trigger
  (F02 `DATA-TRG-02`) and in `release_slot()` alike, in the same transaction, so a blocked hour never becomes
  bookable. Rescheduling only targets `AVAILABLE` slots, so nobody can be moved into a blocked hour.
- **BR-SLOT-20 Block records and state.** Blocks are never deleted by the app. A block's state comes from its
  slots: **Released** when no future slot references it (`released_at`/`released_by` are set inside the unblock,
  single-slot unblock or delete that released its last hour); **Partially released** when some future hour in its
  range has been opened (an `AVAILABLE` slot, or a booked one without a block); otherwise **Active**.
- **BR-SLOT-21 Concurrency.** Range actions (and single-slot changes) for a doctor are serialized by
  `pg_advisory_xact_lock(hashtext('slots:' || doctor_id))`, and lock the in-range slot rows `FOR UPDATE` before
  changing them. Booking keeps its own slot row lock: a booking that commits first makes the block's fingerprint
  stale (409, then the new preview shows it as booked and flags it); a booking after the block commits gets 409
  "Requested slot is not available.". Two overlapping blocks confirmed at once: one applies, the other gets 409.
- **BR-SLOT-22 Audit.** One application audit row per applied range action on `schedule_blocks` plus one per
  flagged/unflagged appointment (F04 §1.1); per-slot rows (BR-SLOT-10) are written for single-slot changes only.
  Audit rows carry ids, never patient names.

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

For DOCTOR, SUPPORT_STAFF and ADMIN callers each item also has `block_id` (or null), `block_reason` (null for
`AVAILABLE` slots) and `needs_reschedule` (`true` when the slot is booked by a live appointment and has a
`block_id`). Patients get only `slot_time` and `status` (BR-SLOT-11).

### 3.4 `POST /doctor/availability` — D (own), S (with `doctor_id`)
Request `{"slot": "<ISO>", "is_available": bool = true, "block_reason": str?, "doctor_id": str?}`.
Order: resolve the doctor (BR-SLOT-07) → parse `slot` (422 "Invalid slot timestamp.") → window check
(BR-SLOT-04) → transition (BR-SLOT-06) → audit → commit → `{"message": …}`.

### 3.5 `DELETE /doctor/availability/{doctor_id}` — D (own), S (supported API; no UI button)
Request body `{"slot_time": "<ISO>"}`. Parse → resolve doctor → window → missing → 404 "Availability slot not
found." → `BOOKED` → 400 → audit DELETE → hard delete → `{"message": "Availability deleted successfully"}`.
It is the only way to remove an hour from a doctor's schedule, so it stays part of the API. Deleting the last
future hour of a range block releases the block (BR-SLOT-20).

### 3.6 Range endpoints — D (own), S (any doctor of the tenant)

All five take `doctor_id` in the path, use `require_roles("DOCTOR", "SUPPORT_STAFF")` (others → 403 "Forbidden for
this role.") and BR-SLOT-07 (a doctor naming another doctor → 403 "Not allowed to change another doctor's
availability."; an id that isn't a UUID or not a doctor of the tenant → 404 "Doctor profile not found.").

| Method & path | Body | Result |
|---------------|------|--------|
| `POST …/{doctor_id}/blocks/preview` | `{start, end, reason_category, reason_note?}` | preview (below); nothing changes |
| `POST …/{doctor_id}/blocks` | same + `fingerprint` | BR-SLOT-17; `{message, block_id, <counts>, needs_reschedule}` |
| `POST …/{doctor_id}/unblock/preview` | `{start, end}` | preview |
| `POST …/{doctor_id}/unblock` | `{start, end, fingerprint}` | BR-SLOT-18; `{message: "Range unblocked.", <counts>, released_block_ids}` |
| `GET …/{doctor_id}/blocks` | — | blocks (below) |

Preview: `{mode, start (clamped), end, slots_to_create, created_blocked, to_block, already_blocked, to_flag,
already_flagged, to_open, already_open, to_unflag, days_to_fill, appointments: [{appointment_id, appointment_time,
patient_name, status, needs_reschedule}], fingerprint}` (block counts are 0 in an unblock preview and vice versa).
Patient names appear only in these doctor/staff responses, never in logs, errors or audit rows.

Blocks: active and partially released blocks, plus those released (or ended) in the last 30 days, by start:
`[{id, start, end, reason_category, reason_label, reason_note, created_at, released_at, state: ACTIVE |
PARTIALLY_RELEASED | RELEASED, blocked_hours, needs_reschedule, opened_hours}]` (counts are of future slots).

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
| `BOOKED` with `needs_reschedule` | "Booked – Needs reschedule" | yellow `#facc15` text, dashed yellow border and tint, `aria-disabled`, still focusable; `title` "Blocked: <reason>" | none |

`BLOCKED` cells also show "Blocked: <reason>" on hover (`title`).

### 4.1a Block or Unblock a Time Range (`RangeBlockPanel`, `UI-CMP-RANGEBLOCK`)

Card between the Doctor Details card and the grid (doctor and support screens alike), shown once the target
doctor is known:

- `h3` "Block or Unblock a Time Range", `ClinicTimeNote`, radio "Block" / "Unblock".
- "From date" / "To date" (`type=date`, today … today+180, clinic calendar), "From hour" (8:00 AM … 11:00 PM),
  "To hour (not included)" (9:00 AM … 11:00 PM and "12:00 AM (end of day)"), defaults today 9 AM → 5 PM.
  "All day" hides the hour selects and means 8 AM on the From date to the end of the To date.
- Block only: "Reason *" select ("Choose a reason", Vacation, Conference, Sick, Personal, Administrative, Other)
  and "Note" (`maxLength` 500; "Note *" when Other).
- "Preview" validates in the browser with the server's messages ("Choose a start and end date.", "End must be
  after start.", "Range is entirely in the past.", "Cannot change slots beyond 180 days.", "Please choose a
  reason.", "Please describe the reason.") shown as an inline alert, then converts the clinic-time inputs to UTC
  (`zonedTimeToDate`) and calls the preview endpoint.
- **Preview dialog** (`role="dialog"`): title "Block|Unblock <from> – <to>"; counts — block: "Slots to create: n
  (m blocked)" (when n > 0), "Open slots to block", "Already blocked", "Booked appointments in range"; unblock:
  "Blocked slots to open", "Appointments to clear "Needs reschedule" from", "Days to fill with default slots"
  (when > 0), "Deleted hours are not restored."; then a table of the appointments (Date & Time, Patient,
  Status). When a block has appointments, an acknowledgement checkbox ("These appointments stay booked and are
  marked "Needs reschedule". Support staff will contact the patients.") must be ticked before "Confirm" enables.
  "Cancel" closes. On 409 "The schedule changed. Review the changes again." the dialog previews again, shows that
  message and needs a fresh acknowledgement; other errors show in the dialog.
- After a successful apply: the dialog closes, a status line shows the server message (block: "+ n booked
  appointment(s) need rescheduling." when n > 0), and the grid and the block list reload.

### 4.1b Active Blocks

Card "Active Blocks": "No active blocks." or a table of non-released blocks — From, To (clinic time), Reason
("<Label>: <note>"), State ("Active" / "Partially released"), Hours blocked, Needs reschedule, and "Unblock all",
which opens the unblock preview for that block's own `[start, end)`.

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
- Every change, including range actions, sends the picked doctor's id (BR-SLOT-07); the Block or Unblock a Time
  Range card and Active Blocks list are those of §4.1a/b.

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
- **F08-AC-10** Given a block from Nov 3 9 AM to 12 PM, Then 9, 10 and 11 AM are `BLOCKED` and 12 PM is not; given
  Nov 3 2 PM to Nov 5 10 AM, Then Nov 3 2–11 PM, all of Nov 4 and Nov 5 8–9 AM are affected and nothing outside
  office hours is created.
- **F08-AC-11** Given 10:20 AM, When blocking 8 AM–1 PM today, Then only 11 AM and 12 PM are affected.
- **F08-AC-12** Given a day with 16 slots, 3 booked and 2 blocked, When a block over the day is previewed, Then
  11 to block, 2 already blocked, 3 appointments listed, and nothing changed.
- **F08-AC-13** Given two days with no slots, Then the preview reports 32 slots to create; given a 2–4 PM block on
  an empty day 20 days out, Then that day has 16 slots, 2 PM and 3 PM `BLOCKED`, the rest `AVAILABLE`.
- **F08-AC-14** Given a deleted 9 AM slot, When 8–11 AM is unblocked, Then no 9 AM slot appears; When 8–11 AM is
  blocked, Then 8, 9 and 10 AM exist and are `BLOCKED`.
- **F08-AC-15** Given a block over 3 booked appointments, Then the slots stay `BOOKED`, the appointments are
  unchanged and flagged, and there is one audit row for the block and one per appointment, with ids only.
- **F08-AC-16** Given blocks Nov 3–5 and then Nov 4–6, Then Nov 4–5 keep the first block and reason and the second
  preview counted them as already blocked; repeating a block blocks nothing new and raises no error.
- **F08-AC-17** Given a patient books an hour in the range between preview and confirm, Then confirm → 409 and the
  next preview lists the new appointment.
- **F08-AC-18** Given an unblock over a block with 3 appointments, Then open hours become `AVAILABLE`, the
  appointments keep their time and status and leave the queue, and the block becomes Released; a partial unblock
  leaves the rest blocked and the block Partially released.
- **F08-AC-19** Given a range ending 150 days ahead, Then it succeeds; 181 days → 400 "Cannot change slots beyond
  180 days."; category Other without a note → 422 "Please describe the reason.".
- **F08-AC-20** Given a range block's hour unblocked from the grid, Then its `block_id` is cleared and the block
  is Partially released.
- **F08-AC-21** Given a booking and a block of the same hour at the same moment, Then exactly one succeeds and
  there is never a double booking; given two overlapping blocks confirmed at once, Then one gets 409.
- **F08-AC-22** Given a clinic in `America/New_York`, When Nov 1 8 AM → Nov 2 8 AM is blocked across the autumn
  clock change, Then each office hour of Nov 1 is blocked exactly once.
- **F08-AC-23** Given a 180-day block on an empty schedule, Then preview + apply finish in under 5 s.
- **F08-AC-24** Given a week with 2 flagged appointments, Then those 2 cells read "Booked – Needs reschedule" and
  can't be clicked; a patient's listing of the same doctor carries no block fields.

## 7. Reference implementation

`backend/app/api/routes/doctor.py` (availability and range endpoints, `_doctor_for_slot_change`,
`_check_slot_window`), `services/availability_service.py` (`ensure_default_slots`, `release_slot`,
`plan_range_change`, `apply_block`, `apply_unblock`, `list_blocks`), `models/schedule_block.py`,
`migrations/010_schedule_blocks.sql`, `frontend/src/components/pages/ManageAvailabilityPage.tsx`,
`components/common/RangeBlockPanel.tsx`, `SupportDoctorAvailabilityPage.tsx`, tests `ManageAvailabilityPage.test.tsx`,
`SupportDoctorAvailabilityPage.test.tsx`, `tests/integration/test_range_blocking.py`, `test_clinic_timezones.py`.
