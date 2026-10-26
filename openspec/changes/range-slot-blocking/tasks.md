Paths below are relative to `healthcare_saas_app/` unless they start with `openspec/` or `aws_env_spin_up/`.
Groups 1–2 can ship on their own (no visible change; freed slots behave as before until a block exists).
Groups 3–4 ship the backend API, 5–6 the UI, 7 the requirement docs.

## 1. Database (migration 010; 009 is `009_rate_limits_and_gender_values`)

- [x] 1.1 Write `backend/migrations/010_schedule_blocks.sql`: `schedule_blocks` table (columns per design D1, CHECK on `reason_category`, `end_time > start_time`), RLS `tenant_isolation` policy and grants as in 006/007, `doctor_availability.block_id` (FK `ON DELETE SET NULL`) + index `(doctor_id, block_id)`, `schedule_blocks` added to the audit trigger list. Acceptance: applies cleanly twice (idempotent) on a copy of the current schema.
- [x] 1.2 In the same migration, replace `sync_doctor_availability` with the release rule (cancel/delete → `BLOCKED` if `block_id` set, else `AVAILABLE`; insert → `BOOKED`). Acceptance: integration test cancels an appointment on a slot with `block_id` and finds it `BLOCKED`; without `block_id`, `AVAILABLE`.
- [x] 1.3 Write `backend/migrations/010_schedule_blocks_rollback.sql` restoring the 002 trigger and dropping the column and table. Acceptance: apply → rollback → schema equals pre-010 snapshot.
- [x] 1.4 Update `aws_env_spin_up/scripts/schema_snapshot.sql` and `aws_env_spin_up/scripts/compare_schema.py` for the new table, column, policy and trigger. Acceptance: compare reports 010 as applied on a migrated local DB.

## 2. Models and slot release

- [x] 2.1 Add `backend/app/models/schedule_block.py` (`ScheduleBlock`), export it in `backend/app/models/__init__.py`, add `block_id` to `backend/app/models/doctor_availability.py`. Acceptance: `test_route_registration` / model import tests pass.
- [x] 2.2 Add `release_slot()` to `backend/app/services/availability_service.py` and use it for the old slot in `reschedule_appointment` (`backend/app/services/appointment_service.py`). Acceptance: integration test reschedules a flagged appointment; old slot `BLOCKED`, new slot `BOOKED`.
- [x] 2.3 Fix `keep_slot_hours_in_new_zone` in `backend/app/services/availability_service.py` to carry `block_id`/`block_reason` and to reopen a flagged booked slot's hour as `BLOCKED`. Acceptance: test in `backend/tests/integration/test_clinic_timezones.py` for both cases.

## 3. Range service

- [x] 3.1 Add `office_hour_slots_in_range(start, end, tz)` to `backend/app/core/timeutils.py`. Acceptance: unit tests in `backend/tests/test_timeutils.py` for half-open ends, multi-day, office-hour filtering and the Nov 1 2026 DST change in America/New_York.
- [x] 3.2 Add range validation (end > start, clamp to next hour, all-past refusal, 180-day horizon, reason category/note rules) to `backend/app/services/availability_service.py`. Acceptance: unit tests for each error message in the spec.
- [x] 3.3 Implement `plan_range_change(db, doctor, tz, start, end, mode)` returning slots to create (full default days for empty days; missing in-range hours as `BLOCKED` for block only), rows to change, already-in-state counts, conflicts and the fingerprint (design D4). Acceptance: integration tests for "Preview over days with no slots yet", "Partial-day block on a day 20 days out", "Unblock does not restore deleted hours".
- [x] 3.4 Implement `apply_block()` and `apply_unblock()` with the per-doctor advisory lock, `FOR UPDATE` on in-range rows, fingerprint recheck (409), batched inserts, block record creation/release (`released_at`), and audit entries (design D8). Acceptance: integration tests for every "Applying a block" / "Applying an unblock" scenario, the 409 mismatch case and the overlapping-block case.
- [x] 3.5 Concurrency tests in `backend/tests/integration/test_core_flows.py` (or a new `test_range_blocking.py`): booking racing a block, two overlapping applies. Acceptance: no double booking; one side gets the documented error.
- [x] 3.6 Performance check: a 180-day block on an empty schedule completes in under 5 s locally. Acceptance: test with timing assertion (marked slow).

## 4. API

