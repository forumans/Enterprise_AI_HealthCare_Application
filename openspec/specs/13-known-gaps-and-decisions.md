# 13 — Known Gaps, Deviations and Decisions

Documents 01–12 describe the intended behavior. This document lists where the current implementation
(`healthcare_saas_app/`, reviewed 2026-10-24) differs from it, so that:

- a team rebuilding from these specs implements the requirement, not the defect; and
- the team maintaining the current code has a prioritized hardening backlog.

Severity: **Critical** = exploitable data exposure or privilege escalation; **High** = security weakness or
wrong data; **Medium** = inconsistency users will hit; **Low** = cleanup.

## 1. Security deviations

| # | Severity | Requirement | Current behavior | Required fix |
|---|----------|-------------|------------------|--------------|
| S1 | Critical | `AUTH-BOOT-03` | `POST /admin/register` is public and always creates an `ADMIN` in the first tenant. Anyone can make themselves an administrator. | Refuse once the tenant has an active admin (403); create the `admins` profile; consider a one-time setup token. |
| S2 | High | `SEC-OWN-02` | `GET /documents/{patient_id}` and `POST /documents` accept any patient id in the tenant for the PATIENT role. | Patients may only use their own patient id (resolve from the token). |
| S3 | High | `SEC-OWN-02/03` | `GET /medical-records/{appointment_id}` checks only the tenant; any patient or doctor in the clinic can read any record by appointment id. | Patient: own appointments only; doctor: own appointments (or the clinic-wide care-team rule in `DOC-SRCH-05`, explicitly). |
| S4 | High | `SEC-OWN-02` | `GET /prescriptions/{id}` checks only the tenant for patients. | Verify the prescription's appointment belongs to the calling patient. |
| S5 | High | `SEC-OWN-03` | `POST /prescriptions` does not check that the doctor owns the medical record, nor that `pharmacy_id` belongs to the tenant. | Check both. |
| S6 | High | `SEC-PHI-01` | The 422 handler logs `exc.errors()`, which includes submitted values (names, emails, passwords). | Log field locations and error types only. |
| S7 | High | `SEC-PHI-03` | Doctor and patient profile GET/PUT endpoints return 500 with `str(exception)`; document upload returns the raw storage error. | Return the generic message; log details server-side. |
| S8 | High | `PAT-PROF-03`, `BR-ACC-01` | `PATCH /patient/profile` lets a patient change their login email with no uniqueness check (can collide with another active account). | Remove email from that endpoint (admins change emails), or apply `BR-ACC-01` and require re-authentication. |
| S9 | High | `SEC-TEN-05` | `POST /tenants` and `GET /tenants/{id}` are open to any clinic admin. | Restrict to a platform super-admin role. |
| S10 | Medium | `SEC-MW` | Middleware is registered so that security headers are innermost (401s from the JWT middleware lack them) and the audit-context middleware runs before the JWT middleware (it never sees tenant/user). | Use the order in `SEC-MW`. |
| S11 | Medium | `BR-SLOT-04` | `POST` and `DELETE /doctor/availability/{doctor_id}` skip the past/30-day window checks enforced by `POST /doctor/availability`. | Apply the same window; or remove the legacy endpoints. |
| S12 | Medium | `SEC-AUTHN-05` | No rate limiting or lockout on login, forgot-password or registration. | Add per-IP and per-account throttling. |
| S13 | Medium | `PAT-DOC-03` | Uploads have no size or type limit (`MAX_UPLOAD_SIZE` is defined but unused); the original filename is kept with only slashes replaced. | Enforce size and MIME allow-list; sanitize filenames more strictly. |
| S14 | Medium | `API-GEN-07`, API §14 | `GET /tenants/debug` and the OpenAPI UI are reachable in production. | Disable outside development. |
| S15 | Medium | `SEC-AUD-01` | No audit entries for slot changes, `PUT /doctor/profile`, `PUT /patient/patient/profile`, or admin bootstrap. | Add them. |
| S16 | Medium | `ADM-DEL-03` | Soft delete has no self-protection or last-admin check. | Apply `BR-ACC-04` to deletes. |
| S17 | Medium | `AUTH-REGD-04` | Self-registered doctors are instantly active and bookable. | Add an approval step or a tenant setting to disable self-registration. |
| S18 | Low | `SEC-TEN-08` | No PostgreSQL row-level security. | Add RLS as defense in depth. |
| S19 | Low | `SEC-AUD-04` | Reads of clinical data are not audited. | Log access events for clinical views. |

## 2. Functional deviations

