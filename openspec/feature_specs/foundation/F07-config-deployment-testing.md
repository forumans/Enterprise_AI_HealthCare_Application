# F07 — Configuration, Deployment, Observability, Quality Targets and Testing

## 1. Configuration (environment variables)

Settings are read once into a frozen `Settings` dataclass. Load order: `.env` (no override), then `.env.test`
(override) when `APP_ENV=test`.

| Variable | Required | Default | Purpose |
|----------|:-:|---------|---------|
| `APP_ENV` | yes | | `dev`, `test`, `staging`, `production`; `production`/`prod` disables OpenAPI docs |
| `DATABASE_URL` | yes | | `postgresql+asyncpg://user:pass@host:5432/db` (secret) |
| `JWT_SECRET` | yes | | ≥ 32 random bytes (secret) |
| `JWT_ALGORITHM` | yes | `HS256` | |
| `ACCESS_TOKEN_MINUTES` | yes | `30` | session length |
| `CORS_ORIGINS` | yes | | comma-separated allowed origins |
| `DB_SCHEMA_INIT_ON_STARTUP` | no | `false` | `true` only for local dev (`create_all`); truthy = 1/true/yes/on |
| `CLINIC_TIMEZONE` | no | `America/New_York` | zone for a clinic created without one; fallback zone |
| `S3_BUCKET_NAME` | for documents | `""` | private documents bucket |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_TLS` / `SMTP_FROM` | for reset email | `""` / `587` / `""` / `""` / `true` / `SMTP_USER` | email is skipped (warning logged) when host or from is empty |
| `FRONTEND_URL` | no | first `CORS_ORIGINS` entry, trailing `/` stripped | base of reset links |
| `PASSWORD_RESET_MINUTES` | no | `30` | reset link lifetime |
| `MAX_UPLOAD_SIZE` | no | `10485760` | upload limit (bytes) |
| `HOST`, `PORT` | local only | `0.0.0.0`, `8000` | Uvicorn |
| `VITE_API_BASE_URL` (frontend, build time) | yes | `http://127.0.0.1:8000` | baked into the bundle; production = `<CloudFront origin>/api` |
| `VITE_ENABLE_DEBUG_LOGS` (frontend) | no | `false` | console debug logs outside dev |

- **NFR-CFG-01** The backend SHALL fail fast at startup when a required variable is missing, naming the variable
  but never its value.

## 2. AWS deployment architecture

- **NFR-DEP-01 Backend (SAM).** Globals: `python3.12`, timeout 30 s, memory 512 MB, env vars `APP_ENV`,
  `DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM=HS256`, `ACCESS_TOKEN_MINUTES=30`, `CORS_ORIGINS`,
  `DB_SCHEMA_INIT_ON_STARTUP=false`, `S3_BUCKET_NAME`; VPC config (private subnets + Lambda security group).
  Parameters: `AppEnv` (production|staging|dev), `DatabaseUrl` (NoEcho), `JwtSecret` (NoEcho), `CorsOrigins`,
  `DocumentsBucketName`, `LambdaSecurityGroupId`, `PrivateSubnetIds` (comma list). Resources: IAM role with
  `AWSLambdaVPCAccessExecutionRole` + inline `s3:PutObject`/`s3:GetObject` on `arn:aws:s3:::<bucket>/documents/*`;
  function `<stack>-backend`, handler `app.main.handler`; HTTP API `<stack>-http-api` stage `$default` with
  `ANY /{proxy+}` and `ANY /`. Outputs `ApiUrl`, `BackendFunctionArn`, `BackendFunctionName`. No CORS at the
  gateway. Secrets never written to `samconfig.toml`.
- **NFR-DEP-02 Database.** RDS PostgreSQL in private subnets, not publicly accessible, encryption at rest,
  automated backups; the Lambda security group is the only inbound source on 5432. App user `healthcare_user`
  with DML only.
- **NFR-DEP-03 Frontend.** `npm run build` output synced to a private S3 bucket behind CloudFront (origin access
  control). Behaviors: `/*` → S3; `/api/*` → API Gateway origin with the `AllViewerExceptHostHeader` origin
  request policy and caching disabled (otherwise API Gateway answers 403 and CloudFront serves `index.html` for
  API calls). Custom errors: S3 403/404 → `/index.html` with 200. Viewer protocol redirect-to-HTTPS.
- **NFR-DEP-04 Order of operations.** Apply migrations → deploy backend → (if the API URL changed) update the
  CloudFront `/api/*` origin → build the frontend with the right `VITE_API_BASE_URL` → sync to S3 → invalidate
  CloudFront → smoke-test `/api/health` and one login.
- **NFR-DEP-05 Migrations in the VPC.** RDS is private, so migrations run from a temporary in-VPC Lambda as the
  master user, deleted afterwards; the master password is typed at a hidden prompt and never stored. A read-only
  preflight reports enum values, tables and app-user privileges; a schema snapshot can be diffed with the local
  database (`compare_schema.py`).
- **NFR-DEP-06 Updates in place.** The update script reuses the live function's secrets without printing them,
  refuses to run on an unhealthy stack, verifies the API URL is unchanged, and smoke-tests at the end. Backend
  and frontend deploy independently.
- **NFR-DEP-07 Cost control.** Teardown: snapshot RDS, record subnet group / security groups / instance class
  (git-ignored metadata), check for forgotten NAT gateways or Elastic IPs, then — after typed confirmation —
  delete the stack and instance. Redeploy restores from the snapshot and repeats NFR-DEP-04.
