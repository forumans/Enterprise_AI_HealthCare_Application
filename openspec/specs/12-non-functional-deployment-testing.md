# 12 — Non-Functional Requirements, Deployment and Testing

## 1. Quality targets (`NFR`)

| ID | Area | Requirement |
|----|------|-------------|
| NFR-PERF-01 | Latency | p95 API latency under 500 ms on a warm Lambda for list and search calls with up to 10,000 patients per tenant |
| NFR-PERF-02 | Cold start | First request after idle completes within 5 s (512 MB Lambda) |
| NFR-PERF-03 | Queries | List endpoints SHALL avoid N+1 queries (join doctor names instead of one lookup per row); searches use indexed, capped queries |
| NFR-SCALE-01 | Concurrency | One DB connection per Lambda environment; RDS `max_connections` and Lambda reserved concurrency sized together |
| NFR-REL-01 | Correctness under races | Booking, rescheduling and admin (de)activation SHALL lock the rows they depend on and rely on unique indexes as the final guard; concurrent attempts produce one success and clean 409s |
| NFR-REL-02 | Idempotent setup | Default slot generation and migrations are safe to run repeatedly and concurrently |
| NFR-AVAIL-01 | Health | `/api/health` reports database connectivity and returns 503 when the database is unreachable |
| NFR-MAINT-01 | Pinned dependencies | Exact versions in `requirements.txt` and a lockfile for npm; upgrades only after the full test suite passes |
| NFR-MAINT-02 | Shared constants | Office hours, slot length and search rules defined once per tier and mirrored deliberately (`BR-TIME-05`) |
| NFR-USAB-01 | Browser support | Current Chrome, Edge, Firefox, Safari; desktop first, usable at 360 px wide |
| NFR-I18N-01 | Locale | English (US) text and formats; clinics in any IANA time zone; times shown and rules applied in the clinic's zone |
| NFR-PRIV-01 | Data minimization | Each endpoint returns only the fields its screen needs (support staff never receive clinical fields) |

## 2. Configuration (environment variables)

