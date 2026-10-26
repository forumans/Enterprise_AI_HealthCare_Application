## Context

Slots live in `doctor_availability`, one row per doctor per clinic hour, with a single `status`
(`AVAILABLE` / `BOOKED` / `BLOCKED`) and an optional `block_reason`. Booking and rescheduling
(`backend/app/services/appointment_service.py`) lock the slot row and require `AVAILABLE`. Three places free a
slot and all set it to `AVAILABLE` unconditionally:

1. the `sync_doctor_availability` trigger (migration 002) on cancel (`status = 'CANCELLED'`) and on row delete;
2. `reschedule_appointment`, for the old slot;
3. `keep_slot_hours_in_new_zone`, which reopens a booked slot's hour in the new zone after a clinic zone change.

Default slots come from `ensure_default_slots`, which fills only the next 7 days and skips any day that already
has a slot (`BR-SLOT-02`). Single-slot changes are limited to 30 days ahead. There are two single-slot upsert
endpoints in `backend/app/api/routes/doctor.py` (`POST /doctor/availability` used by the UI, and the older
`POST /doctor/availability/{doctor_id}`). Every table is tenant-isolated by RLS (migration 007), and the
Lambda pool has one connection, so each request runs in one connection and transaction.

## Goals / Non-Goals

**Goals:**
- Block and unblock a range of hours in one action, with a preview of the impact before anything changes.
- Keep booked appointments untouched, flag them, and give support staff a work queue.
- Guarantee that an hour the doctor wants blocked never becomes bookable when its appointment is freed.
- One set of slot rules for range and single-slot actions.

**Non-Goals:**
- "Same hours every day" recurring blocks (phase 2).
- Automatic patient emails or SMS; contact-attempt tracking in the queue (phase 2).
- Changing office hours, slot length, the 30-day booking window or the 7-day default generation.

## Decisions

### D1. Block record + `block_id` on the slot (not a pure overlay, not a flag-only column)

Add a `schedule_blocks` table and a nullable `doctor_availability.block_id` (FK, `ON DELETE SET NULL`, indexed
on `(doctor_id, block_id)`). `block_id` means "the doctor wants this hour blocked". Booked + `block_id` is the
"Needs reschedule" state; no new enum value is needed.

- *Alternative: flag-only column (`pending_block boolean`)*. Smaller, but loses grouping ("Vacation Nov 3–7"),
  the active-blocks list, "Unblock all", and block-level audit.
- *Alternative: pure overlay (blocks computed at read/booking time)*. Cleanest model, used by large EHR
  schedulers, but every read, the slot picker and booking would have to join blocks. Too large a change for the
  value; the per-slot row already exists for every bookable hour.

`schedule_blocks` columns: `id`, `tenant_id`, `doctor_id`, `start_time`, `end_time` (UTC, half-open),
`reason_category` (text with CHECK on the six values), `reason_note` (text, ≤ 500), `created_by`, `created_at`,
`released_at`, `released_by`. RLS `tenant_isolation` policy as in migration 007.

Block state (Active / Partially released / Released) is derived by counting future slots in the range that still
reference the block; `released_at` is set when that count reaches zero, inside the unblock transaction.

### D2. One release rule, enforced in the database and the service

Release = `status := CASE WHEN block_id IS NOT NULL THEN 'BLOCKED' ELSE 'AVAILABLE' END`, and
`block_reason` keeps the block's reason when `BLOCKED`.

- The trigger is rewritten in migration 010 with this rule for cancel and delete.
- A `release_slot(slot)` helper in `availability_service.py` is used by `reschedule_appointment`.
- `keep_slot_hours_in_new_zone` carries `block_id`/`block_reason` for moved slots and applies the rule to the
  reopened hour of a booked slot.

Because the release happens in the same transaction as the cancel/reschedule and booking requires `AVAILABLE`
under a row lock, the freed hour is never bookable. *Alternative: application-only fix* — rejected because the
trigger would still free slots on any cancel path.

### D3. Range walking in clinic time; fill whole default days first

A pure function in `backend/app/core/timeutils.py`, `office_hour_slots_in_range(start, end, tz)`, returns the
UTC slot times whose clinic-local start is 8–23 and that fall in `[start, end)`, walking local dates (DST-safe,
reusing the existing `default_slot_times` construction). The service then:

1. clamps `start` to the next whole hour after now;
2. finds clinic-local days in the range with no slot for the doctor and inserts their full default day
   (`ON CONFLICT DO NOTHING`, batched by `_INSERT_BATCH`) — this keeps `BR-SLOT-02` from leaving a day
   permanently partial;
3. for a block, inserts missing in-range hours on days that already have slots as `BLOCKED`;
4. updates the in-range rows.

Unblock does steps 1–2 and 4 only, so deliberately deleted hours are not re-created.

### D4. Preview + fingerprint (optimistic check), per-doctor advisory lock on apply

`preview` and `apply` share one function that computes the plan; `preview` rolls back, `apply` commits. The
fingerprint is a SHA-256 over sorted `(slot_time, status, block_id)` of existing in-range rows plus sorted live
appointment ids in range, so it is cheap and stable. Apply takes
`pg_advisory_xact_lock(hashtext('slots:' || doctor_id))`, selects the in-range rows `FOR UPDATE` ordered by
`slot_time`, recomputes the fingerprint and returns 409 if it differs.

- *Alternative: lock only, no fingerprint*. Safe for data, but the doctor could confirm an impact they never
  saw (e.g. a booking that arrived after preview). The fingerprint makes the confirmation honest.
