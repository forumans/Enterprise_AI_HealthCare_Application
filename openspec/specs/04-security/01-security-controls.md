# Prompt: Security Controls

## Prompt

Implement all security controls for this multi-tenant Healthcare SaaS platform. Security is enforced at the backend — the frontend enforces it only as a UX convenience.

---

### Permission Matrix

Every endpoint must enforce role check AND tenant ownership. Frontend role guards are not sufficient.

| Resource | Action | PATIENT | DOCTOR | ADMIN |
|----------|--------|---------|--------|-------|
| Own profile | Read / Write | ✓ | ✓ | ✓ |
| Other user profiles | Read | — | — | ✓ |
| Any user | Delete / Restore | — | — | ✓ |
| Own appointments | Book / Cancel | ✓ | — | ✓ |
| Own appointments | Read | ✓ | ✓ | ✓ |
| Any appointment | Read | — | — | ✓ |
| Appointment status | Update | — | ✓ | ✓ |
| Doctor availability | Create / Update | — | ✓ | ✓ |
| Doctor availability | Read | ✓ (public) | ✓ | ✓ |
| Medical records | Create | — | ✓ | ✓ |
| Own medical history | Read | ✓ | — | ✓ |
| Own prescriptions | Read | ✓ | — | ✓ |
| Prescriptions | Create | — | ✓ | ✓ |
| Own documents | Upload / Read | ✓ | — | ✓ |
| System reports | Read | — | — | ✓ |
| Audit logs | Read | — | — | ✓ |

---

### Tenant Isolation

The `tenant_id` claim in the JWT is used to scope **every** database query. A user from Tenant A can never access Tenant B data even with a valid token.

```python
# Every service method must filter by tenant_id
stmt = select(User).where(
    User.tenant_id == identity.tenant_id,
    User.deleted_at.is_(None),
)
```

Write integration tests that attempt cross-tenant access and verify they return 403 or empty results.

---

### Password Requirements

- Minimum 8 characters
- At least one uppercase, one lowercase, one digit
- Hashed with PBKDF2-HMAC-SHA256, 120,000 iterations, 16-byte random salt
- Never stored in plaintext; never logged; never returned in API responses

---

### Encryption

**In transit:** TLS enforced at CloudFront. All HTTP traffic is redirected to HTTPS at the CloudFront distribution level.

**At rest:**
- RDS: enable encryption at rest (AWS KMS managed key) at instance creation.
- S3 (documents): enable server-side encryption (`SSE-S3` or `SSE-KMS`).
- S3 (frontend assets): no sensitive data, standard S3 defaults.

---

### IAM Least Privilege

**Lambda execution role** needs only:
```json
{
  "s3:PutObject": "arn:aws:s3:::healthcare-patient-documents/*",
  "s3:GetObject": "arn:aws:s3:::healthcare-patient-documents/*",
  "logs:CreateLogGroup": "*",
  "logs:CreateLogStream": "*",
  "logs:PutLogEvents": "*",
  "ec2:CreateNetworkInterface": "*",
  "ec2:DescribeNetworkInterfaces": "*",
  "ec2:DeleteNetworkInterface": "*"
}
```

**CI/CD deploy user** needs only what SAM requires — no `AdministratorAccess`.

---

### CORS Policy

CORS is handled **only** in FastAPI `CORSMiddleware`. API Gateway must **not** be configured to add CORS headers — this would cause duplicate headers that browsers reject.

```python
CORSMiddleware(
    allow_origins=["https://your-cloudfront-domain.cloudfront.net"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

In local development, also allow `http://127.0.0.1:5173` and `http://localhost:5173`.

---

### Security Headers

Add to every response (see `SecurityHeadersMiddleware`):

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `Strict-Transport-Security` | `max-age=31536000` | Force HTTPS |
| `Cache-Control` | `no-store` | Prevent API response caching |
| `Permissions-Policy` | `geolocation=(), camera=(), microphone=(), payment=()` | Restrict browser features |

---

### PHI Safety Rules

These must never appear in logs, error messages, or API responses:
- Passwords or password hashes
- JWT tokens or signing secrets
- Patient names, dates of birth, addresses
- Medical diagnoses, symptoms, or lab results (except in authorized data responses)
- Insurance policy numbers

Log format:
```json
{
  "timestamp": "2025-01-01T00:00:00Z",
  "level": "INFO",
  "request_id": "uuid",
  "tenant_id": "uuid",    ← tenant UUID is OK (not PHI)
  "path": "/api/appointments",
  "status_code": 200,
  "duration_ms": 45
}
```

---

### Input Validation

Use Pydantic models for all request bodies. Never trust client input:
- Validate email format with regex or Pydantic's `EmailStr`
- Sanitize filenames before using them in S3 keys (`werkzeug.utils.secure_filename` or equivalent)
- Reject file uploads with unsupported MIME types
- Enforce max upload size server-side (not just frontend)

---

### Anti-Patterns to Avoid

- Using `create_all` as the production schema strategy
- Logging tokens, passwords, or PHI
- Treating frontend role checks as sufficient authorization
- Using broad wildcard CORS (`allow_origins=["*"]`) in production
- Hardcoding secrets in source files or CI workflow files
- Returning different error messages for "user not found" vs "wrong password" (enables account enumeration)
- Writing migrations without rollback planning

---

### Deliverables

- `backend/app/middleware/security_headers.py` — response headers
- `backend/app/middleware/tenant_middleware.py` — JWT validation and tenant enforcement
- `backend/app/core/dependencies.py` — `require_roles()` enforcement
- `backend/docs/security-controls.md` — permission matrix and threat model notes
- `backend/tests/test_rbac.py` — role tests: correct role allowed, wrong role 403, cross-tenant 403/empty

### Acceptance Criteria

- Every protected endpoint returns 403 for the wrong role.
- Cross-tenant access attempts return 403 or empty results — never foreign tenant data.
- Security headers are present on every response.
- No PHI appears in any log output.
- Passwords are never stored in plaintext or returned in any API response.
- S3 bucket and RDS have encryption at rest enabled.
