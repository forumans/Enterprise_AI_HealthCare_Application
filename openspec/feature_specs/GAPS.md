# Known Gaps — Current Code vs. Feature Specifications

Found while reverse-engineering the code at commit `bc3b34c` (2026-10-25). GAP-02 and GAP-03 were fixed on
2026-10-25 (branch `fix/gap-02-03-doctor-checks`); their IDs are not reused. The feature specs state the
**intended** behavior; this file records where the running code differs, so that:

- an agent rebuilding from the specs knows these are deliberate corrections, not omissions, and
- the existing application can be fixed one gap at a time.

Severity: **High** = security or data integrity · **Medium** = wrong behavior users can hit · **Low** = cosmetic,
consistency, or dead code.

## 1. Security and data integrity

| ID | Severity | Where (code) | Current behavior | Intended (spec) | Recommended fix |
|----|----------|--------------|------------------|-----------------|-----------------|
| GAP-04 | Medium | `routes/admin.py` `admin_create_user` | No application audit row when an admin creates a user (only the DB trigger row). | `users` INSERT audit naming the admin ([19](features/19-admin-user-registration.md) §3, F04 §1.1). | Call `write_audit_log` before commit. |
| GAP-05 | Medium | `routes/admin.py` `soft_delete_user` | Sets `users.deleted_at` but not `users.deleted_by`. | Both set ([20](features/20-admin-account-management.md) BR-ACC-06). | Add `deleted_by=identity.user_id` to the `update(User)` values. |
| GAP-06 | Medium | `routes/auth.py` `RegisterRequest`; `routes/doctor.py` `DoctorRegisterRequest` | Server checks only name length and password length (and email length for doctors): email format, phone pattern, gender enum, DOB range and doctor age ≥ 18 are enforced only in the browser. | Server enforces the same rules as the UI ([04](features/04-patient-self-registration.md) AUTH-REGP-SRV, [05](features/05-doctor-self-registration.md) AUTH-REGD-03). | Add Pydantic validators (pattern, `Literal` gender, date checks); return the generic 422. |
| GAP-15 | Medium | `routes/patient.py` `PUT /patient/patient/profile`; `PatientProfilePage.tsx` | No server validation (any phone, any gender text, name < 3 accepted). The UI sends `undefined` for cleared optional fields, so the key is omitted and **a stored address/insurance value can never be cleared**. | Server validates name, phone, DOB, gender; UI sends `""` for cleared fields and the server stores NULL ([17](features/17-profiles.md) §2). | Use a typed request model; map `""` → NULL; send `""` from the UI. |
| GAP-16 | Low | `routes/doctor.py` `PUT /doctor/profile` | No server validation of name or phone; values not trimmed. | Validate and trim ([17](features/17-profiles.md) §3). | Typed request model. |
| GAP-23 | Medium | `routes/appointments.py` `update_appointment_status` | Any of SCHEDULED/CONFIRMED/COMPLETED can be set from any state, so a `COMPLETED` visit can be reopened. | Terminal states can't change ([07](features/07-appointment-lifecycle.md) BR-APT-05). | Refuse changes when the current status is `COMPLETED`; allow `SCHEDULED→CONFIRMED→COMPLETED` only. |

## 2. Behavior users can hit

