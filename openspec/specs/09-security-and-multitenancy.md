# 09 — Security and Multi-Tenancy

The platform stores PHI for several independent clinics in one database and one deployment. These controls
keep each clinic's data isolated, limit each role to what it needs, and keep an audit trail. They are
mandatory for every endpoint, including ones added later.

## 1. Threat model summary

| Threat | Primary controls |
|--------|------------------|
| A user reads or changes another clinic's data | Tenant id taken only from the signed token; every query filters by it (`SEC-TEN`) |
| A user acts outside their role | Server-side role check on every endpoint (`SEC-RBAC`) |
| A user acts on someone else's records in the same clinic | Ownership checks (`SEC-OWN`) |
| Stolen or stale session | Short-lived signed tokens, per-request account re-check, in-memory storage (`SEC-SESS`) |
| Credential guessing or account discovery | Uniform login and forgot-password replies, PBKDF2 hashing (`SEC-AUTHN`, `SEC-PWD`) |
| PHI leaking through logs, errors or caches | Generic errors, no PHI in logs, `no-store` caching (`SEC-PHI`) |
| Tampering without trace | Application and database audit trails (`SEC-AUD`) |
| Browser attacks | Security headers, strict CORS, no token in storage (`SEC-WEB`) |
| Secrets exposure | Secrets only in environment/deploy parameters; public-repo hygiene (`SEC-SECRETS`) |

## 2. Authentication (`SEC-AUTHN`)

- **SEC-AUTHN-01** Login SHALL accept email + password, look up the user by lower-cased email among
  non-deleted, active accounts, and compare the password in constant time.
- **SEC-AUTHN-02** Every failure (unknown email, wrong password, deactivated, deleted) SHALL return the same
  401 "Authentication failed" with no timing shortcuts that reveal which.
- **SEC-AUTHN-03** On success, issue a JWT (HS256) with claims `user_id` (UUID), `tenant_id` (UUID), `role`,
  `iat`, `exp` (now + `ACCESS_TOKEN_MINUTES`, default 30). No PHI in the token.
- **SEC-AUTHN-04** Public (unauthenticated) endpoints are exactly: health checks (`/health`, `/api/health`,
  `/api/health/ready`, `/api/health/live`), `/auth/login`, `/auth/register`, `/auth/forgot-password`,
  `/auth/reset-password`, `/doctors/register`, `/admin/register` — each with and without the `/api` prefix.
  Matching is by exact path. CORS preflight (`OPTIONS`) is always allowed. Everything else requires a token.
- **SEC-AUTHN-05** Login, password reset and self-registration SHALL be rate-limited per email and per client
  address (`AUTH-RATE`). Failed attempts SHALL NOT be logged with the email.

## 3. Passwords and reset tokens (`SEC-PWD`)

- **SEC-PWD-01** Passwords SHALL be hashed with PBKDF2-HMAC-SHA256, 120,000 iterations, a fresh 16-byte random
  salt, stored as `pbkdf2$<salt hex>$<digest hex>`. Verification uses `hmac.compare_digest`. Legacy bcrypt
  hashes MAY be verified for backward compatibility.
- **SEC-PWD-02** Minimum length 8 for every new password (registration, admin creation, admin reset, email
  reset). Passwords are never logged, audited, returned or emailed.
- **SEC-PWD-03** Reset tokens SHALL be signed with a key derived from the JWT secret but distinct from it
  (`HMAC-SHA256(JWT_SECRET, "password-reset")`), so a reset token can never be used as an access token and
  vice versa. Claims: `sub` (user id), `purpose = "password_reset"`, `pwh`, `iat`, `exp` (now +
  `PASSWORD_RESET_MINUTES`, default 30).
- **SEC-PWD-04 Single use.** `pwh` is the first 24 hex characters of SHA-256 of the current password hash. The
  token is accepted only while the account still has that hash, so it stops working as soon as the password
  changes (including after its own use).
- **SEC-PWD-05** Forgot-password replies SHALL be identical for known and unknown emails (`AUTH-FP-02`).

## 4. Sessions (`SEC-SESS`)

