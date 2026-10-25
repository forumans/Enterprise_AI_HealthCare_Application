# F03 — Authentication, Sessions, Role-Based Access and Tenant Isolation

Mandatory for every endpoint, including ones added later.

## 1. Passwords (`SEC-PWD`)

- **SEC-PWD-01 Hash.** `hash_password(p)`: 16 random bytes salt (`os.urandom(16)`),
  `hashlib.pbkdf2_hmac("sha256", p.encode("utf-8"), salt, 120000)`, stored as
  `"pbkdf2$" + salt.hex() + "$" + digest.hex()`.
- **SEC-PWD-02 Verify.** For `pbkdf2$` hashes: split on `$` (max 2 splits), recompute, compare with
  `hmac.compare_digest`; malformed → false. Otherwise try `bcrypt.checkpw` (legacy), any exception → false.
- **SEC-PWD-03** Every new password (self-registration, admin creation, admin reset, email reset, bootstrap) is
  at least 8 characters (server: Pydantic `min_length=8, max_length=255` or an explicit check). Passwords are
  never logged, audited, returned or emailed. `password_hash` is never returned by any endpoint.

## 2. Access tokens (`SEC-AUTHN`)

- **SEC-AUTHN-01** Login: lower-case + trim the email; find the active, non-deleted account through
  `cross_tenant.login_lookup` (F02 §6); verify the password. Unknown email, wrong password, deactivated and
  deleted accounts all return the same **401 "Authentication failed"**.
- **SEC-AUTHN-02 Token.** JWT HS256 signed with `JWT_SECRET`; claims
  `{"user_id": <uuid>, "tenant_id": <uuid>, "role": <ROLE>, "iat": <epoch s>, "exp": iat + ACCESS_TOKEN_MINUTES*60}`
  (default 30 minutes). No PHI in the token. No refresh token (`refresh_token` is returned as `""`).
- **SEC-AUTHN-03 Public paths** (exact match, each also with the `/api` prefix): `/health`, `/api/health`,
  `/api/health/ready`, `/api/health/live`, `/auth/login`, `/auth/register`, `/auth/forgot-password`,
  `/auth/reset-password`, `/doctors/register`, `/admin/register`, `/admin/setup-status`. Any `OPTIONS`
  request (CORS preflight) is also passed through. Everything else requires a token. `/doctors` (list) is
  deliberately **not** public: it needs the caller's tenant.

## 3. Request authentication middleware (`TenantContextMiddleware`)

For every request:

1. Generate `request_id = uuid4()`; store on `request.state.request_id`.
2. If the method is `OPTIONS` or the path is public: call the app and add header `X-Request-ID`.
3. Parse `Authorization`: must be exactly two space-separated parts, first part `bearer` (case-insensitive),
   non-empty token. Otherwise → 401 `{"detail": "Missing or invalid Authorization header."}`.
4. Decode with `JWT_SECRET`/`JWT_ALGORITHM` (signature + `exp`). Any error → 401
   `{"detail": "Invalid or expired access token."}`.
5. Validate claims: `tenant_id` and `user_id` are strings parsing as UUIDs (else 401
   "JWT claim '<name>' is missing or invalid." / "JWT claim '<name>' must be a valid UUID."); `role` is a string
   whose upper-case form is one of `ADMIN, DOCTOR, PATIENT, SUPPORT_STAFF` (else 401
   "JWT claim 'role' is missing or invalid." / "Invalid role '<v>'. Must be one of: [...]"); `iat`, if numeric,
   is not in the future (else 401 "Access token has an invalid issued-at timestamp.").
6. Every failure SHALL be returned as a JSON 401 **from the middleware** (never a 500) with header
   `X-Request-ID`.
7. On success set `request.state.tenant_id / user_id / role` and a `RequestContext(request_id, tenant_id,
   user_id, role)` contextvar; call the app; **reset the contextvar in `finally`**; add `X-Request-ID`.

## 4. Identity dependency and per-request account re-check (`SEC-SESS`)

`get_current_identity(request, db) -> CurrentIdentity(tenant_id, user_id, role, clinic_tz)`:

