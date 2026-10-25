# 01 — Product Overview

## 1. Purpose

A web-based clinic management platform, sold as multi-tenant SaaS. Each customer clinic (tenant) uses it to:

- let patients register, book, reschedule and cancel appointments with the clinic's doctors;
- let doctors manage their weekly schedule and hourly availability, confirm appointments, run consultations,
  and record symptoms, diagnoses, lab results and prescriptions;
- let support staff (front desk, call center) do the same appointment and availability work on behalf of
  patients and doctors;
- let administrators register users, manage accounts (password, login email, activation, soft delete) and
  watch clinic-wide appointment metrics.

Every record belongs to exactly one tenant. Users only ever see their own tenant's data.

## 2. Scope

### 2.1 In scope

| Area | Capabilities |
|------|--------------|
| Identity | Login per role, patient self-registration, doctor self-registration, admin-created accounts for all roles, email-based password reset, admin password/email reset, deactivate/activate, soft delete/restore |
| Scheduling | Hourly slots from 8 AM to the 11 PM slot, clinic time; automatic generation of a rolling 7-day window; block, unblock, add and delete slots; booking up to 5 weeks ahead |
| Appointments | Book, confirm, reschedule, cancel, edit reason (support staff), complete (through consultation) |
| Clinical | Consultation form: symptoms, diagnosis, lab results, prescription (medication, dosage, instructions, pharmacy) |
| Records | Patients see their completed visits with diagnoses and prescriptions; doctors search patients and view their history |
| Documents | Patient document upload to private object storage; download through short-lived signed URLs |
| Administration | Dashboard (counts and appointment metrics), user registration, account management, audit log query |
| Security | JWT sessions, RBAC on every endpoint, tenant isolation, audit trail, security headers, PHI-safe logging |

### 2.2 Out of scope (deferred)

- Billing (a placeholder menu item and page exist; no functionality).
- Clinics spanning several time zones (one clinic time zone per deployment today; see doc 13).
- Self-service tenant sign-up and tenant administration UI.
- Refresh tokens and "remember me" (the field exists and is ignored).
- Notifications other than the password-reset email (no appointment reminders).
- Real-time updates (pages refresh after each action).

## 3. Roles (personas)

| Role code | Name | Who | How the account is created | Landing page after login |
|-----------|------|-----|----------------------------|--------------------------|
| `GUEST` | Visitor | Anyone not signed in | n/a | n/a |
| `PATIENT` | Patient | A person receiving care | Self-registration, or by an admin | `/patients/appointments` |
| `DOCTOR` | Doctor | A licensed provider | Self-registration, or by an admin | `/doctors/appointments` |
| `SUPPORT_STAFF` | Support staff | Front desk or call center | By an admin only | `/support/patient-appointments` |
| `ADMIN` | Administrator | Clinic operations or IT | First admin through the bootstrap endpoint; others by an admin | `/admin/system-dashboard` |

Each user account has exactly one role. One email address maps to at most one active account across all
tenants (see `BR-ACC-01`).

### 3.1 Capability summary by role

| Capability | Patient | Doctor | Support staff | Admin |
|------------|:-:|:-:|:-:|:-:|
| Book appointment | own | — | for any patient | — |
| Reschedule appointment | own | own | any | — |
| Cancel appointment | own | own | any | any |
| Confirm appointment | — | own | — | — |
| Edit appointment reason | — | — | any | — |
| Complete appointment / consultation | — | own | — | status change only |
| Manage availability (block/unblock/add) | — | own | any doctor | — |
| View own medical history and prescriptions | yes | — | — | — |
| Search patients and view clinical history | — | yes | contact details only | — |
| Update own profile | yes | yes | yes | — |
| Register users | — | — | — | all roles |
| Reset password / change login email of others | — | — | — | yes |
| Deactivate / activate / soft delete / restore accounts | — | — | — | yes |
| Dashboard and audit log | — | — | — | yes |

"own" means the appointment, slot or record belongs to the caller's own patient or doctor profile.

## 4. Glossary