- [x] 4.1 Add request/response models and the five block/unblock endpoints (design D6) in `backend/app/api/routes/doctor.py`, reusing `_doctor_for_slot_change`. Acceptance: `backend/tests/test_role_access.py` covers doctor-own, doctor-other (403), support staff, patient (403); `test_route_registration.py` lists the new routes.
- [x] 4.2 Switch `POST /doctor/availability` (the older `POST /doctor/availability/{doctor_id}` was already removed by GAP-22) in `backend/app/api/routes/doctor.py` to the range service for a one-hour range, keeping messages, the 30-day window and the booked-slot refusal. Acceptance: existing single-slot tests pass unchanged; new test that unblocking one hour of a range block clears `block_id`.
- [x] 4.3 Add `block_id`, `block_reason`, `needs_reschedule` to `GET /doctor/availability/{doctor_id}/all` in `backend/app/api/routes/doctor.py`. Acceptance: test shows a flagged booked slot with `needs_reschedule: true`; patient-facing listings return no reason.
- [x] 4.4 Add `GET /support/reschedule-queue` in `backend/app/api/routes/support.py` (SUPPORT_STAFF, ADMIN; optional `doctor_id`; urgent-first sort; tenant-scoped). Acceptance: tests for ordering, "Urgent" within 24 h, doctor filter, 403 for patient/doctor, no cross-tenant rows (`test_row_level_security.py`).

## 5. Frontend: Manage Availability

- [x] 5.1 Add API client methods and types for the new endpoints in `frontend/src/api.ts`. Acceptance: `npm run build` type-checks.
- [x] 5.2 Build the "Block or Unblock a Time Range" card in `frontend/src/components/pages/ManageAvailabilityPage.tsx` (toggle, from/to date + hour in clinic zone, All day, reason category + note, inline validation). Acceptance: tests in `ManageAvailabilityPage.test.tsx` for validation messages and the UTC values sent.
- [x] 5.3 Add the preview/confirm dialog (counts, conflict table, acknowledgement checkbox when conflicts exist, 409 → re-preview with message) in `frontend/src/components/pages/ManageAvailabilityPage.tsx`. Acceptance: tests for confirm disabled until acknowledged, and 409 handling.
- [x] 5.4 Add the "Active Blocks" list with state and "Unblock all" in `frontend/src/components/pages/ManageAvailabilityPage.tsx`. Acceptance: test that "Unblock all" previews the block's range.
- [x] 5.5 Style flagged grid cells "Booked – Needs reschedule" (warning style, disabled, reason on hover/focus) in `frontend/src/components/pages/ManageAvailabilityPage.tsx`. Acceptance: test renders the label for a slot with `needs_reschedule: true`.
- [x] 5.6 Confirm `frontend/src/components/pages/SupportDoctorAvailabilityPage.tsx` passes `doctor_id` through for range actions. Acceptance: test for support staff blocking on a doctor's behalf.

## 6. Frontend: support queue

- [x] 6.1 Create `frontend/src/components/pages/SupportRescheduleQueuePage.tsx` (table, doctor filter, Urgent marker, Reschedule via `RescheduleAppointmentModal`, Cancel with the existing confirmation) and its route in `frontend/src/App.tsx` and `frontend/src/app/routeBreadcrumbs.ts`. Acceptance: page tests for ordering and that a rescheduled row disappears after reload.
- [x] 6.2 Add the "Needs Reschedule" menu entry with count badge in `frontend/src/config/menu.ts` (and its rendering in the header). Acceptance: `menu.test.ts` / `AppHeader.test.tsx` show "Needs Reschedule (3)" for a count of 3 and no badge for 0.
- [x] 6.3 Run `npm run build` in `frontend/`. Acceptance: production build succeeds.

## 7. Requirement docs and end-to-end

- [x] 7.1 Update `openspec/feature_specs/foundation/F02-database-schema.md` (`schedule_blocks` table, `block_id`, `DATA-TRG-01`, RLS table list, migration 010) and `foundation/F04-audit-privacy-errors-security.md` (audit event catalog for blocks and flags). Acceptance: no remaining statement that a freed slot always becomes `AVAILABLE`.
- [x] 7.2 Update `openspec/feature_specs/features/07-appointment-lifecycle.md` (release rule in `BR-APT-04`, `RESCHED-06`), `features/08-doctor-availability.md` (range block/unblock UI and API, new `BR-SLOT-12`–`22` since 04–06 were already taken, active blocks, flagged cells), `features/16-support-appointments.md` (Needs Reschedule queue), `features/21-clinic-settings-and-tenants.md` (zone change keeps `block_id`), `foundation/F06-ui-shell-and-shared-components.md` (menu entry, routes, breadcrumbs) and `foundation/F07-config-deployment-testing.md` (test plan, migration 010); close or add `GAPS.md` rows as needed. Acceptance: every new endpoint and screen has a requirement ID.
- [x] 7.3 Add a Playwright flow in `test_healthcare_saas_app/tests/e2e/`: doctor blocks a range over a booked appointment → support staff reschedules it from the queue → old hour still blocked and unbookable by a patient → doctor partially unblocks → remaining appointment untouched. Acceptance: test passes against the local stack. *Passed 2026-10-26 against the local stack (`range-blocking.e2e.spec.ts`; needs `DOCTOR_E2E_*`, `SUPPORT_E2E_*`, `PATIENT_E2E_*`).*
- [x] 7.4 Run the full backend test suite (unit + integration) from `.venv` and the frontend tests. Acceptance: all green; results reported to the user before any deploy (user runs migration 010 and the deploy).