| ID | Severity | Where | Current | Intended | Fix |
|----|----------|-------|---------|----------|-----|
| GAP-07 | Medium | `AdminRegisterPatientPage.tsx` | Gender options send "Male" / "Female" / "Other" (not the enum values), so admin-created patients store mixed-case gender. | `MALE`, `FEMALE`, `OTHER` ([19](features/19-admin-user-registration.md) §2.2). | Change option values; optionally normalize existing rows. |
| GAP-08 | Low | `PatientRegistrationPage.tsx` | Any failure shows the generic alert "Registration failed. Please try again." (e.g. a duplicate email isn't explained). | Show the server's message ([04](features/04-patient-self-registration.md) §2). | `alert(parseErrorMessage(error))` or an inline `StatusMessage`. |
| GAP-09 | Low | `ConsultationForm.tsx` | Client only checks that symptoms and diagnosis are non-empty; a 4-character symptom gets "Failed to save consultation details" from the server's 422. | Client also checks symptoms ≥ 5 and diagnosis ≥ 3 with a clear message ([12](features/12-consultation-clinical-records.md) §2.4). | Add the checks. |
| GAP-10 | Low | `ManageAvailabilityPage.tsx` | "Next Week" is never disabled; weeks beyond 30 days show "Click to Add" cells that the server rejects. | Disable at week 4 like the other grids ([08](features/08-doctor-availability.md) §4.1). | `disabled={weekOffset === 4}`. |
| GAP-12 | Low | `ManageAvailabilityPage.tsx` | Unblocking prompts "Enter reason for unblocking this slot:" but the reason is discarded (the server clears `block_reason`). | Either drop the prompt (use a plain confirm) or record the reason in the audit row. | Replace with `confirm("Unblock this slot?")`, or send it and store it in `new_data`. |
| GAP-13 | Low | `/appointments/all`, doctor lists | Cancelled appointments are soft-deleted and excluded from every list, so the pink "CANCELLED" styling on the patient and doctor screens never shows and patients can't see what they cancelled. | Product decision. The specs keep the current behavior (cancelled visits disappear); the admin list (`GET /admin/appointments`) is the only history view. | If cancelled history is wanted, add `include_cancelled=true` to `/appointments/all` and show them under Past. |
| GAP-14 | Low | `SystemDashboardPage.tsx` | Administrator "Name" uses `session.userName`, which login sets only for patients, so it always shows "System Administrator". Recent Users "Status" is computed from `is_deleted`, but the list excludes deleted users, so it always says "Active". | Show the admin's own name; status from `is_active` ([18](features/18-admin-dashboard.md)). | Return `user_name` for every role at login (profile `full_name`); use `is_active`. |
| GAP-17 | Low | `routes/audit_logs.py` | An unparseable `date_from`/`date_to` raises an unhandled `ValueError` → generic 500. | 422 "Invalid datetime format." (F04 §2). | Catch `ValueError`. |
| GAP-18 | Low | `routes/support.py` `support_list_appointments` | Joins doctors without `deleted_at IS NULL` (patients are filtered). | Filter both. | Add the condition. |
| GAP-21 | Low | `LoginPage.tsx` | The client refuses passwords shorter than 8 before calling the API, so an account with an older, shorter password (legacy bcrypt hash) can't sign in from the UI. | Either keep (all current passwords are ≥ 8) or let the server decide. | Remove the client length check on login, or migrate legacy accounts. |
| GAP-24 | Low | `routes/doctor.py` `doctor_get_appointment_details` | Validates the id by length (`< 32` or `"all"` → 400), not by UUID parsing; a 36-character non-UUID reaches the DB and errors. | 400 "Invalid appointment ID" for any non-UUID. | Parse with `uuid.UUID(...)`. |

## 3. Routing, UI consistency and dead code

| ID | Severity | Where | Current | Intended / note |
|----|----------|-------|---------|-----------------|
| GAP-01 | Low | `backend/app/main.py` | `/health` (unprefixed) is listed as a public path but the health router is mounted only under `/api`; `GET /health` returns 404. | Either mount the health router unprefixed too, or remove `/health` from the public list. The specs document `/api/health*` only (F01 §7). |
| GAP-11 | Low | `frontend/src/app/routeBreadcrumbs.ts` | No labels for `/patients/profile`, `/doctors/today-appointments`, `/doctors/manage-availability` (map has a stale `/doctors/availability`), `/doctors/profile`, `/doctors/consultation/:id`, `/admin/reset-password`; they show "Home". Also stale `/more/*` entries. | Full table in F06 §3. |
| GAP-20 | Low | `PatientDetailsCard.tsx`, `AdminRegisterAdminPage` (in `App.tsx`), `navigation.ts`, `app/breadcrumbs.ts`, `news.ts`, `useAppointments.bookAppointment/cancelAppointment` | Unused components and helpers from an earlier UI. | Safe to delete; not part of the spec. |
| GAP-22 | Low | API | Endpoints with no UI caller: `GET /availability/{id}`, `/doctor/availability/{id}/ndays`, `GET /doctor/appointments`, `/doctor/appointments/upcoming`, `GET /patient/medical-history`, `/patient/appointments/upcoming`, `PATCH /patient/profile`, `GET /patients`, `/patients/{id}/prescriptions`, `POST /patients`, `POST /doctors`, `POST /doctor/availability/{id}`, `DELETE /doctor/availability/{id}`, legacy admin email/password endpoints, `GET /admin/appointments`. | Kept in the specs as API (marked "API only"). Remove or document as public API before a v2. |
| GAP-25 | Info | `core/rate_limit.py` | Rate-limit counters are per Lambda instance. | Documented (F04 §5); add an AWS WAF rate-based rule for a global limit. |
| GAP-26 | Low | `PatientAppointmentsPage.tsx` | Loads `GET /appointments/all` twice (hook and local state) on every refresh. | One source of truth; no behavior change. |

## 4. Closing a gap

1. Fix the code and add the test named in the matching acceptance criterion.
2. Delete the row here (or mark it "Fixed in <commit>").
3. If the intended behavior changed instead, update the feature spec and remove the row.
