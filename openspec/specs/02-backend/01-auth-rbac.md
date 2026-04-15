## ADDED Requirements

### Requirement: JWT HS256 token structure
The system SHALL issue stateless JWT tokens signed with HS256 using the `JWT_SECRET` environment variable. Each token SHALL contain claims: `user_id` (UUID string), `tenant_id` (UUID string), `role` (one of `ADMIN`, `DOCTOR`, `PATIENT`), `iat` (issued-at), and `exp` (expiry). The default TTL SHALL be 30 minutes, configurable via `ACCESS_TOKEN_MINUTES`.

#### Scenario: Successful login token issuance
- **GIVEN** a valid user with correct credentials
- **WHEN** `POST /auth/login` is called with the correct email and password
- **THEN** the system SHALL return a JWT containing `user_id`, `tenant_id`, `role`, `iat`, and `exp` claims, signed with HS256

#### Scenario: Expired token rejected
- **GIVEN** a JWT whose `exp` timestamp is in the past
- **WHEN** a request is made to any protected endpoint with this token
- **THEN** the system SHALL return `401 Unauthorized` and SHALL NOT process the request

---

### Requirement: PBKDF2 password hashing
The system SHALL hash passwords using PBKDF2-HMAC-SHA256 with 120,000 iterations and a 16-byte cryptographically random salt per password. The stored format SHALL be `pbkdf2$<salt_hex>$<digest_hex>`. Passwords SHALL never be stored in plaintext and SHALL never appear in logs or API responses.

#### Scenario: Password stored hashed
- **GIVEN** a user registering with a plaintext password
- **WHEN** the registration is processed
- **THEN** the `password_hash` column SHALL contain a PBKDF2 hash in `pbkdf2$<salt_hex>$<digest_hex>` format and SHALL NOT contain the original plaintext

#### Scenario: Password verification
- **GIVEN** a stored PBKDF2 hash
- **WHEN** `verify_password(plain, hashed)` is called with the correct plaintext
- **THEN** the function SHALL return `True`; with any other input it SHALL return `False`

---

### Requirement: TenantContextMiddleware on every protected request
The system SHALL run `TenantContextMiddleware` on every request. For protected paths, the middleware SHALL: (1) extract the `Authorization: Bearer <token>` header, (2) verify the JWT signature against `JWT_SECRET`, (3) confirm the token has not expired, (4) validate that `tenant_id` and `user_id` are valid UUIDs and `role` is a known value, (5) store the identity in `request.state` and `contextvars`. IF any validation step fails the middleware SHALL return `401 Unauthorized` and SHALL NOT call the downstream handler.

#### Scenario: Valid token on protected path
- **GIVEN** a request to a protected endpoint with a valid, unexpired JWT
- **WHEN** `TenantContextMiddleware` processes the request
- **THEN** the identity SHALL be stored in `request.state` and the request SHALL proceed to the route handler

#### Scenario: Missing Authorization header
- **GIVEN** a request to a protected endpoint with no `Authorization` header
- **WHEN** the middleware processes the request
- **THEN** the system SHALL return `401 Unauthorized` and SHALL NOT invoke the route handler

#### Scenario: Tampered token signature
- **GIVEN** a JWT with a modified payload but the original signature
- **WHEN** the middleware verifies the signature
- **THEN** the system SHALL return `401 Unauthorized`

---

### Requirement: Public path bypass
The middleware SHALL bypass JWT validation for the following paths: `/health`, `/api/health`, `/auth/login`, `/api/auth/login`, `/auth/register`, `/api/auth/register`, `/auth/forgot-password`, `/api/auth/forgot-password`, `/auth/reset-password`, `/api/auth/reset-password`, `/doctors`, `/api/doctors`, `/doctors/register`, `/api/doctors/register`, `/admin/register`, `/api/admin/register`, and `/doctor/availability/{id}/ndays` (and `/api/` prefixed equivalents).

#### Scenario: Login endpoint accessible without token
- **GIVEN** no Authorization header is present
- **WHEN** `POST /api/auth/login` is called
- **THEN** the middleware SHALL NOT reject the request and the login handler SHALL execute normally

#### Scenario: Public doctor list accessible without token
- **GIVEN** no Authorization header is present
- **WHEN** `GET /api/doctors` is called
- **THEN** the system SHALL return the list of active doctors without requiring authentication

---

### Requirement: Role-based access control via require_roles()
The system SHALL provide a `require_roles(*roles)` FastAPI dependency factory. WHEN the authenticated user's role is not in the allowed list the dependency SHALL raise `HTTPException(403, "Insufficient permissions")`. Every protected route SHALL declare its allowed roles explicitly via `Depends(require_roles(...))`.

#### Scenario: Correct role allowed
- **GIVEN** an authenticated ADMIN user
- **WHEN** the user calls `GET /api/admin/users`
- **THEN** the system SHALL return the user list with status 200

#### Scenario: Wrong role rejected
- **GIVEN** an authenticated PATIENT user
- **WHEN** the user calls `GET /api/admin/users`
- **THEN** the system SHALL return `403 Forbidden` with `{"detail": "Insufficient permissions"}`

#### Scenario: Multi-role endpoint
- **GIVEN** an authenticated DOCTOR user
- **WHEN** the doctor calls `PUT /api/appointments/{id}/status`
- **THEN** the system SHALL allow the request because DOCTOR is in the allowed roles `[DOCTOR, ADMIN]`

---

### Requirement: Account enumeration prevention
The login endpoint SHALL return identical error messages and status codes for both "user not found" and "wrong password" conditions. The response SHALL always be `401 {"detail": "Invalid credentials"}` regardless of which condition caused the failure.

#### Scenario: Wrong password returns generic error
- **GIVEN** a real user account in the system
- **WHEN** `POST /auth/login` is called with the correct email but wrong password
- **THEN** the system SHALL return `401 {"detail": "Invalid credentials"}`

#### Scenario: Non-existent user returns same generic error
- **GIVEN** an email address that does not exist in the tenant
- **WHEN** `POST /auth/login` is called with that email
- **THEN** the system SHALL return `401 {"detail": "Invalid credentials"}` — identical to the wrong-password response

---

### Requirement: Security response headers on every response
The system SHALL add the following headers to every HTTP response via `SecurityHeadersMiddleware`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security: max-age=31536000`, `Cache-Control: no-store`, `Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()`.

#### Scenario: Security headers present on protected endpoint
- **GIVEN** an authenticated request to any API endpoint
- **WHEN** the response is returned
- **THEN** all five security headers SHALL be present with the specified values

#### Scenario: Security headers present on public endpoint
- **GIVEN** an unauthenticated request to `GET /api/health`
- **WHEN** the response is returned
- **THEN** all five security headers SHALL be present

---

### Requirement: Auth API endpoints
The system SHALL expose four auth endpoints: `POST /auth/register` (public, registers a PATIENT), `POST /auth/login` (public, returns access token), `POST /auth/forgot-password` (public, always returns the same generic message), `POST /auth/reset-password` (public, applies a new password using a reset token). All four endpoints SHALL be accessible with and without the `/api` prefix.

#### Scenario: Successful registration
- **GIVEN** a valid email, password meeting complexity requirements, and full_name
- **WHEN** `POST /auth/register` is called
- **THEN** the system SHALL create a new user with role PATIENT and return `{user_id, email, role, tenant_id}` with status 201

#### Scenario: Forgot-password always returns same response
- **GIVEN** any email address, whether it exists in the system or not
- **WHEN** `POST /auth/forgot-password` is called
- **THEN** the system SHALL return `{"message": "If account exists, reset link sent"}` with status 200, regardless of whether the email exists
