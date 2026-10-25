# F01 — Architecture, Technology Stack and Project Layout

## 1. Product in one paragraph

A web-based clinic management platform sold as multi-tenant SaaS. Each customer clinic (tenant) uses it so
that patients can register and book, reschedule and cancel hourly appointments with the clinic's doctors;
doctors can manage their availability, confirm appointments, run consultations and record diagnoses and
prescriptions; support staff (front desk, call center) can do appointment and availability work on behalf of
patients and doctors; and administrators can register users, manage accounts, set the clinic's time zone and
watch appointment metrics. Every business record belongs to exactly one tenant and users only ever see their
own tenant's data.

## 2. Roles

| Code | Name | How the account is created | Landing page after login |
|------|------|----------------------------|--------------------------|
| `GUEST` | Visitor (not signed in) | n/a | n/a |
| `PATIENT` | Patient | Self-registration ([04](../features/04-patient-self-registration.md)) or by an admin ([19](../features/19-admin-user-registration.md)) | `/patients/appointments` |
| `DOCTOR` | Doctor | Self-registration, inactive until an admin activates it ([05](../features/05-doctor-self-registration.md)), or by an admin (active immediately) | `/doctors/appointments` |
| `SUPPORT_STAFF` | Support staff | By an admin only | `/support/patient-appointments` |
| `ADMIN` | Administrator | The very first one through the public setup ([06](../features/06-first-admin-setup.md)); others by an admin | `/admin/system-dashboard` |

Each user account has exactly one role and exactly one role profile row (`patients`, `doctors`,
`support_staff` or `admins`).

### 2.1 Capability matrix

| Capability | P | D | S | A |
|------------|:-:|:-:|:-:|:-:|
| Book an appointment | own | — | for any patient | — |
| Reschedule | own | own | any | — |
| Cancel | own | own | any | any |
| Confirm | — | own | — | — |
| Edit appointment reason | — | — | any | — |
| Consultation / complete | — | own | — | status change only |
| Manage slots (add / block / unblock / delete) | — | own | any doctor | — |
| View own completed visits and prescriptions | yes | — | — | — |
| Search patients with clinical history | — | yes | — | API only |
| Search patients / doctors (contact details) | — | — | yes | — |
| Update own profile | yes | yes | yes | — |
| Register users, manage accounts, clinic time zone, dashboard, audit log | — | — | — | yes |

## 3. Reference technology stack

An equivalent stack is acceptable if it meets every requirement. Versions are those the reference
implementation pins.

| Layer | Technology |
|-------|-----------|
| Backend language / framework | Python 3.12, FastAPI 0.162 (async), Pydantic 2.14, Starlette 1.10 |
| ORM / driver | SQLAlchemy 2.1 (asyncio), asyncpg 0.32 |
| Database | PostgreSQL 15+ (RDS in production), extension `uuid-ossp` |
| Auth | PyJWT 2.15 (HS256); PBKDF2-HMAC-SHA256 password hashing (stdlib); bcrypt 5.0 only to verify legacy hashes |
| Object storage | AWS S3 (boto3 1.43), private bucket, presigned GET URLs |
| Email | SMTP with STARTTLS (stdlib `smtplib`), plain text |
| Runtime | AWS Lambda (python3.12, 512 MB, 30 s) via Mangum 0.22 behind API Gateway HTTP API; Uvicorn locally |
| Time zones | `zoneinfo` + `tzdata` (pinned) |
| Frontend | React 18.3, TypeScript 5.5, Vite 7, React Router 7, TanStack Query 5 (home page only) |
| Frontend hosting | Private S3 bucket behind CloudFront; CloudFront proxies `/api/*` to API Gateway |
| IaC | AWS SAM (`backend/template.yaml`) + PowerShell operator scripts |
| Tests | Python `unittest` (unit + PostgreSQL integration), Vitest + Testing Library, Playwright |

- **GEN-STACK-01** Backend dependencies SHALL be pinned to exact versions (including transitive ones) in
  `backend/requirements.txt`; the frontend SHALL use a lockfile. Upgrades happen only after the full test suite
  passes.

## 4. Runtime architecture

```
Browser (React SPA, token in memory)
   │ HTTPS
   ▼
CloudFront ── /*      ──► S3 bucket (static SPA; 403/404 → /index.html, 200)
   │
   └───────── /api/* ──► API Gateway HTTP API (catch-all route, no CORS) ──► Lambda: FastAPI + Mangum
                                                                              ├─► RDS PostgreSQL (private subnets)
                                                                              ├─► S3 documents bucket (private)
                                                                              └─► SMTP server (reset emails)
```

- **GEN-ARCH-01 Dual mounting.** All business routers SHALL be served both under `/api/...` and unprefixed
  (`/...`), so the backend works behind CloudFront's `/api/*` behavior and when called directly.
  Health routes are served under `/api` only (§7).
