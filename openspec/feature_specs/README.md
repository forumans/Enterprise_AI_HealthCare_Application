# Feature Specifications — Multi-Tenant Healthcare SaaS

These documents describe the clinic management platform in `healthcare_saas_app/` **one feature at a time**,
with enough detail that a code-generation agent (Claude Code, Codex or similar) or a human team can build a
functionally equivalent application from scratch: screens, exact on-screen text, validations, business rules,
REST API contracts, database schema, security controls, audit trail, deployment and tests.

They were reverse-engineered from the code as of commit `bc3b34c` (2026-10-25). They replace the earlier
role-oriented documents that lived in `openspec/specs/` (01–12, removed after this set was written; see git
history). Requirement IDs from those documents (`BR-SLOT-05`, `DOC-AVAIL-03`, `VAL-09`, …) are kept, so older
references still resolve here. **These files are the source of truth for the application's requirements.**

## How to build the application from these specs

Build in this order. Each step only depends on the ones before it.

| Step | Read | Produces |
|------|------|----------|
| 1 | [F01 Architecture, stack and project layout](foundation/F01-architecture-stack-and-layout.md) | Repository skeleton, backend app factory, frontend shell, health endpoints |
| 2 | [F02 Database schema](foundation/F02-database-schema.md) | Every table, enum, constraint, index, trigger, RLS policy and migration |
| 3 | [F03 Authentication, sessions, RBAC and tenant isolation](foundation/F03-auth-rbac-tenancy.md) | JWT, middleware, identity re-check, `require_roles`, tenant scoping, cross-tenant lookups |
| 4 | [F04 Audit, privacy, errors and web security](foundation/F04-audit-privacy-errors-security.md) | Audit service and query API, PHI-safe logging, error contract, headers, CORS, rate limits |
| 5 | [F05 Clinic time and calendar](foundation/F05-clinic-time-and-calendar.md) | Time-zone helpers on both tiers, office hours, DST rules |
| 6 | [F06 UI shell, design system and shared components](foundation/F06-ui-shell-and-shared-components.md) | Header, menus, routing, breadcrumbs, tokens, form widgets, search panels, slot picker, reschedule dialog |
| 7 | [F07 Configuration, deployment and testing](foundation/F07-config-deployment-testing.md) | Environment variables, AWS layout, deploy order, test strategy |
| 8 | Feature files below, in numeric order | One vertical slice each (UI + API + data + rules + tests) |

## Feature index