- **NFR-DEP-08 Human approval.** Deployments and production migrations are run by an operator after local
  testing; automation SHALL NOT deploy on its own.
- **NFR-DEP-09 Public repository hygiene.** Account ids, subnet/SG ids, bucket names and endpoints live in
  `aws_env_spin_up/scripts/aws-config.local.json` (git-ignored) with a committed `aws-config.example.json`.

## 3. Observability

- **NFR-OBS-01** Logs to stdout (CloudWatch), `timestamp | level | logger | message`, INFO. Target: structured JSON
  with request id, method, path, status, duration, tenant id, user id (ids only).
- **NFR-OBS-02** Responses to authenticated paths carry `X-Request-ID`.
- **NFR-OBS-03** Log retention 30 days (configurable).
- **NFR-OBS-04 (target)** Alarms: Lambda error rate > 1% / 5 min, p95 duration, throttles, RDS CPU / connections /
  free storage, 5xx at CloudFront/API Gateway → SNS.
- **NFR-OBS-05** Startup logs whether schema init ran and fails loudly if migration 003 is missing.

## 4. Quality targets

| ID | Requirement |
|----|-------------|
| NFR-PERF-01 | p95 latency < 500 ms (warm) for list and search calls with up to 10,000 patients per tenant |
| NFR-PERF-02 | Cold start completes first request within 5 s (512 MB) |
| NFR-PERF-03 | No N+1 queries: list endpoints join names in one query; searches are indexed and capped |
| NFR-SCALE-01 | One DB connection per Lambda environment; RDS `max_connections` sized with reserved concurrency |
| NFR-REL-01 | Booking, rescheduling and admin (de)activation lock the rows they depend on; unique indexes are the final guard; concurrent attempts give one success and clean 409s |
| NFR-REL-02 | Default slot generation and migrations are safe to run repeatedly and concurrently |
| NFR-AVAIL-01 | `/api/health` reports DB connectivity and returns 503 when unreachable |
| NFR-USAB-01 | Current Chrome, Edge, Firefox, Safari; desktop first, usable at 360 px |
| NFR-I18N-01 | English (US) text and formats; any IANA clinic zone |
| NFR-PRIV-01 | Each endpoint returns only the fields its screen needs |

## 5. Test strategy

| Layer | Tooling | Runs | Scope |
|-------|---------|------|-------|
| Backend unit | `python -m unittest discover -s backend/tests -t .` (from `healthcare_saas_app/`, inside `.venv`) | always | role guards per route, search helper, validation, time utilities (DST), middleware wiring, token handling, health, login, route registration |
| Backend integration | `unittest` against a disposable PostgreSQL given by `HC_TEST_PG_ADMIN_URL`; each test creates and drops `hc_it_<random>` from the baseline + migrations; RLS and HTTP suites connect as a non-owner role | when the variable is set | migrations (data preserved, reruns, rollback), slot generation incl. DST and concurrency, booking/cancel/rebook via trigger, double booking, reschedule rules, support flows, admin flows, permissions, clinic time zones, an end-to-end HTTP suite with real Uvicorn |
| Frontend unit | Vitest + Testing Library + user-event (`npm run test`), browser zone `Asia/Tokyo` | always | pages and components with the API mocked |
| End-to-end | Playwright (`test_healthcare_saas_app/`) | against running servers | critical journeys in a browser |

- **TEST-ENV-01** Integration tests refuse to run against anything but a disposable server.
- **TEST-ENV-02** Project dependencies install only into a virtual environment, never the shared system Python.

### 5.1 Mandatory test cases

- **TEST-SEC-01** Every protected endpoint: no token → 401; each disallowed role → 403.
- **TEST-SEC-02** Expired, garbled, wrong-signature, future-`iat`, non-UUID-claim and unknown-role tokens → JSON 401.
- **TEST-SEC-03** Deactivated, deleted or role-changed user's existing token → 401.
- **TEST-SEC-04** Two-tenant isolation for every list, search and lookup endpoint.
- **TEST-SEC-05** Ownership: patients/doctors can't act on others' appointments, records, prescriptions, documents.
- **TEST-SEC-06** Login: wrong password and unknown email give identical 401 bodies.
- **TEST-SEC-07** Forgot password: identical replies; reset token single-use, expiry, wrong purpose, and an access
  token used as a reset token are all rejected.
- **TEST-SEC-08** Validation errors don't echo values; 500s carry CORS headers and the generic message.
- **TEST-BR-01** Every acceptance criterion in the feature files.
- **TEST-BR-02** Booking race: two concurrent bookings of one slot → exactly one 201 and one 409.
- **TEST-BR-03** DST: default slots and day/week boundaries on spring-forward and fall-back days.
- **TEST-BR-04** Search: 1-character term rejected, `*` returns all, phone formatting ignored, email
  case-insensitive, 50-result cap.
- **TEST-BR-05** Clinics in different zones (including half-hour offsets) get their own office hours, days and
  weeks; a zone change keeps local slot hours.
- **TEST-UI-01** Token never written to `localStorage`/`sessionStorage`.
- **TEST-UI-02** Route guards redirect wrong roles to `/`; menus show only the role's items.

### 5.2 Definition of done for any change

1. Backend and frontend suites pass locally; `tsc --noEmit` and `npm run build` are clean.
2. New behavior has tests at the right layer; security-relevant changes have negative tests.
3. Needed migrations are added, idempotent, and listed in the deployment notes.
4. The matching feature spec is updated in the same change.
