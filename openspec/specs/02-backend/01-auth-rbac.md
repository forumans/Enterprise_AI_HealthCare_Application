# Prompt: Authentication and Role-Based Access Control

## Prompt

Implement authentication and authorization for a stateless, multi-tenant Healthcare SaaS backend. The backend runs on AWS Lambda — no sessions, no cookies, all state in the JWT.

---

### JWT Token Design

**Algorithm:** HS256 (HMAC-SHA256), secret from `JWT_SECRET` env var.

**Payload claims:**

| Claim | Type | Description |
|-------|------|-------------|
| `user_id` | UUID string | Authenticated user's ID |
| `tenant_id` | UUID string | Tenant the user belongs to |
| `role` | string | `ADMIN`, `DOCTOR`, or `PATIENT` |
| `iat` | int | Issued-at (seconds since epoch) |
| `exp` | int | Expiry (seconds since epoch) |

**Default TTL:** 30 minutes (configurable via `ACCESS_TOKEN_MINUTES` env var).

```python
# backend/app/core/security.py
def create_access_token(user_id: str, tenant_id: str, role: str, expires_minutes: int = 30) -> str:
    payload = {
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
```

---

### Password Hashing

Use **PBKDF2-HMAC-SHA256** with 120,000 iterations and a 16-byte random salt per password. This is the Python standard library `hashlib.pbkdf2_hmac` — no extra dependencies.

```python
# Output format: "pbkdf2$<salt_hex>$<digest_hex>"

def hash_password(password: str) -> str: ...
def verify_password(plain: str, hashed: str) -> bool: ...
```

Maintain backward compatibility with bcrypt hashes (for accounts migrated from earlier versions) by detecting the hash prefix.

---

### TenantContextMiddleware

File: `backend/app/middleware/tenant_middleware.py`

Runs on every request. For protected paths:

1. Read `Authorization: Bearer <token>` header.
2. Decode and verify JWT signature against `JWT_SECRET`.
3. Check token has not expired.
4. Validate `tenant_id` and `user_id` are valid UUIDs.
5. Validate `role` is one of `ADMIN`, `DOCTOR`, `PATIENT`.
6. Store identity in `request.state` and Python `contextvars`.
7. Return `401 Unauthorized` if any step fails.

**Public paths that bypass the middleware entirely:**

```python
PUBLIC_PATHS = {
    "/health", "/api/health", "/api/health/ready", "/api/health/live",
    "/auth/login", "/api/auth/login",
    "/auth/register", "/api/auth/register",
    "/auth/forgot-password", "/api/auth/forgot-password",
    "/auth/reset-password", "/api/auth/reset-password",
    "/doctors", "/api/doctors",
    "/doctors/register", "/api/doctors/register",
    "/admin/register", "/api/admin/register",
}
# Also bypass: /doctor/availability/{id}/ndays and /api/doctor/availability/{id}/ndays
```

---

### Identity and Role Dependencies

File: `backend/app/core/dependencies.py`

```python
@dataclass
class CurrentIdentity:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str

def get_current_identity(request: Request) -> CurrentIdentity:
    """Extract identity set by TenantContextMiddleware."""
    ...

def require_roles(*roles: str):
    """Return a dependency that checks the authenticated role."""
    def dependency(identity: CurrentIdentity = Depends(get_current_identity)) -> CurrentIdentity:
        if identity.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return identity
    return dependency
```

Usage in routes:
```python
@router.get("/admin/users")
async def list_users(identity: CurrentIdentity = Depends(require_roles("ADMIN"))):
    ...

@router.post("/medical-records")
async def create_record(identity: CurrentIdentity = Depends(require_roles("DOCTOR", "ADMIN"))):
    ...
```

---

### Auth API Routes

File: `backend/app/api/routes/auth.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | Public | Register a new PATIENT account |
| `POST` | `/auth/login` | Public | Login, returns `{access_token, role, tenant_id, user_name}` |
| `POST` | `/auth/forgot-password` | Public | Send password reset email |
| `POST` | `/auth/reset-password` | Public | Apply new password using reset token |

**Login response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "role": "PATIENT",
  "tenant_id": "uuid",
  "user_name": "John Doe",
  "user_id": "uuid"
}
```

**Error responses:**
- `401 {"detail": "Invalid credentials"}` — wrong email or password (never distinguish which)
- `403 {"detail": "Account inactive"}` — `is_active=false` or soft-deleted user
- `422` — validation error (missing fields, invalid format)

---

### RBAC Permission Summary

| Action | PATIENT | DOCTOR | ADMIN |
|--------|---------|--------|-------|
| Book own appointment | ✓ | — | ✓ |
| Cancel own appointment | ✓ | — | ✓ |
| View own appointments | ✓ | ✓ | ✓ |
| Manage availability | — | ✓ | ✓ |
| Create medical records | — | ✓ | ✓ |
| View own medical history | ✓ | — | ✓ |
| Upload own documents | ✓ | — | ✓ |
| View all users (tenant) | — | — | ✓ |
| Delete / restore users | — | — | ✓ |
| Reset any user's password | — | — | ✓ |
| View system reports | — | — | ✓ |

---

### Security Headers Middleware

File: `backend/app/middleware/security_headers.py`

Add to every response:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Strict-Transport-Security` | `max-age=31536000` |
| `Cache-Control` | `no-store` |
| `Permissions-Policy` | `geolocation=(), camera=(), microphone=(), payment=()` |

---

### Deliverables

- `backend/app/core/security.py` — `create_access_token`, `hash_password`, `verify_password`
- `backend/app/middleware/tenant_middleware.py` — JWT extraction, validation, public path bypass
- `backend/app/middleware/security_headers.py` — response headers
- `backend/app/core/dependencies.py` — `CurrentIdentity`, `get_current_identity`, `require_roles()`
- `backend/app/api/routes/auth.py` — register, login, forgot-password, reset-password
- `backend/tests/test_auth.py` — unit tests for JWT, password hashing, and middleware

### Acceptance Criteria

- `POST /auth/login` with valid credentials returns a JWT with correct claims.
- `POST /auth/login` with wrong password returns `401`, not `403` or `422`.
- A request with an expired token returns `401`.
- A PATIENT token accessing `/admin/users` returns `403`.
- Cross-tenant access: a valid token from Tenant A cannot access Tenant B data.
- All auth failure responses use safe, generic messages — no account enumeration.