- Missing state → 401 "Authentication required.".
- Load `users.tenant_id, role, is_active, deleted_at` and `tenants.timezone` for `user_id` (one query, outer join
  to tenants). Return **401 "Your session is no longer valid. Please sign in again."** if the user is missing,
  inactive, soft-deleted, in a different tenant than the token says, or has a different role than the token
  claims. A deactivated, deleted or demoted user is therefore signed out at their next request.
- `clinic_tz = ZoneInfo(tenants.timezone)` (unknown/empty → `CLINIC_TIMEZONE` default) — used by every
  clinic-calendar computation (F05).

`require_roles(*roles)` wraps it and returns **403 "Forbidden for this role."** when the role isn't allowed,
before any data access. Endpoints open to all signed-in roles still depend on `get_current_identity`.

## 5. Client session handling (summary; full UI in [02](../features/02-login-and-session.md))

- **SEC-SESS-04** The session `{accessToken, role, tenantId, clinicTimezone, userName?, insuranceProvider?,
  insurancePolicyId?}` lives only in React state. Never `localStorage`, `sessionStorage` or cookies.
- **SEC-SESS-05** Any 401 on a request that carried a token triggers one forced sign-out (event
  `hc:session-ended`), even when several requests fail together.
- **SEC-SESS-06** Route guards and menu filtering are conveniences; the server is the only enforcement point.

## 6. Permission matrix (`SEC-RBAC`)

P = patient, D = doctor, S = support staff, A = admin. "own" = only records tied to the caller's own profile.
"—" = 403. Every path is also served under `/api`.

| Endpoint | P | D | S | A |
|----------|:-:|:-:|:-:|:-:|
| `POST /appointments` (book) | own | — | ✓ (patient_id) | — |
| `GET /appointments`, `/appointments/all`, `/appointments/week` | own | own | tenant | tenant |
| `POST /appointments/{id}/reschedule` | own | own | ✓ | — |
| `DELETE /appointments/{id}` (cancel) | own | own | ✓ | ✓ |
| `POST /appointments/{id}/confirm` | — | own | — | — |
| `PATCH /appointments/{id}/status` | — | own | — | ✓ |
| `PATCH /appointments/{id}` (reason) | — | — | ✓ | — |
| `GET /doctors`, `GET /doctor/availability/{id}/all` | ✓ | ✓ | ✓ | ✓ |
| `POST /doctor/availability` | — | own | ✓ (doctor_id) | — |
| `DELETE /doctor/availability/{doctor_id}` | — | own | ✓ | — |
| `GET /doctors/me`, `GET /doctor/profile`, `PUT /doctor/profile`, `GET /doctor/appointments*` | — | own | — | — |
| `GET /patient/me`, `GET/PUT /patient/patient/profile`, `POST /patient/documents` | own | — | — | — |
| `GET /patient/prescriptions-full` | own | ✓ (patient_id) | — | — |
| `GET /patients/search` | — | ✓ | — | ✓ |
| `POST /medical-records` | — | own | — | — |
| `GET /medical-records/{appointment_id}` | own | own | — | ✓ |
| `POST /prescriptions` | — | own | — | ✓ |
| `GET /prescriptions/pharmacies`, `GET /prescriptions/{id}` | own | ✓ | — | ✓ |
| `POST /documents?patient_id=`, `GET /documents/{patient_id}` | own | ✓ | — | ✓ |
| `/support/*` | — | — | ✓ | — |
| `/admin/*` (except the public bootstrap pair), `/audit-logs`, `GET /tenants/{id}`, `PATCH /tenants/current` | — | — | — | ✓ |
| `GET /tenants/current` | ✓ | ✓ | ✓ | ✓ |

## 7. Ownership inside a tenant (`SEC-OWN`)

- **SEC-OWN-01** A patient's or doctor's own profile is always resolved from the token's `user_id` + tenant
  (`Patient.user_id == user_id AND tenant_id == token tenant AND deleted_at IS NULL`), never from a
  client-supplied id. A caller with no profile gets `[]` from list endpoints and 404/403 from item endpoints —
  never someone else's data.
- **SEC-OWN-02** "own" patient endpoints verify the appointment / record / prescription / document belongs to the
  caller's patient profile; mismatch → 403 (appointments) or 404 (records, prescriptions, documents — to avoid
  confirming existence).
