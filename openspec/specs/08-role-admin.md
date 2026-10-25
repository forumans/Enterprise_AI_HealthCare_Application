# 08 — Role: Administrator

An administrator runs the clinic's accounts: registers users of every role, resets passwords, changes login
emails, deactivates/activates, soft-deletes/restores accounts, and watches clinic-wide metrics and the audit
log. Admins do not book or treat; they only see their own tenant.

## 1. Menu (top menu "Admin")

| Item | Route | Shown when |
|------|-------|-----------|
| Login Admin | `/admin/login` | signed out |
| System Dashboard | `/admin/system-dashboard` | ADMIN (landing page) |
| Register Doctor | `/admin/register-doctor` | ADMIN |
| Register Patient | `/admin/register-patient` | ADMIN |
| Register Admin | `/admin/register-admin` | ADMIN |
| Register Support Staff | `/admin/register-support-staff` | ADMIN |
| Reset Password / Email | `/admin/reset-password` | ADMIN |
| Deactivate | `/admin/deactivate` | ADMIN |

- **ADM-GEN-01** Every admin page redirects to `/admin/login` if the session is missing or not ADMIN.
- **ADM-GEN-02** Every admin endpoint requires the `ADMIN` role and scopes all reads and writes to the
  admin's tenant (`SEC-TEN`).

## 2. System Dashboard (`/admin/system-dashboard`)

- **ADM-DASH-01** Heading "System Dashboard". "Administrator" card: Name, Role, Tenant Name.
- **ADM-DASH-02 System Overview** tiles: Total Doctors, Total Patients, Appointments (To Date), Appointments
  YTD, Appointments This Month, Appointments This Week, Appointments Today.
- **ADM-DASH-03** Doctor and patient totals SHALL be server-side counts (`doctor_count`, `patient_count` from
  `GET /admin/reports`): profiles that aren't deleted and whose login isn't deleted or deactivated — never
  counts of a paged user list.
- **ADM-DASH-04** Appointment tiles come from `GET /admin/appointment-metrics`: counts of non-deleted
  appointments with `appointment_time <= now`, total and since the start of the clinic-local year, month,
  week (Monday) and day (`BR-TIME-02`). Future appointments are not counted.
- **ADM-DASH-05 Quick Actions** buttons: Register Support Staff, Register Doctor, Register Patient, Register
  Admin.
- **ADM-DASH-06 Recent Users (N)**: the 10 most recently created non-deleted users (`GET /admin/users`, newest
  first) with Name (profile name, else email), Email, Role, Status.
- **ADM-DASH-07** `GET /admin/reports` returns `doctor_count`, `patient_count`, `monthly_patient_count` (non-deleted patients),
  `diagnosis_frequency` (non-deleted medical records) and `doctor_utilization_rate` (completed appointments ÷
  doctors, 2 decimals; 0 with no doctors).

## 3. Registering users (`ADM-REG`)

All four screens post to `POST /admin/users` with `role` and the role's fields. The server creates the user and
profile together (`BR-ACC-02`), enforces `BR-ACC-01`, writes an audit entry, and returns `{id}` with 201.
Each screen has a Cancel button back to the dashboard, clears the form after success, and shows the server
error on failure.

| Screen | Role | Fields (required marked *) | Success message |
|--------|------|----------------------------|-----------------|
| Register Doctor | DOCTOR | Full Name* (VAL-01), Email* (VAL-02), Phone* (VAL-03), Password* (VAL-04), Specialty, License Number, Date of Birth* (VAL-07, 18+) | "Doctor registration successful!" |
| Register Patient | PATIENT | Full Name*, Email*, Phone*, Password*, Date of Birth* (VAL-06), Gender* (VAL-08), Address Line 1, City, State, Postal Code, Insurance Provider, Insurance Policy Number; country defaults to "USA" | "Patient registration successful!" |
| Register Admin | ADMIN | Full Name*, Email*, Phone*, Password* | "Admin registered successfully" |
| Register Support Staff | SUPPORT_STAFF | Full Name*, Email*, Phone*, Password* | "Support staff registered successfully" |

- **ADM-REG-01** Server field limits: role ∈ {PATIENT, DOCTOR, ADMIN, SUPPORT_STAFF}; full name 3–255; email
  5–255; password per VAL-04; phone ≤ 50; specialty ≤ 255; license ≤ 100; insurance ≤ 255; address lines ≤ 255;
  city/state ≤ 100; postal code ≤ 20; country ≤ 100.
- **ADM-REG-02** Malformed JSON → 422 "Invalid JSON in request body"; failed validation → 422 generic message
  (`VAL-GEN-01`).
- **ADM-REG-03** If the database lacks the `SUPPORT_STAFF` role (migration 005 not applied), creating support
  staff returns 503 "Support staff accounts aren't available yet: the database needs migration
  005_add_support_staff_role.sql."
- **ADM-REG-04** The new user belongs to the admin's tenant, whatever the request body says.

## 4. Account search (`UI-CMP-ADMINSEARCH`, used by §5 and §6)

- **ADM-SRCH-01** "Role *" dropdown from `GET /admin/roles` (Patients, Doctors, Support Staff, Admin) and a
  "Search" box (placeholder "Name, email or phone number, or * for everyone"). Missing role → "Please select a
  role"; search term per `BR-SRCH-01`. Changing the role clears results.