| Variable | Required | Default | Purpose |
|----------|:-:|---------|---------|
| `APP_ENV` | yes | | `dev`, `test`, `production`; `test` also loads `.env.test` |
| `DATABASE_URL` | yes | | `postgresql+asyncpg://user:pass@host:5432/db` (secret) |
| `JWT_SECRET` | yes | | ≥32 random bytes (secret) |
| `JWT_ALGORITHM` | yes | `HS256` | |
| `ACCESS_TOKEN_MINUTES` | yes | `30` | session length |
| `CORS_ORIGINS` | yes | | comma-separated allowed origins |
| `DB_SCHEMA_INIT_ON_STARTUP` | no | `false` | `true` only for local development |
| `CLINIC_TIMEZONE` | no | `America/New_York` | Zone given to a clinic created without one (each clinic's zone is `tenants.timezone`) |
| `S3_BUCKET_NAME` | for documents | | private documents bucket |
| `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS` (true), `SMTP_FROM` | for reset email | | email is skipped (with a warning) when host or from is empty |
| `FRONTEND_URL` | no | first CORS origin | base of reset links |
| `PASSWORD_RESET_MINUTES` | no | `30` | reset link lifetime |
| `MAX_UPLOAD_SIZE` | no | `10485760` | upload limit in bytes |
| `HOST`, `PORT` | local only | `0.0.0.0`, `8000` | Uvicorn |
| Frontend `VITE_API_BASE_URL` | yes at build time | `http://127.0.0.1:8000` | baked into the bundle; set to the CloudFront origin + `/api` for production |
| Frontend `VITE_ENABLE_DEBUG_LOGS` | no | `false` | console debug logs outside dev |

- **NFR-CFG-01** The backend SHALL fail fast at startup when a required variable is missing, naming the variable
  (never its value).

## 3. Deployment architecture (AWS)

- **NFR-DEP-01 Backend.** AWS SAM template defines: a Lambda function (python3.12, 512 MB, 30 s timeout,
  handler `app.main.handler`, VPC private subnets + security group), an IAM role with basic execution, VPC
  access and S3 `PutObject`/`GetObject` on the documents bucket, and an HTTP API with a catch-all route. No CORS
  at the gateway. Secrets are `NoEcho` parameters, never written to `samconfig.toml`.
- **NFR-DEP-02 Database.** RDS PostgreSQL in private subnets, not publicly accessible, encryption at rest,
  automated backups. The Lambda security group is the only inbound source on 5432.
- **NFR-DEP-03 Frontend.** `npm run build` output synced to a private S3 bucket served by CloudFront (origin
  access control). Behaviors: `/*` → S3; `/api/*` → API Gateway with the `AllViewerExceptHostHeader` origin
  request policy and caching disabled (without it API Gateway returns 403 and CloudFront serves `index.html`
  for API calls). 403/404 from S3 → `/index.html` with 200 for client-side routes. HTTPS redirect.
- **NFR-DEP-04 Order of operations.** Apply migrations → deploy backend → (if the API URL changed) update the
  CloudFront `/api/*` origin → build the frontend with the right `VITE_API_BASE_URL` → sync to S3 → invalidate
  CloudFront → smoke-test `/api/health` and a login.
- **NFR-DEP-05 Migrations in the VPC.** Because RDS is private, migrations run from a temporary in-VPC Lambda as
  the master user, which is deleted afterwards; the master password is entered at a hidden prompt and never
  stored. A read-only preflight reports enum values, tables and app-user privileges. A schema snapshot can be
  diffed against the local database to confirm both match.
- **NFR-DEP-06 Updates in place.** An update script reuses the live function's secrets without printing them,
  refuses to run on an unhealthy stack, verifies the API URL is unchanged, and smoke-tests at the end. Backend
  and frontend can be deployed independently.
- **NFR-DEP-07 Cost control.** Teardown script: snapshot RDS, record subnet group/security groups/instance class
  (git-ignored), check for forgotten NAT gateways or Elastic IPs, then (after typed confirmation) delete the
  stack and the instance. Redeploy script restores from the snapshot and repeats `NFR-DEP-04`. Idle cost when
  torn down is snapshot and bucket storage only.
- **NFR-DEP-08 Human approval.** Deployments to AWS and production migrations are run by an operator after local
  testing; automation SHALL NOT deploy on its own.
- **NFR-DEP-09 CI (target).** Separate backend and frontend pipelines: lint, type-check, unit tests, build; the
  backend pipeline applies migrations before `sam deploy`; secrets come from the CI secret store; every deploy is
  traceable to a commit SHA. (Planned; see doc 01 §2.2.)

## 4. Observability

- **NFR-OBS-01** Logs go to stdout (CloudWatch Logs), format `timestamp | level | logger | message`, INFO by
  default. Target: structured JSON with request id, method, path, status, duration, tenant id and user id (ids
  only, `SEC-PHI-01`).
- **NFR-OBS-02** Every response to an authenticated path carries `X-Request-ID`; logs for that request include
  it.
- **NFR-OBS-03** Log group retention 30 days (configurable).
- **NFR-OBS-04** Alarms (target): Lambda error rate > 1% over 5 minutes, p95 duration, throttles, RDS CPU,
  connections and free storage, 5xx at CloudFront/API Gateway — notifying an SNS topic.
- **NFR-OBS-05** Startup logs whether schema initialization ran and fails loudly if the timestamp migration is
  missing (`DATA-GEN-03`).

## 5. Test plan (`TEST`)

### 5.1 Layers

| Layer | Tooling | Runs | Scope |
|-------|---------|------|-------|
| Backend unit | Python `unittest` (`python -m unittest discover -s backend/tests -t .` from `healthcare_saas_app/`) | always | role guards per route, search helper, request validation, time utilities (DST), middleware wiring, token handling, health endpoints, login |
| Backend integration | `unittest` against a disposable PostgreSQL; RLS tests and the HTTP suite connect as a non-superuser, non-owner role so policies are enforced; (`HC_TEST_PG_ADMIN_URL`); each test creates and drops its own `hc_it_<random>` database from the baseline schema plus migrations | when the variable is set | migrations (data preserved, reruns, rollback), slot generation incl. DST and concurrency, booking/cancel/rebook via trigger, double-booking, reschedule rules, support staff flows, admin account flows, permissions, and an end-to-end HTTP suite that starts the real app with Uvicorn |
| Frontend unit | Vitest + Testing Library + user-event (`npm run test`) | always | pages and components with the API mocked: login, session-ended sign-out, header, password reset pages, admin pages, support appointments (search, scroll, booking, close-and-scroll-back), reschedule modal, slot state helpers, search validation |
| End-to-end | Playwright | against running servers | critical journeys in a real browser |

- **TEST-ENV-01** Integration tests SHALL refuse to run against anything but a disposable server; never point them
  at a database holding real data.
- **TEST-ENV-02** Project dependencies install only into a virtual environment (`.venv`), never the shared system
  interpreter.

### 5.2 Mandatory test cases

- **TEST-SEC-01** For every protected endpoint: no token → 401; each disallowed role → 403.
- **TEST-SEC-02** Expired, garbled, wrong-signature, future-`iat`, non-UUID-claim and unknown-role tokens → 401
  JSON (not 500).
- **TEST-SEC-03** A deactivated, deleted or role-changed user's existing token → 401 on the next request.
- **TEST-SEC-04** Two-tenant isolation for every list, search and lookup endpoint (`SEC-TEN-09`).
- **TEST-SEC-05** Ownership: patient/doctor cannot act on another patient's/doctor's appointment, record,
  prescription or document.
- **TEST-SEC-06** Login: wrong password and unknown email return the identical 401 body.
- **TEST-SEC-07** Forgot password: identical reply for known and unknown emails; reset token single-use, expiry,
  wrong purpose, and access token used as reset token all rejected.
- **TEST-SEC-08** Validation errors do not echo submitted values; 500s carry CORS headers and the generic message.
- **TEST-BR-01** Every acceptance criterion in docs 05–08 (`*-AC-*`).
- **TEST-BR-02** Booking race: two concurrent bookings of one slot → exactly one 201 and one 409.
- **TEST-BR-03** DST: default slots and clinic-day/week boundaries on spring-forward and fall-back days.
- **TEST-BR-05** Time zones: clinics in different zones (including half-hour offsets) get office hours, days and
  weeks in their own zone; a zone change keeps local slot hours (`BR-TIME-06`); frontend tests run with a
  browser zone (`Asia/Tokyo`) unlike any clinic's, so a grid or time that follows the viewer's zone fails.
- **TEST-BR-04** Search: 1-character term rejected, `*` returns all, phone formatting ignored, email match
  case-insensitive, 50-result cap.
- **TEST-UI-01** Token never written to `localStorage`/`sessionStorage`.
- **TEST-UI-02** Route guards redirect wrong roles to `/`; menus show only the role's items.

### 5.3 Definition of done for any change

1. Backend and frontend test suites pass locally; type check (`tsc --noEmit`) is clean.
2. New behavior has tests at the right layer; security-relevant changes have negative tests.
3. Needed migrations are added, idempotent, and listed in the deployment notes.
4. The matching requirement in these documents is updated in the same change.