- **SEC-SESS-01** The middleware SHALL require `Authorization: Bearer <token>`, verify signature and expiry,
  validate that `tenant_id` and `user_id` are UUIDs and `role` is one of the four roles, and reject tokens
  whose `iat` is in the future. Every failure returns a JSON 401 (never a 500) with header `X-Request-ID`.
- **SEC-SESS-02** Missing or malformed header → 401 "Missing or invalid Authorization header."; bad or expired
  token → 401 "Invalid or expired access token.".
- **SEC-SESS-03 Per-request account re-check.** For every authenticated request the server SHALL load the user
  and return 401 "Your session is no longer valid. Please sign in again." if the user no longer exists, is
  deactivated or soft-deleted, has moved tenant, or has a different role than the token claims. A deactivated
  or demoted user is therefore signed out on their next request, not when the token expires.
- **SEC-SESS-04** The client SHALL keep the token in memory only (`GEN-ARCH-05`) and react to any 401 on an
  authenticated request with a single forced sign-out (`AUTH-SESS-03`).
- **SEC-SESS-05** Identity (tenant, user, role, request id) SHALL be stored per request (request state and
  `contextvars`) and reset in a `finally` block so it never leaks between concurrent requests.

## 5. Role-based access control (`SEC-RBAC`)

- **SEC-RBAC-01** Every protected endpoint SHALL declare its allowed roles with a single dependency
  (`require_roles(...)`) that returns 403 "Forbidden for this role." before any data access. Endpoints open to
  all signed-in roles still require a valid identity.
- **SEC-RBAC-02** The frontend hides menus and guards routes by role, but the server is the only enforcement
  point. Tests SHALL call endpoints directly with each wrong role.

### 5.1 Permission matrix

P = patient, D = doctor, S = support staff, A = admin. "own" = only records tied to the caller's profile.

| Endpoint group | P | D | S | A |
|----------------|:-:|:-:|:-:|:-:|
| `POST /appointments` (book) | own | — | ✓ (patient_id) | — |
| `GET /appointments`, `/appointments/all`, `/appointments/week` | own | own | tenant | tenant |
| `POST /appointments/{id}/reschedule` | own | own | ✓ | — |
| `DELETE /appointments/{id}` (cancel) | own | own | ✓ | ✓ |
| `POST /appointments/{id}/confirm` | — | own | — | — |
| `PATCH /appointments/{id}/status` | — | own | — | ✓ |
| `PATCH /appointments/{id}` (reason) | — | — | ✓ | — |
| `GET /doctors`, `GET /availability/{id}`, `GET /doctor/availability/{id}/all\|ndays` | ✓ | ✓ | ✓ | ✓ |
| `POST /doctor/availability` | — | own | ✓ (doctor_id) | — |
| `POST\|DELETE /doctor/availability/{doctor_id}` | — | own | ✓ | — |
| `GET /doctors/me`, `/doctor/profile`, `/doctor/appointments*` | — | own | — | — |
| `PUT /doctor/profile` | — | own | — | — |
| `GET /patient/me`, `/patient/appointments/upcoming`, `/patient/medical-history`, `PATCH /patient/profile`, `/patient/patient/profile` | own | — | — | — |
| `GET /patient/prescriptions-full` | own | ✓ (patient_id) | — | — |
| `POST /patient/documents` | own | — | — | — |
| `GET /patients` | — | ✓ | ✓ | ✓ |
| `GET /patients/search` | — | ✓ | — | ✓ |
| `GET /patients/{id}/prescriptions` | — | ✓ | — | — |
| `POST /medical-records` | — | own | — | — |
| `GET /medical-records/{appointment_id}` | own | own | — | ✓ |
| `POST /prescriptions` | — | own | — | ✓ |
| `GET /prescriptions/pharmacies`, `GET /prescriptions/{id}` | own | ✓ | — | ✓ |
| `POST /documents`, `GET /documents/{patient_id}` | own | ✓ | — | ✓ |
| `/support/*` | — | — | ✓ | — |
| `/admin/*`, `/users*`, `/audit-logs`, `POST /patients`, `POST /doctors`, `POST /tenants`, `GET /tenants/{id}` | — | — | — | ✓ |
| `GET /tenants/current` | ✓ | ✓ | ✓ | ✓ |