| # | Severity | Requirement | Current behavior | Required fix |
|---|----------|-------------|------------------|--------------|
| F1 | High | `DOC-CONS-04`, `BR-CLIN-01` | `POST /medical-records` takes only `patient_id` and attaches the record to that patient's **most recent** appointment with the doctor, not the appointment being consulted; it does not require `CONFIRMED`. | Accept `appointment_id`, verify it is the doctor's own `CONFIRMED` appointment, and link the record to it. |
| F2 | High | `VAL-04` | Registration screens and APIs accept passwords of 5+ characters, but the login screen requires 8+. A user who registered with 5–7 characters cannot sign in through the UI. The legacy `POST /users` requires 12. | Minimum 8 everywhere (UI and API). |
| F3 | High | `ADM-DASH-03` | Dashboard "Total Doctors/Patients" are counted from the first page (25) of `GET /admin/users`. Clinics with more users see wrong totals. | Use server-side counts. |
| F4 | Medium | `AUTH-BOOT` | The Admin Login link "First time setup? Register admin" points to `/admin/register-admin`, which is admin-only, so guests are redirected to Home. | Provide a public bootstrap page shown only when the tenant has no admin, or remove the link. |
| F5 | Medium | `DOC-TODAY-04` | The Consultation link is only styled as disabled for non-confirmed appointments; it still navigates. | Disable navigation and enforce on the server (F1). |
| F6 | Medium | `PAT-BOOK-05` | Patient booking/cancel failures show a generic message, hiding the server's reason (for example the 409 slot-taken message). | Show the server `detail`. |
| F7 | Medium | `ADM-DEACT-03` | The Deactivate screen says a signed-in user "stays signed in until their session expires", but the server now ends the session on the next request (`SEC-SESS-03`). | Update the note. |
| F8 | Medium | `DATA-SEED-01` | Self-registration (patients, doctors, bootstrap admin) always joins the first tenant in the database; there is no way to choose a clinic. | Resolve the tenant from the hostname/subdomain (`tenants.domain`) or an invitation code. |
| F9 | Low | API §8 | `GET /patient/prescriptions` returns placeholder "Debug …" values. | Remove it (the UI uses `/patient/prescriptions-full`). |
| F10 | Low | `NFR-PERF-03` | `/appointments/all`, `/appointments/week` and `/admin/users` run one query per row for names. | Join in one query. |
| F11 | Low | ADM §9 | `GET /admin/appointments` includes cancelled (soft-deleted) appointments and returns ids, not names. | Filter or label cancelled rows; return names. |
| F12 | Low | `AUTH-BOOT-02` | Admins created through `/admin/register` have no `admins` profile, so lists fall back to the email as the name. | Create the profile. |
| F13 | Low | API §13 | Two parallel user-management APIs exist (`/users*` and `/admin/users*`) with different rules (`/users` allows only three roles). | Keep `/admin/users*`; retire `/users*`. |

## 3. Not yet implemented (deferred scope)

| Item | Notes |
|------|-------|
| Billing | Menu item and placeholder page only. |
| Multi-time-zone clinics | One `CLINIC_TIMEZONE` per deployment; grids render in the browser's zone. Supporting a clinic in any zone needs a per-tenant (or per-doctor) zone column, slot generation and boundaries per tenant, and grids rendered in clinic time with the viewer's offset shown. |
| Patient documents UI | API exists; no upload/list screen. |
| Soft delete / restore UI | API only. |
| Tenant onboarding and platform super-admin | Not built (see S9, F8). |
| Refresh tokens / remember me | Field accepted and ignored. |
| Appointment reminders and notifications | Only the password-reset email exists. |
| CI/CD pipelines | Deploys run from operator scripts (`NFR-DEP-09`). |
| Structured JSON logs, alarms, dashboards | Plain-text logs only (`NFR-OBS-01/04`). |
| Medical news feed | Static cards on the home page. |

## 4. Design decisions (keep unless deliberately revisited)

| Decision | Rationale |
|----------|-----------|
| Token in memory only; reload signs out | Avoids XSS token theft from storage; acceptable for a clinic workstation app. |
| Per-request account re-check (one indexed query) | Makes deactivation, deletion and role changes take effect immediately without a token blacklist. |
| Global email uniqueness for active accounts | Login is not tenant-qualified; one email must resolve to one account. |
| Cancel = soft delete + `CANCELLED` | Keeps history and audit while freeing the slot; partial unique indexes ignore cancelled rows. |
| Hourly slots, 8 AM–11 PM, 7 days a week | Matches the clinic's extended hours; generation is lazy (on read) and never overwrites edited days. |
| Rolling 7-day generation, 5-week booking horizon, 30-day change window | Bounded data growth; doctors open further days by adding slots. |
| Doctors may view clinic-wide patient history | Care-team model chosen for small clinics; tenants can tighten it (`DOC-SRCH-05`). |
| Support staff never see clinical data | Least privilege for non-clinical staff. |
| SQL migrations instead of an ORM migration tool | Explicit, reviewable DDL that also runs inside the VPC from a temporary Lambda. |
| Lambda with one DB connection per environment | Prevents connection exhaustion under burst concurrency. |