- **GEN-ARCH-02** The backend SHALL be stateless: state lives in PostgreSQL, S3 and the client-held JWT. The
  only in-process state is the rate-limit counters ([F04](F04-audit-privacy-errors-security.md)).
- **GEN-ARCH-03** Each Lambda execution environment SHALL hold at most one DB connection: `pool_size=1`,
  `max_overflow=0`, `pool_pre_ping=True`, `hide_parameters=True`.
- **GEN-ARCH-04** CORS SHALL be handled only by the application, never by API Gateway (duplicate headers break
  browsers).
- **GEN-ARCH-05** The SPA SHALL keep the access token in memory only (React context). Reloading the page or
  opening a new tab starts as a guest.
- **GEN-ARCH-06** OpenAPI docs (`/docs`, `/redoc`, `/openapi.json`) SHALL be disabled when `APP_ENV` is
  `production` or `prod`.

## 5. Backend layout

```
backend/
  app/
    main.py              app factory create_app(): logging, validation handler, middleware stack,
                         startup checks, routers (/api and unprefixed), Mangum `handler`
    core/
      config.py          Settings (frozen dataclass) read from env (.env, .env.test when APP_ENV=test)
      database.py        async engine/session, per-transaction tenant scope (set_config), set_db_tenant()
      dependencies.py    CurrentIdentity, get_current_identity (per-request account re-check), require_roles
      security.py        hash/verify password, access token, password-reset token
      cross_tenant.py    the 4 cross-tenant lookups (SECURITY DEFINER functions, plain-query fallback)
      rate_limit.py      in-memory sliding-window limits for public auth endpoints
      timeutils.py       clinic-zone helpers, office hours, default slot times
      storage.py         S3 upload/presign, upload validation
      aws_secrets.py     optional Secrets Manager loader (not required by the spec)
    middleware/
      tenant_middleware.py           JWT validation → request.state + contextvar
      audit_context_middleware.py    request metadata for audit
      security_headers_middleware.py
      request_context.py             RequestContext contextvar (set / reset in finally)
    models/              one SQLAlchemy model per table (see F02)
    services/
      account_service.py      email availability, delete guards, restore
      appointment_service.py  book (row lock) and reschedule
      availability_service.py default slot generation, keep-local-hours on zone change
      tenant_service.py       registration tenant resolution, set clinic time zone
      audit_service.py        write_audit_log, write_access_log
      email_service.py        send_email (never raises)
    api/
      routes/            auth, tenants, patient, patients, documents, doctor, appointments,
                         medical_records, prescriptions, support, admin, admin_password_reset, audit_logs
      health.py          /health, /health/ready, /health/live (mounted under /api)
      search_utils.py    shared people-search matching (F15)
      deps.py            re-exports of dependencies
  migrations/            NNN_description.sql (idempotent), plus *_rollback.sql where possible
  tests/                 unit tests; tests/integration = disposable-PostgreSQL tests
  template.yaml          SAM template;  requirements.txt  pinned deps
```

### 5.1 Router registration order

`auth`, `tenants`, `patient` (prefix `/patient`), `patients` (prefix `/patients`), `documents` (prefix
`/documents`), `doctor` (no prefix), `appointments`, `medical_records`, `prescriptions` (prefix `/prescriptions`),
`support` (prefix `/support`), `admin` (prefix `/admin`), `admin_password_reset` (prefix `/admin`),
`audit_logs`. Route order matters where paths overlap: `/doctor/appointments/today`, `/all` and `/upcoming`
SHALL be declared before `/doctor/appointments/{appointment_id}`; `/prescriptions/pharmacies` before
`/prescriptions/{id}`; `/admin/users/search` before any `/admin/users/{id}` path.

### 5.2 Application factory (`create_app`)

1. Configure logging: `basicConfig(level=INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")`;
   add a filter on `uvicorn.access` that replaces the client address with `-` and strips the query string.
2. Create `FastAPI(title="Healthcare SaaS API", version="1.0.0")`, docs disabled in production.
3. Register a `RequestValidationError` handler returning 422
   `{"detail": "Invalid request format. Please check your input and try again."}` and logging only
   `field.path: error_type` pairs (never values).
4. Add middleware in this code order (last added = outermost): `AuditContextMiddleware`,
   `TenantContextMiddleware(excluded_paths=…)`, `SecurityHeadersMiddleware`, the unhandled-error catcher,
   `CORSMiddleware(allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`.
   Resulting order outermost→innermost: CORS → error catcher → security headers → tenant/JWT → audit context →
   routes ([F03](F03-auth-rbac-tenancy.md), [F04](F04-audit-privacy-errors-security.md)).
5. On startup: if `DB_SCHEMA_INIT_ON_STARTUP` is true run `Base.metadata.create_all` (local dev only); then
   query `information_schema.columns` for any `public` column of type `timestamp without time zone` and refuse
   to start (`RuntimeError` naming the columns and migration 003) if any exist. If the database is unreachable,
   log a warning and continue (the health endpoint reports it).
