## ADDED Requirements

### Requirement: Backend enforces RBAC and tenant ownership on every protected endpoint
Every protected endpoint SHALL verify both (1) that the authenticated role is in the allowed set and (2) that the requested resource belongs to the authenticated user's tenant. Frontend role guards SHALL NOT be considered sufficient authorization. Enforcement SHALL occur via `require_roles()` and `tenant_id` query filtering in the service layer.

#### Scenario: PATIENT cannot access admin endpoint
- **GIVEN** an authenticated PATIENT user
- **WHEN** `GET /api/admin/users` is requested with the patient's token
- **THEN** the system SHALL return `403 Forbidden` before executing any database query

#### Scenario: DOCTOR cannot book appointment for patient
- **GIVEN** an authenticated DOCTOR user
- **WHEN** `POST /api/appointments` is called with the doctor's token
- **THEN** the system SHALL return `403 Forbidden` because only PATIENT and ADMIN may book appointments

#### Scenario: ADMIN can access all tenant resources
- **GIVEN** an authenticated ADMIN user
- **WHEN** `GET /api/admin/users` is requested
- **THEN** the system SHALL return all users within the admin's tenant

---

### Requirement: Cross-tenant access is always blocked
Every database query on a tenant-owned table SHALL include `WHERE tenant_id = <jwt.tenant_id>`. A valid JWT from Tenant A SHALL never return, modify, or delete data belonging to Tenant B, regardless of what IDs are passed in the request.

#### Scenario: Cross-tenant patient data inaccessible
- **GIVEN** a valid token for a user in Tenant A and the ID of a patient in Tenant B
- **WHEN** a request is made to fetch the Tenant B patient's profile using Tenant A's token
- **THEN** the system SHALL return 403 or 404 and SHALL NOT return any Tenant B data

#### Scenario: Tenant scoping on all list endpoints
- **GIVEN** two tenants each with 10 appointments
- **WHEN** an ADMIN from Tenant A calls `GET /api/admin/appointments`
- **THEN** the response SHALL contain exactly 10 appointments from Tenant A and zero from Tenant B

---

### Requirement: Password complexity and secure hashing
Passwords SHALL meet minimum complexity requirements: at least 8 characters, one uppercase letter, one lowercase letter, and one digit. Passwords SHALL be hashed using PBKDF2-HMAC-SHA256 with 120,000 iterations and a 16-byte random salt. Passwords SHALL never be stored in plaintext, logged, or returned in any API response.

#### Scenario: Weak password rejected at registration
- **GIVEN** a user registering with password `"short"`
- **WHEN** `POST /auth/register` is called
- **THEN** the system SHALL return `422 Unprocessable Entity` with a validation error

#### Scenario: Password not in API response
- **GIVEN** a user retrieves their own profile
- **WHEN** `GET /api/patient/me` returns the profile object
- **THEN** the `password_hash` field SHALL NOT be present in the response

---

### Requirement: PHI must never appear in logs or error messages
The system SHALL NEVER log or emit in error messages: passwords, password hashes, JWT tokens, JWT signing secrets, patient names, dates of birth, addresses, medical diagnoses, symptoms, lab results, or insurance policy numbers. Structured log entries SHALL contain only: `timestamp`, `level`, `request_id`, `tenant_id` (UUID only), `path`, `method`, `status_code`, and `duration_ms`.

#### Scenario: Login failure log contains no PHI
- **GIVEN** a failed login attempt for `patient@example.com`
- **WHEN** the system logs the event
- **THEN** the log entry SHALL contain `path: /api/auth/login` and `status_code: 401` but SHALL NOT contain the email address or any password value

#### Scenario: Unhandled exception log contains no tokens
- **GIVEN** an internal exception occurs during a request
- **WHEN** the exception handler logs the error
- **THEN** the log entry SHALL contain the stack trace but SHALL NOT include the `Authorization` header value or JWT token

---

### Requirement: Input validation on all request bodies
All request bodies SHALL be validated using Pydantic models before any business logic executes. Email fields SHALL be validated with `EmailStr` or equivalent regex. File uploads SHALL be rejected if the content type or sanitised filename indicate an unsupported or dangerous type.

#### Scenario: SQL injection in login email rejected
- **GIVEN** a login attempt with email `"' OR 1=1 --"`
- **WHEN** `POST /auth/login` is called
- **THEN** the system SHALL return `401` or `422` and SHALL NOT execute any raw SQL with that input

#### Scenario: Invalid email format rejected
- **GIVEN** a registration request with `email: "not-valid"`
- **WHEN** Pydantic validates the request body
- **THEN** the system SHALL return `422 Unprocessable Entity` before any database operation

---

### Requirement: Encryption in transit and at rest
All traffic SHALL be served over HTTPS enforced at CloudFront. RDS SHALL have encryption at rest enabled using an AWS KMS managed key. The patient documents S3 bucket SHALL have server-side encryption enabled (`SSE-S3` or `SSE-KMS`).

#### Scenario: HTTP request redirected to HTTPS
- **GIVEN** a browser sends an HTTP request to the CloudFront distribution
- **WHEN** CloudFront evaluates the request
- **THEN** it SHALL redirect to HTTPS and SHALL NOT serve content over plain HTTP

---

### Requirement: CORS restricted to known origins in production
The `allow_origins` list in FastAPI's `CORSMiddleware` SHALL contain only the CloudFront domain in production. Wildcard `allow_origins=["*"]` SHALL NOT be used in any non-development environment.

#### Scenario: Production CORS rejects unknown origin
- **GIVEN** `CORS_ORIGINS` is set to the CloudFront domain only
- **WHEN** a request arrives from an unknown origin
- **THEN** the response SHALL NOT include `Access-Control-Allow-Origin` for that origin