- **ADM-SRCH-02** `GET /admin/users/search?role=&q=` returns active (non-deleted) users of that role in the
  tenant matching name, email or phone (`BR-SRCH-02/03`): user id, role, name, email, phone, address (patients),
  date of birth, specialty (doctors), `is_active`, `is_self`.
- **ADM-SRCH-03** Results table: #, Full Name, Email, Phone, Address, Details (DOB / specialty), plus
  screen-specific columns. No results: `No <role label> match "<q>"` or "No <role label> found" for `*`.

## 5. Reset Password / Change Email (`/admin/reset-password`)

- **ADM-ACCT-01** Heading "Reset Password / Change Email". Search (§4), then click a user to show "Selected
  Account" (name, email, role) and two independent forms, each with a value and a confirmation field:
  - **Change Email** — New Email + Confirm New Email; validation VAL-02 ("Please enter a valid email address")
    and equality ("The two new email entries do not match"); confirmation dialog "Change <name>'s login email
    from <old> to <new>? They must sign in with the new email from now on."; calls
    `POST /admin/users/{user_id}/change-email` (`BR-ACC-08`).
  - **Reset Password** — New Password + Confirm New Password; VAL-04 ("Password must be at least 8 characters
    long") and equality; calls `POST /admin/users/{user_id}/reset-password` (`BR-ACC-09`).
- **ADM-ACCT-02** Actions target the clicked account by its id. The "Important Notes" box states: changes apply to
  the account you clicked; passwords must be at least 8 characters; an email already used by another account
  can't be assigned; changing the email keeps the password and resetting the password keeps the email.
- **ADM-ACCT-03** Legacy endpoints `POST /admin/reset-password` and `POST /admin/change-email` (lookup by current
  email + role) share the same rules.
- **ADM-ACCT-04** Neither action ever logs or returns the password; audit entries record `{"password_reset": true}`
  or `{email: old} → {email: new}`.

## 6. Deactivate / Activate (`/admin/deactivate`)

- **ADM-DEACT-01** Heading "Deactivate / Activate Accounts". Search (§4) with extra columns Status (Active /
  Deactivated badge) and Action ("Deactivate" red / "Activate" green; "Saving..." while busy). The admin's own row
  shows "Your account" instead of a button.
- **ADM-DEACT-02** Confirmation: "Deactivate <name> (<email>)? They will no longer be able to log in." or
  "Activate <name> (<email>)? They will be able to log in again." Calls `POST /admin/users/{id}/deactivate` or
  `/activate` (`BR-ACC-03` … `BR-ACC-05`). On success update the row in place and show "<name> has been
  deactivated/activated."; on error show the server message.
- **ADM-DEACT-03** Notes box: deactivated users can't log in and their records and appointments are kept; you
  can't deactivate your own account; at least one admin account must always stay active; a deactivated user who
  is signed in is signed out on their next action.

## 7. Soft delete and restore (API)

- **ADM-DEL-01** `PATCH /admin/users/{id}/soft-delete` soft-deletes the user and profile (`BR-ACC-06`), with audit
  entries for both rows; returns "<ROLE> soft deleted successfully."
- **ADM-DEL-02** `PATCH /admin/users/{id}/restore` restores (`BR-ACC-07`).
- **ADM-DEL-03** The same self-protection as deactivation SHALL apply: an admin cannot delete their own account
  or the last active admin.
- **ADM-DEL-04** A screen for soft delete/restore is planned (doc 01 §2.2); the APIs above are complete.

## 8. Audit log (API)

- **ADM-AUD-01** `GET /audit-logs?table=&date_from=&date_to=` returns the tenant's newest 200 entries (optionally
  filtered by table name and ISO date range): action, timestamp, performed_by, table, old, new.
- **ADM-AUD-02** Audit entries are read-only; there is no endpoint to modify or delete them.

## 9. Other admin APIs

| Endpoint | Purpose |
|----------|---------|
| `GET /admin/users?page=&page_size=` (1–500, default 25) | Paged non-deleted users, newest first, with profile name and active flag (one query) |
| `GET /admin/appointments?page=&page_size=` | Paged appointments, newest first, with doctor and patient names; cancelled visits included and flagged (`status = CANCELLED`, `is_cancelled`) |
| `GET /tenants/{id}` | The admin's own tenant only (`SEC-TEN-05`) |
| `POST /patients`, `POST /doctors` | Attach a profile to an existing user (legacy) |
| `PATCH /appointments/{id}/status`, `DELETE /appointments/{id}` | Correct an appointment's status or cancel it |

## 10. Acceptance criteria

- **ADM-AC-01** Creating a user with an email that an active account in another tenant uses returns 409.
- **ADM-AC-02** An admin cannot deactivate themselves (400) or the last active admin (409); two admins
  deactivating each other concurrently leave at least one active.
- **ADM-AC-03** A deactivated user's next request with an existing token returns 401 and the UI shows the
  session-ended notice.
- **ADM-AC-04** Resetting a password with 7 characters returns 400; with 8 it succeeds and the old password no
  longer works.
- **ADM-AC-05** Changing an email to the same email returns 400; the user can sign in with the new email and
  their password unchanged.
- **ADM-AC-06** Restoring a deleted user whose email was reused by an active account returns 409.
- **ADM-AC-07** Dashboard appointment counts exclude future and cancelled appointments and use clinic-local
  boundaries.
- **ADM-AC-08** An admin of tenant A cannot see, search, change or delete any user of tenant B (404 or empty).