6. Include `api_router` with prefix `/api`, then again unprefixed; include the health router with prefix `/api`.
7. Expose `handler = Mangum(app, lifespan="off")` for Lambda.

## 6. Frontend layout

```
frontend/src/
  main.tsx               React root: StrictMode > QueryClientProvider > BrowserRouter > App
  App.tsx                route table; AppHeader + <Routes>; HomePage and BillingPage inline
  api.ts                 request() wrapper + one typed function per endpoint; SESSION_ENDED_EVENT
  contexts/AuthContext.tsx        session state, login/logout, forced sign-out, ClinicTimeZoneContext provider
  contexts/ClinicTimeZoneContext.ts  useClinicTimeZone()
  config/menu.ts         submenuMap, getMainMenuFromPath
  app/routeBreadcrumbs.ts  breadcrumb labels; app/access.ts requireRole
  hooks/                 useAppointments, useUserData (tenant info, admin dashboard), useNavigation, useMedicalNewsAgent
  components/layout/     AppHeader, AppLayout
  components/common/     LabeledField, StatusMessage, ProtectedRoute, ClinicTimeNote, SupportSearchPanel,
                         AdminUserSearch, SlotPickerCalendar, RescheduleAppointmentModal
  components/pages/      one component per screen
  utils/index.ts         validation, clinic-time helpers, slot keys, search rule, upcoming rule
  constants/index.ts     COUNTRIES, DEFAULT_COUNTRY="USA", durations
  styles.css             design tokens and component classes (F06)
```

- **GEN-FE-01** `api.ts` SHALL be the only module that calls `fetch`. Base URL = `VITE_API_BASE_URL` (default
  `http://127.0.0.1:8000`), set at build time to `<CloudFront origin>/api` for production.
- **GEN-FE-02 `request()` contract:** sends `Content-Type: application/json` merged with caller headers; on a
  non-2xx response reads the body, and if the request carried an `Authorization` header and the status is 401,
  dispatches `window` event `hc:session-ended`; then throws `Error(detail)` when the body is JSON with `detail`,
  else `Error(body text or "HTTP <status>: <statusText>")`. 204 returns `undefined`. A network `TypeError`
  becomes `Error("Failed to fetch - please check your internet connection and ensure the server is running")`.
  Debug logging only when `import.meta.env.DEV` or `VITE_ENABLE_DEBUG_LOGS === "true"`, logging the path without
  query string and never bodies.
- **GEN-FE-03** `parseErrorMessage(error)` returns the `Error.message` (unwrapping a JSON string's `detail`), or
  "An error occurred".

## 7. Health endpoints (public)

| Method & path | Response |
|---------------|----------|
| GET `/api/health` | 200 `{"status":"healthy","service":"healthcare-backend","database":"connected","version":"1.0.0"}` after `SELECT 1`; on DB error 503 `{"status":"unhealthy","service":"healthcare-backend","database":"disconnected","error":"Database connection failed"}`; on any other error 503 with `"database":"unknown","error":"Service unavailable"` |
| GET `/api/health/ready` | 200 `{"status":"ready","checks":{"database":true,"api":true},"service":"healthcare-backend"}` or 503 with `"status":"not_ready"` and `database:false` |
| GET `/api/health/live` | 200 `{"status":"alive","service":"healthcare-backend","timestamp":"<UTC ISO>"}` |

Health failures log only the exception type. `/health` (unprefixed) is listed as a public path in the
middleware but is not routed (see [GAPS](../GAPS.md) GAP-01).

## 8. Key design decisions (keep unless deliberately revisited)

| Decision | Rationale |
|----------|-----------|
| Token in memory only; reload signs out | Nothing in browser storage for XSS to steal |
| Account re-checked on every request | Deactivation, deletion and role changes take effect immediately, no blacklist |
| Tenant isolation in every query **and** PostgreSQL RLS | A forgotten filter still can't leak another clinic's data |
| Email unique across clinics for active accounts | Login is not tenant-qualified |
| Self-registration clinic chosen by web address (`tenants.domain`) | Patients join the clinic whose site they used |
| Cancel = soft delete + `CANCELLED` | History kept; partial unique indexes ignore cancelled rows |
| Hourly slots 8 AM–11 PM, 7 days, generated lazily for 7 days | Bounded data; never overwrites a day the doctor edited |
| 5-week booking horizon, 30-day change window | Bounded scheduling surface |
| Doctors can view clinic-wide patient history (audited) | Care-team model for small clinics |
| Support staff never see clinical data | Least privilege |
| Self-registered doctors start deactivated | An admin vouches for every doctor |
| Versioned SQL migrations, no ORM migration tool | Reviewable DDL that runs from a temporary in-VPC Lambda |
| One DB connection per Lambda environment | Prevents RDS connection exhaustion |