## 6. Ownership within a tenant (`SEC-OWN`)

- **SEC-OWN-01** A patient's or doctor's own profile SHALL be resolved from the token's `user_id` (+ tenant),
  never from a client-supplied id.
- **SEC-OWN-02** Endpoints marked "own" for patients SHALL verify the record belongs to the caller's patient
  profile: appointments, medical records (`GET /medical-records/{appointment_id}`), prescriptions
  (`GET /prescriptions/{id}`) and documents (`GET /documents/{patient_id}`, `POST /documents`). A mismatch
  returns 403 (or 404 to avoid confirming existence).
- **SEC-OWN-03** Endpoints marked "own" for doctors SHALL verify the appointment's `doctor_id` equals the
  caller's doctor profile (confirm, status, reschedule, cancel, consultation, medical record creation, and
  prescription creation for that record).
- **SEC-OWN-04** Support staff never receive clinical data: their endpoints return contact, scheduling and
  reason fields only.

## 7. Tenant isolation (`SEC-TEN`)

- **SEC-TEN-01** The tenant id SHALL come only from the verified token. No endpoint accepts a tenant id from the
  request body or query to choose whose data to read or write.
- **SEC-TEN-02** Every query on a tenant-owned table SHALL filter by `tenant_id = <token tenant>`, including
  lookups by primary key, joins (filter each joined tenant table) and existence checks. Records of another
  tenant SHALL behave exactly as if they did not exist (404 or empty list).
- **SEC-TEN-03** Every insert SHALL set `tenant_id` from the token (or from the parent record that was itself
  tenant-checked).
- **SEC-TEN-04** Composite foreign keys SHALL prevent cross-tenant links where practical (appointments →
  slots use (`slot_id`, `tenant_id`)).
- **SEC-TEN-05** Creating tenants is a platform-operator task (SQL or seed script); the API has no
  tenant-creation endpoint. `GET /tenants/{id}` returns only the caller's own tenant (any other id → 404).
- **SEC-TEN-06** Email uniqueness is global for active accounts (`BR-ACC-01`) because login is not
  tenant-qualified.
- **SEC-TEN-07** Object storage keys SHALL start with `documents/<tenant_id>/<patient_id>/`, and a document's
  key SHALL only be presigned after the document row passed the tenant (and ownership) check.
- **SEC-TEN-08** Defense in depth: PostgreSQL row-level security SHALL restrict every tenant table to the
  tenant set for the transaction (`DATA-RLS`), so a missing filter in code still cannot leak data. Cross-tenant
  reads happen only through the four `SECURITY DEFINER` lookups in `DATA-RLS-03`.
- **SEC-TEN-09** Automated tests SHALL create two tenants and prove that every list and lookup endpoint returns
  nothing from the other tenant.

## 8. Audit (`SEC-AUD`)

- **SEC-AUD-01** Every create, update, delete, cancel, status change, reschedule, slot change, account change
  (create, email, password, activation, delete, restore), profile change and password-reset request SHALL write
  an `audit_logs` row in the same transaction: tenant, table, record id, action (`INSERT`/`UPDATE`/`DELETE`),
  changed fields old/new, acting user.
- **SEC-AUD-02** Audit data SHALL NOT contain passwords, hashes or tokens.
- **SEC-AUD-03** Database triggers (`DATA-TRG-02`) provide a second, full-row trail.
- **SEC-AUD-04** Reads of clinical data by staff (doctor patient search and history views) SHOULD be recorded
  as access events for HIPAA-style accounting of disclosures.
- **SEC-AUD-05** Audit rows are append-only and visible only to admins of the same tenant.

## 9. PHI and error hygiene (`SEC-PHI`)

- **SEC-PHI-01** Logs SHALL NOT contain names, emails, phone numbers, dates of birth, clinical text, tokens,
  passwords or request bodies. Log ids (request id, user id, record id) instead.
