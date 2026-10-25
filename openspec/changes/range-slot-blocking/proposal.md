## Why

Today a doctor (or support staff on their behalf) can block or unblock only one hourly slot at a time, and only
while it is not booked. Real absences — vacation, conferences, sick days — span many hours or days and often
overlap existing appointments. Worse, when a patient cancels or is moved out of an hour the doctor wanted
blocked, the database trigger and the reschedule code set that hour back to `AVAILABLE`, so another patient can
book a time the doctor is not there. Clinics need to block and unblock whole ranges safely, see which booked
patients are affected, and be sure that freed hours stay blocked.

## What Changes

- New **range block** action on Manage Availability (doctor) and Doctor Availability (support staff): from a
  date + hour to a date + hour (clinic time, half-open `[from, to)`), with a required reason category and an
  optional note.
- New **range unblock** action with the same from/to inputs.
- Every range action runs a **preview** first that shows how many slots will be created, blocked or unblocked,
  how many are already in the target state, and the booked appointments that fall in the range. Confirming
  sends back a fingerprint of that preview; if the schedule changed in between, the server refuses with 409
  and the user previews again.
- **Booked appointments inside a blocked range are never cancelled automatically.** They stay booked and are
  flagged "Needs reschedule".
- **Freed hours stay blocked**: when a flagged appointment is cancelled or rescheduled, its old slot becomes
  `BLOCKED`, not `AVAILABLE` — in the DB trigger and in application code alike. **BREAKING** (behavior):
  `DATA-TRG-01` and `BR-APT-RESCHED-04` no longer always free a slot to `AVAILABLE`.
- **Unblocking never touches appointments**: blocked slots in the range become `AVAILABLE`; flagged booked
  slots lose their flag and the appointment stays as it is.
- **Slots are created on demand**: a range that reaches days with no slots yet first gets the full default
  office-hour day (8 AM–11 PM clinic time), so a partial-day block never leaves the rest of that day empty.
  Unblock does not re-create hours the doctor deliberately deleted.
- Range blocks may reach **180 days** ahead (single-slot changes and booking stay at 30 days).
- New **Needs reschedule** work queue for support staff, sorted with appointments in the next 24 hours first,
  marked "Urgent".
- Doctors and support staff see a list of active blocks, each with "Unblock all".
- Single-slot block/unblock on the grid goes through the same rules (a one-hour range), so both paths behave
  the same.
- One audit entry per range action (with counts and affected IDs) plus entries when appointments are flagged
  or unflagged.
- Patients see only "Unavailable"; the block reason is visible to doctors, support staff and admins only.

Out of scope for this change (phase 2): a "same hours every day" recurring mode, automatic patient emails, and
contact-attempt tracking in the work queue.

## Capabilities

### New Capabilities

- `slot-range-blocking`: blocking and unblocking a range of a doctor's slots — inputs, preview and
  fingerprint, creating missing days, handling booked slots, the block record and its derived state, active
  block list, horizon, concurrency and audit.
- `blocked-slot-release`: what happens to a slot when its appointment is cancelled or rescheduled while the
  doctor still wants the hour blocked (trigger, reschedule, clinic time-zone change).
- `reschedule-queue`: the support staff "Needs reschedule" work queue and the "Needs reschedule" marking on
  the availability grid.

### Modified Capabilities

None as OpenSpec capability folders. The application's requirements live in `openspec/feature_specs/` (the
source of truth), which this change updates instead: `foundation/F02` (new table, column, trigger, migration 009),
`foundation/F04` (audit events), `foundation/F06` (range card, preview dialog, grid style, menu entry),
`foundation/F07` (test plan), `features/07-appointment-lifecycle` (slot release on cancel/reschedule),
`features/08-doctor-availability` (`BR-SLOT-04/05/06`, range rules, active blocks), `features/16-support-appointments`
(Needs Reschedule queue) and `features/21-clinic-settings-and-tenants` (zone change keeps blocks).

## Impact

- **Database**: migration `009_schedule_blocks.sql` (+ rollback) — new `schedule_blocks` table with
  row-level security, new `doctor_availability.block_id` column and index, rewritten `sync_doctor_availability`
  trigger. Schema snapshot/compare scripts in `aws_env_spin_up/scripts/` updated.
- **Backend**: `backend/app/models/` (new `ScheduleBlock`, `block_id` on `DoctorAvailability`),
  `backend/app/services/availability_service.py` (range service, slot release rule, zone-change fix),
  `backend/app/services/appointment_service.py` (reschedule release), `backend/app/api/routes/doctor.py`
  (new endpoints; single-slot endpoints reuse the range service), `backend/app/api/routes/support.py`
  (queue endpoint).
- **Frontend**: `ManageAvailabilityPage.tsx` (range card, preview dialog, active blocks, grid style),
  `SupportDoctorAvailabilityPage.tsx`, `SupportAppointmentsPage.tsx` or a new queue page, `menu.ts`, `api.ts`.
- **APIs**: new endpoints only; existing endpoints keep their shapes. `GET /doctor/availability/{id}/all` gains
  fields (`block_id`, `block_reason`, `needs_reschedule`).
- **Deployment**: the user runs the migration and deploys after local testing; the migration must be applied
  before the new backend code.
