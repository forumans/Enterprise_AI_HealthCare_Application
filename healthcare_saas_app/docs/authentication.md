# Authentication & Authorization

---

## Overview

The application uses **stateless JWT authentication**. No server-side sessions are stored. Every API request carries a signed token that the backend validates independently on each call — making this approach ideal for Lambda (no shared state between invocations).

---

## JWT Token

### Structure

Tokens use the **HS256** algorithm (HMAC with SHA-256). The secret key is configured via the `JWT_SECRET` environment variable.

**Payload claims:**

| Claim | Type | Description |
|---|---|---|
| `user_id` | UUID string | Authenticated user's ID |
| `tenant_id` | UUID string | Tenant the user belongs to |
| `role` | string | `ADMIN`, `DOCTOR`, or `PATIENT` |
| `iat` | int | Issued-at timestamp (seconds since epoch) |
| `exp` | int | Expiry timestamp (seconds since epoch) |

**Default expiry:** 30 minutes (configurable via `ACCESS_TOKEN_MINUTES` env var)

### Creating a Token

```python
# core/security.py
create_access_token(
    user_id="uuid",
    tenant_id="uuid",
    role="PATIENT",
    expires_minutes=30
) -> str
```

### Using a Token

Include the token in the `Authorization` header of every protected request:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Password Security

Passwords are hashed using **PBKDF2-HMAC-SHA256**:

- **Iterations:** 120,000
- **Salt:** 16 random bytes (unique per password)
- **Output format:** `pbkdf2$<salt_hex>$<digest_hex>`

The system is also backward-compatible with bcrypt hashes (for accounts migrated from earlier versions).

---

## Authentication Middleware

**File:** `backend/app/middleware/tenant_middleware.py`

`TenantContextMiddleware` runs on every request. For protected routes it:

1. Reads the `Authorization` header
2. Extracts the Bearer token
3. Decodes and verifies the JWT signature against `JWT_SECRET`
4. Checks the token has not expired
5. Validates `tenant_id` and `user_id` are valid UUIDs
6. Validates `role` is one of `ADMIN`, `DOCTOR`, `PATIENT`
7. Stores the identity in `request.state` and Python `contextvars` (for async access)
8. Returns `401 Unauthorized` if any step fails

### Public Paths (no token required)

The following paths bypass the middleware entirely:

```
GET  /health
GET  /api/health
GET  /api/health/ready
GET  /api/health/live

POST /auth/login
POST /api/auth/login
POST /auth/register
POST /api/auth/register
POST /auth/forgot-password
POST /api/auth/forgot-password
POST /auth/reset-password
POST /api/auth/reset-password

GET  /doctors
GET  /api/doctors
POST /doctors/register
POST /api/doctors/register
POST /admin/register
POST /api/admin/register

GET  /doctor/availability/{doctor_id}/ndays
GET  /api/doctor/availability/{doctor_id}/ndays
```

---

## Role-Based Access Control (RBAC)

### Roles

| Role | Description |
|---|---|
| `PATIENT` | Registered patient — access to own records only |
| `DOCTOR` | Healthcare provider — access to assigned appointments and patient records |
| `ADMIN` | System administrator — full access |

### How Roles Are Enforced

Each protected route declares which roles are allowed using the `require_roles()` dependency:

```python
# core/dependencies.py
@router.get("/admin/users")
async def list_users(
    identity: CurrentIdentity = Depends(require_roles("ADMIN"))
):
    ...

@router.post("/medical-records")
async def create_record(
    identity: CurrentIdentity = Depends(require_roles("DOCTOR", "ADMIN"))
):
    ...
```

If the authenticated user's role is not in the allowed list, the endpoint returns `403 Forbidden`.

### Permissions by Role

#### PATIENT
- Book and cancel own appointments
- View own upcoming appointments
- View own medical history and prescriptions
- Upload and view own documents
- View own profile

#### DOCTOR
- View and manage own availability slots
- View assigned appointments (today, upcoming, all, weekly)
- Create medical records for completed appointments
- Create prescriptions linked to medical records
- Search patients
- View and update own profile

#### ADMIN
- All DOCTOR and PATIENT permissions
- Create, restore, and soft-delete any user
- Reset any user's password
- View all users and appointments (system-wide)
- View audit logs
- Access system reports and metrics
- Manage tenants

---

## Identity in Request Handlers

After middleware validation, the identity is available in route handlers via dependency injection:

```python
from app.core.dependencies import CurrentIdentity, get_current_identity, require_roles

@router.get("/my-profile")
async def get_profile(
    identity: CurrentIdentity = Depends(get_current_identity),
    db: AsyncSession = Depends(get_db),
):
    # identity.user_id   → UUID of the authenticated user
    # identity.tenant_id → UUID of the tenant
    # identity.role      → "ADMIN" | "DOCTOR" | "PATIENT"
    ...
```

---

## Multi-Tenancy and Data Isolation

The `tenant_id` claim in the JWT is used to scope all database queries. Every query includes a filter such as:

```python
select(Patient).where(
    Patient.tenant_id == identity.tenant_id,
    Patient.deleted_at.is_(None),
)
```

This means a user from Tenant A can **never** access data belonging to Tenant B, even if they somehow obtain a valid token — because their token's `tenant_id` will not match the other tenant's records.

---

## Security Headers

`SecurityHeadersMiddleware` adds the following headers to every response:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Strict-Transport-Security` | `max-age=31536000` |
| `Cache-Control` | `no-store` |
| `Permissions-Policy` | `geolocation=(), camera=(), microphone=(), payment=()` |

---

## CORS

**File:** `backend/app/main.py`

CORS is configured via the `CORS_ORIGINS` environment variable (comma-separated list of allowed origins):

```python
CORSMiddleware(
    allow_origins=["https://your-cloudfront-domain.cloudfront.net"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

CORS is handled entirely by FastAPI. API Gateway does **not** add CORS headers — adding them at both layers would cause duplicate headers and break browser requests.