- **SEC-PHI-02** Validation errors SHALL return the generic 422 message without echoing input (`VAL-GEN-01`).
- **SEC-PHI-03** Unhandled exceptions SHALL return JSON 500 "Something went wrong on the server. Please try
  again, or contact support if it keeps happening." with CORS headers (so browsers show the message), and log
  the stack trace server-side. Error responses SHALL NOT include exception text, SQL or stack traces.
- **SEC-PHI-04** API responses SHALL NOT include `password_hash` or other credentials.
- **SEC-PHI-05** The frontend SHALL NOT log credentials, tokens or PHI to the browser console in production
  builds (debug logging only when `import.meta.env.DEV` or `VITE_ENABLE_DEBUG_LOGS=true`).
- **SEC-PHI-06** Email bodies SHALL contain only what is needed (the reset link), not PHI.
- **SEC-PHI-07** The database engine SHALL hide bound parameter values in errors and tracebacks
  (`hide_parameters=True`). Email failures log only the exception type (SMTP errors can embed the recipient).
- **SEC-PHI-08** Local access logs SHALL drop query strings (search terms carry names, emails and phone numbers)
  and client addresses. Frontend debug logs SHALL log request paths without query strings and never response
  bodies.

## 10. Web and transport security (`SEC-WEB`)

- **SEC-WEB-01** Every response SHALL carry:
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`,
  `Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()`, `Cache-Control: no-store`,
  `Strict-Transport-Security: max-age=31536000; includeSubDomains`, and `X-Request-ID` (authenticated paths).
- **SEC-WEB-02** CORS SHALL allow only the origins listed in `CORS_ORIGINS` (comma-separated), with credentials,
  all methods and headers. CORS is configured only in the application.
- **SEC-WEB-03** All traffic SHALL use HTTPS (CloudFront viewer protocol "redirect to HTTPS"). The database and
  Lambda run in private subnets; the database is not publicly reachable.
- **SEC-WEB-04** External links opened by the app SHALL use `rel="noopener noreferrer"`.
- **SEC-WEB-05** The SPA SHOULD ship a Content-Security-Policy restricting scripts to its own origin.

## 11. Middleware order (`SEC-MW`)

Outermost to innermost (intended order):

1. CORS
2. Unhandled-error catcher (JSON 500 that still passes back through CORS)
3. Security headers — outside the JWT middleware so 401 responses carry them too
4. Tenant/JWT context (`SEC-SESS-01`)
5. Audit context — inside the JWT middleware so it sees the tenant and user it sets
6. Router → endpoint dependencies (`get_current_identity` re-check, `require_roles`)

With Starlette's `add_middleware`, the last middleware added is the outermost, so add them in reverse of this
list.

## 12. Secrets and configuration (`SEC-SECRETS`)

- **SEC-SECRETS-01** Secrets (`DATABASE_URL`, `JWT_SECRET`, `SMTP_PASSWORD`) SHALL come from environment
  variables / deployment parameters (SAM parameters with `NoEcho`), never from committed files.
- **SEC-SECRETS-02** `JWT_SECRET` SHALL be at least 32 random bytes and differ per environment.
- **SEC-SECRETS-03** The repository is public: account ids, subnet ids, security group ids, bucket names and
  endpoints SHALL live in a git-ignored local config (`aws-config.local.json`), with a committed
  `*.example.json` template.
- **SEC-SECRETS-04** The documents bucket SHALL block all public access, use server-side encryption, and be
  reachable only by the Lambda role (`s3:PutObject`, `s3:GetObject` on `documents/*`). Download URLs expire after
  1 hour.
- **SEC-SECRETS-05** The application database user SHALL hold only DML privileges (`DATA-MIG-02`).

## 13. Compliance posture

The controls above support HIPAA-style safeguards (access control, audit controls, integrity, transmission
security). A production launch additionally needs: a signed BAA with the cloud provider, encryption at rest for
RDS and S3 (enable), backup and retention policy, breach-notification procedure, workforce access reviews, and
periodic penetration testing.