| Term | Meaning |
|------|---------|
| Tenant / clinic | An isolated customer organization. Every business row carries `tenant_id`. |
| User | A login account (`users` row): email, password hash, role, active flag. |
| Profile | The role-specific row linked 1:1 to a user: `patients`, `doctors`, `support_staff` or `admins`. |
| Slot | One hour of a doctor's time (`doctor_availability` row) with status `AVAILABLE`, `BOOKED` or `BLOCKED`. |
| Appointment | A patient booked into a doctor's slot. Status: `SCHEDULED`, `CONFIRMED`, `COMPLETED` or `CANCELLED`. |
| Reason / notes | The patient's free-text reason for the visit, stored in `appointments.notes`. |
| Medical record | Symptoms, diagnosis and lab results for one appointment (1:1). |
| Prescription | Medication details for one medical record (1:1), optionally routed to a pharmacy. |
| Clinic time | Wall-clock time in the tenant's IANA time zone (`CLINIC_TIMEZONE`, default `America/New_York`). |
| Soft delete | Setting `deleted_at` / `deleted_by` instead of removing the row. Soft-deleted rows are hidden everywhere. |
| Deactivate | Setting `users.is_active = false`. The person cannot sign in; their data stays visible to staff. |
| PHI | Protected health information: names, contact details, dates of birth, clinical data, documents. |
| Wildcard search | Searching for exactly `*` lists every match with no result cap. |

## 5. Technology stack (reference implementation)

An equivalent stack is acceptable if it meets every requirement. The reference stack:

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI (async), Pydantic v2 |
| ORM / DB driver | SQLAlchemy 2.x async, asyncpg |
| Database | PostgreSQL 15+ (AWS RDS in production), `uuid-ossp` extension |
| Auth | PyJWT (HS256), PBKDF2-HMAC-SHA256 password hashing |
| Object storage | AWS S3, private bucket, presigned GET URLs |
| Email | SMTP (STARTTLS), plain text |
| Runtime | AWS Lambda (Mangum ASGI adapter) behind API Gateway HTTP API; Uvicorn locally |
| Frontend | React 18, TypeScript, Vite, React Router, TanStack Query (home page news only) |
| Frontend hosting | S3 static site behind CloudFront; CloudFront proxies `/api/*` to API Gateway |
| IaC | AWS SAM (`backend/template.yaml`) plus PowerShell deploy/teardown scripts |
| Tests | Python `unittest` (backend), Vitest and Testing Library (frontend), Playwright (end-to-end) |

Dependency versions are pinned exactly (`backend/requirements.txt`) so local, test and cloud environments run
identical code.

## 6. Architecture

```
Browser (React SPA)
   │  HTTPS
   ▼
CloudFront ──── /*      ──► S3 bucket (static SPA assets; 403/404 → /index.html)
   │
   └──────────── /api/* ──► API Gateway HTTP API ──► Lambda (FastAPI + Mangum)
                                                       ├─► RDS PostgreSQL (private subnets)
                                                       ├─► S3 documents bucket (private)
                                                       └─► SMTP server (password reset email)
```

- **GEN-ARCH-01** All business endpoints SHALL be served both under `/api/...` and unprefixed (`/...`), so
  the same backend works behind CloudFront's `/api/*` behavior and when called directly.
- **GEN-ARCH-02** The backend SHALL be stateless. All state lives in PostgreSQL, S3 and the client-held JWT.
- **GEN-ARCH-03** Each Lambda execution environment SHALL hold at most one database connection
  (`pool_size=1`, `max_overflow=0`, `pool_pre_ping=true`).
- **GEN-ARCH-04** CORS SHALL be handled only by the application (not API Gateway), to avoid duplicate headers.
- **GEN-ARCH-05** The frontend SHALL keep the access token in memory only (React context), never in
  `localStorage`, `sessionStorage` or cookies. Reloading the page signs the user out.

### 6.1 Backend layering

```
app/
  main.py            app factory, middleware order, exception handlers, routers, Lambda handler
  core/              config, database engine, security (hashing, JWT, reset tokens),
                     dependencies (identity, require_roles), timeutils, storage (S3)
  middleware/        security headers, tenant/JWT context, audit context, request contextvars
  models/            ORM models (one per table)
  services/          account lifecycle, appointment booking/rescheduling, default slots, audit, email
  api/routes/        one router per area (auth, admin, doctor, patient, appointments, support, …)
  api/search_utils.py  shared people-search matching
migrations/          versioned, idempotent SQL files (no ORM migration tool)
tests/               unit tests + PostgreSQL integration tests
```

### 6.2 Frontend layering

```
src/
  App.tsx            route table; every protected route wrapped in ProtectedRoute + AppLayout
  api.ts             typed API client; one function per endpoint; session-ended detection
  contexts/AuthContext.tsx   session state, login/logout, redirect after login, forced sign-out
  config/menu.ts     top menus and role-filtered submenus
  app/               role checks, breadcrumbs
  components/common/ shared widgets: search panels, slot picker, reschedule modal, labeled fields
  components/layout/ header and page layout
  components/pages/  one component per screen
  hooks/             data loading hooks
  utils/             validation, date/slot helpers, error parsing
```