| # | Feature | Roles | Main routes / endpoints |
|---|---------|-------|-------------------------|
| 01 | [Home page](features/01-home-page.md) | everyone | `/` |
| 02 | [Login, sign-out and session](features/02-login-and-session.md) | all | `/patients/login` … `POST /auth/login` |
| 03 | [Forgot / reset password](features/03-password-reset.md) | guest | `/forgot-password`, `/reset-password` |
| 04 | [Patient self-registration and clinic resolution](features/04-patient-self-registration.md) | guest | `/patients/register`, `POST /auth/register` |
| 05 | [Doctor self-registration and approval](features/05-doctor-self-registration.md) | guest, admin | `/doctors/register`, `POST /doctors/register` |
| 06 | [First administrator setup](features/06-first-admin-setup.md) | guest | `/admin/setup`, `POST /admin/register` |
| 07 | [Appointment lifecycle (core domain and API)](features/07-appointment-lifecycle.md) | P, D, S, A | `/appointments*` |
| 08 | [Doctor availability and slots](features/08-doctor-availability.md) | D, S | `/doctors/manage-availability`, `/support/doctor-availability`, `/doctor/availability*` |
| 09 | [Patient: Schedule / Cancel Appointment](features/09-patient-schedule-appointments.md) | P | `/patients/appointments` |
| 10 | [Doctor: Weekly Appointments](features/10-doctor-weekly-appointments.md) | D | `/doctors/appointments` |
| 11 | [Doctor: Today's Appointments](features/11-doctor-today-appointments.md) | D | `/doctors/today-appointments` |
| 12 | [Consultation and clinical records](features/12-consultation-clinical-records.md) | D | `/doctors/consultation/:id`, `/medical-records`, `/prescriptions` |
| 13 | [Patient: Prescriptions and medical history](features/13-patient-prescriptions.md) | P | `/patients/prescriptions` |
| 14 | [Doctor: Search Patients and clinical history](features/14-doctor-search-patients.md) | D | `/doctors/search-patients`, `/patients/search` |
| 15 | [People search (shared rules)](features/15-people-search.md) | S, A, D | `/support/patients`, `/support/doctors`, `/admin/users/search` |
| 16 | [Support staff: Patient and Doctor Appointments](features/16-support-appointments.md) | S | `/support/patient-appointments`, `/support/doctor-appointments` |
| 17 | [Profiles (patient, doctor, support staff)](features/17-profiles.md) | P, D, S | `/patients/profile`, `/doctors/profile`, `/support/profile` |
| 18 | [Admin: System Dashboard and reports](features/18-admin-dashboard.md) | A | `/admin/system-dashboard` |
| 19 | [Admin: Register users](features/19-admin-user-registration.md) | A | `/admin/register-*`, `POST /admin/users` |
| 20 | [Admin: Account management](features/20-admin-account-management.md) | A | `/admin/reset-password`, `/admin/deactivate`, soft delete / restore |
| 21 | [Clinic settings and tenants](features/21-clinic-settings-and-tenants.md) | A, all | `/admin/clinic-settings`, `/tenants*` |
| 22 | [Patient documents](features/22-patient-documents.md) | P, D, A | `/documents*`, `/patient/documents` |
| 23 | [Billing placeholder and other stubs](features/23-placeholders.md) | P | `/patients/billing` |

Cross-cutting reference: [GAPS.md](GAPS.md) lists every place where the current code differs from these
specifications, with the intended behavior and a recommended fix.

## Conventions

- **SHALL / MUST** is mandatory. **SHOULD** is recommended. **MAY** is optional.
- Roles are written `P` (patient), `D` (doctor), `S` (support staff), `A` (admin), `G` (guest, not signed in).
- **Exact strings** appear in double quotes and SHALL be reproduced verbatim (tests match them).
- Every feature file has the same sections: Purpose, Roles and entry points, UI, Business rules, API, Data,
  Security and audit, Edge cases, Acceptance criteria, Reference implementation.
- **Acceptance criteria** are written Given / When / Then. Each one is meant to become an automated test.
- "Clinic" and "tenant" mean the same thing. "Clinic time" means the tenant's IANA zone (`tenants.timezone`).
- All instants are stored and exchanged in UTC with an offset (`2026-10-23T14:00:00+00:00`).
- API paths are written without the `/api` prefix; every business path is served both with and without it
  (`F01`).
- Where these specs and the current code disagree, **the spec states the intended behavior** and the
  difference is recorded in [GAPS.md](GAPS.md) (IDs `GAP-NN`). Rebuilding from the specs therefore yields the
  application as intended, not its known defects.

## Scope

**In scope:** everything that runs in `healthcare_saas_app/` today: four roles plus guest, scheduling in each
clinic's time zone, appointment lifecycle, consultations and prescriptions, admin account management, clinic
time zone, audit, row-level security, AWS deployment.

**Out of scope (not built yet):** billing, tenant onboarding UI (clinics are created by SQL), screens for patient
documents and for soft delete / restore (APIs exist), notifications other than the password-reset email,
refresh tokens, real-time updates, CI/CD pipelines.

**Pending changes:** `openspec/changes/range-slot-blocking/` proposes range block/unblock of slots. It is not
part of this baseline; when it is implemented, update [08](features/08-doctor-availability.md),
[07](features/07-appointment-lifecycle.md), [16](features/16-support-appointments.md) and [F02](foundation/F02-database-schema.md).

## Keeping these specs current

When the application changes, update the matching feature file in the same change, add or close the matching
`GAP-NN`, and keep the requirement IDs stable.

OpenSpec changes (`openspec/changes/`) update these files in their tasks. Archiving a change with the OpenSpec
CLI also writes its delta specs to `openspec/specs/<capability>/spec.md`; those are a by-product of the CLI, and
the feature files here stay authoritative.