- **SEC-OWN-03** "own" doctor endpoints verify `appointment.doctor_id == caller's doctor id` for confirm, status
  change, reschedule, cancel, consultation reads, medical record and prescription creation.
- **SEC-OWN-04** Support staff endpoints return contact, scheduling and reason fields only — never symptoms,
  diagnoses, lab results, prescriptions or documents.

## 8. Tenant isolation (`SEC-TEN`)

- **SEC-TEN-01** The tenant id comes only from the verified token (or, on public endpoints, from the server's own
  resolution). No endpoint accepts a tenant id from the body or query to choose whose data to read or write.
- **SEC-TEN-02** Every query on a tenant table filters `tenant_id = <token tenant>`, including primary-key
  lookups, joins (filter each joined tenant table where practical) and existence checks. Another tenant's
  record behaves exactly as if it doesn't exist (404 or empty list).
- **SEC-TEN-03** Every insert sets `tenant_id` from the token (or from a parent row that was itself
  tenant-checked).
- **SEC-TEN-04** Composite FKs prevent cross-tenant links where practical (`appointments(slot_id, tenant_id)` →
  `doctor_availability(id, tenant_id)`).
- **SEC-TEN-05** No tenant-creation endpoint. `GET /tenants/{id}` returns only the caller's own tenant (any other
  id → 404 "Tenant not found.").
- **SEC-TEN-06** Email uniqueness is global for active accounts (`BR-ACC-01`, [20](../features/20-admin-account-management.md)).
- **SEC-TEN-07** Object storage keys start with `documents/<tenant_id>/<patient_id>/`; a key is presigned only
  after the document row passed tenant and ownership checks.
- **SEC-TEN-08 Defense in depth.** PostgreSQL RLS (F02 §6) restricts every tenant table to the transaction's
  tenant. The backend sets the scope in the SQLAlchemy `Session.after_begin` event:
  - authenticated requests: from the `RequestContext` contextvar;
  - public requests: `set_db_tenant(db, tenant_id, user_id=None)` stores an override contextvar **and** runs
    `set_config` immediately, so the current and later transactions of that request use the resolved tenant.
- **SEC-TEN-09** Tests SHALL create two tenants and prove every list, search and lookup endpoint returns nothing
  from the other tenant, both with the code filters and with RLS enforced (connect as a non-owner role).

## 9. Acceptance criteria

- **F03-AC-01** Given no `Authorization` header, When any protected endpoint is called, Then 401
  "Missing or invalid Authorization header." with an `X-Request-ID` header.
- **F03-AC-02** Given an expired, garbled or wrongly signed token, a token with a future `iat`, non-UUID
  `user_id`/`tenant_id`, or role "NURSE", When a protected endpoint is called, Then a JSON 401 (never 500).
- **F03-AC-03** Given a valid token for a user who was then deactivated, soft-deleted, or whose role changed,
  When they call any protected endpoint, Then 401 "Your session is no longer valid. Please sign in again.".
- **F03-AC-04** Given each row of the matrix in §6, When the endpoint is called with each disallowed role, Then
  403 "Forbidden for this role." (or the endpoint's documented 403 message).
- **F03-AC-05** Given tenants A and B, When a user of A requests any id belonging to B, Then 404 / empty list.
- **F03-AC-06** Given RLS enabled and a connection as the app user with no tenant set, When `SELECT count(*) FROM
  users` runs, Then it returns 0.
- **F03-AC-07** Given a correct password, When logging in, Then the token decodes to `user_id`, `tenant_id`,
  `role`, `iat`, `exp = iat + 1800` (default) and contains no other personal data.
- **F03-AC-08** Given wrong password vs unknown email, When logging in, Then both responses are byte-identical
  401 bodies.

## 10. Reference implementation

`backend/app/core/security.py`, `core/dependencies.py`, `core/database.py` (`_scope_transaction`,
`set_db_tenant`), `core/cross_tenant.py`, `middleware/tenant_middleware.py`, `middleware/request_context.py`,
`backend/tests/test_role_access.py`, `tests/integration/test_row_level_security.py`.