- Booking does not take the advisory lock; it relies on its existing slot row lock, which the apply's
  `FOR UPDATE` serializes against.

### D5. "Needs reschedule" is derived, not stored

`needs_reschedule = slot.status = 'BOOKED' AND slot.block_id IS NOT NULL` for a live, future appointment.
The queue query joins `appointments` → `doctor_availability` on `(doctor_id, appointment_time = slot_time)`
(the same join `BR-SLOT-08` uses) plus patients, users and doctors. Nothing to keep in sync.

### D6. Endpoints

| Method & path | Roles | Purpose |
|---|---|---|
| `POST /doctor/availability/{doctor_id}/blocks/preview` | DOCTOR (own), SUPPORT_STAFF | Block impact |
| `POST /doctor/availability/{doctor_id}/blocks` | same | Apply block (`fingerprint` required) |
| `POST /doctor/availability/{doctor_id}/unblock/preview` | same | Unblock impact |
| `POST /doctor/availability/{doctor_id}/unblock` | same | Apply unblock |
| `GET /doctor/availability/{doctor_id}/blocks` | same | Active + recently released blocks |
| `GET /support/reschedule-queue?doctor_id=` | SUPPORT_STAFF, ADMIN | Needs reschedule list |

Bodies: `{start, end, reason_category, reason_note, fingerprint?}` (UTC ISO). Responses carry counts and the
conflict list. Patient names appear only in these staff/doctor responses (same exposure as existing
appointment lists), never in logs or error messages. `GET /doctor/availability/{doctor_id}/all` gains
`block_id`, `block_reason` and `needs_reschedule` per slot.

The single-slot `POST /doctor/availability` keeps its contract and messages but calls the range service for a
one-hour range (skipping preview). The older `POST /doctor/availability/{doctor_id}` is switched to the same
code path; it is not removed in this change.

### D7. Frontend

- `ManageAvailabilityPage.tsx` (also used by support staff): new "Block or Unblock a Time Range" card under the
  doctor details — Block/Unblock toggle, From date + hour, To date + hour (hour dropdowns 8 AM–11 PM, clinic
  zone label), "All day" checkbox (from 8 AM on the start date to the end of the end date), reason category +
  note for block. "Preview" opens a dialog with the counts and conflict table, an acknowledgement checkbox when
  there are conflicts, and "Confirm". A 409 re-runs the preview with the message. An "Active Blocks" list sits
  below, with "Unblock all". Grid cells for flagged slots use a warning style and the label
  "Booked – Needs reschedule".
- New `SupportRescheduleQueuePage.tsx` at `/support/needs-reschedule` reusing `RescheduleAppointmentModal`
  and the existing cancel confirmation; menu entry with count badge in `menu.ts`.
- All date/hour inputs are built and shown in the clinic zone (existing utils), sent as UTC.

### D8. Audit

One application audit entry on `schedule_blocks` per apply (action `INSERT` for block, `UPDATE` for unblock)
with counts and affected ids, plus one `UPDATE` entry per flagged/unflagged appointment
(`new_data = {"needs_reschedule": true|false, "block_id": ...}`). The per-slot `_audit_slot` entries are not
written for range actions (hundreds of rows per action); single-slot actions keep them. `schedule_blocks` is
added to the `audit_trigger_function` table list for the DB-level safety net.

## Risks / Trade-offs

- [The trigger rewrite changes behavior for every cancellation] → Rule is identical when `block_id` is NULL,
  which is every slot until the first range block; covered by trigger tests on a real Postgres.
- [Large ranges (180 days ≈ 2,900 slots) in one Lambda request] → Batched inserts, single `UPDATE … WHERE id
  = ANY(...)` per status group; a test asserts a 180-day block finishes well inside the API timeout.
- [Fingerprint mismatch is common when the clinic is busy] → The UI re-runs the preview automatically and
  shows what changed; the doctor confirms again.
- [`ON DELETE SET NULL` on `block_id` silently unblocks if a block row is deleted] → Block rows are never
  deleted by the application (release sets `released_at`); only tenant cascade removes them.
- [The flag is derived from `appointment_time = slot_time`] → Same join the app already relies on
  (`BR-SLOT-08`); no new consistency risk.
- [Doctors may expect unblock to restore deleted hours] → The preview states "Deleted hours are not restored";
  they can still add a single slot from the grid.

## Migration Plan

1. Add `backend/migrations/010_schedule_blocks.sql` and `010_schedule_blocks_rollback.sql`: create
   `schedule_blocks` with RLS and grants (as in 006/007), add `doctor_availability.block_id` + index, replace
   `sync_doctor_availability`, add `schedule_blocks` to the audit trigger. Existing rows get `block_id = NULL`,
   so behavior is unchanged until a range block is made.
2. Update `aws_env_spin_up/scripts/schema_snapshot.sql` / `compare_schema.py` for the new table, column and
   policy.
3. Test locally; the user applies 010 to RDS, then deploys backend and frontend (backend code reads
   `block_id`, so the migration goes first).
4. Rollback: run the rollback script (restores the 002 trigger, drops the column and table) and redeploy the
   previous build. Slots blocked by ranges stay `BLOCKED` with their reason; flagged booked slots simply lose
   their flag.

## Open Questions

- Should doctors (not only support staff) see the Needs Reschedule list for their own appointments? Proposed:
  not in phase 1; doctors see flagged cells in the grid.
- Should an admin be able to view/cancel any block across doctors? Proposed: admins use the support screens.
