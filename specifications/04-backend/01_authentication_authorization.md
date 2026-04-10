# Prompt: Backend Authentication and Authorization

## Prompt
You are implementing authentication and authorization in `backend/` for a multi-tenant Healthcare SaaS platform.

### Architecture Contract
- Keep project boundaries: `frontend/`, `backend/`, `testing/`, `infrastructure/`, `deployment/`.
- Backend must remain stateless and production-ready for ECS Fargate.

### Requirements
1. Implement JWT-based auth (`access` token, optional refresh strategy).
2. Implement RBAC roles: `ADMIN`, `DOCTOR`, `PATIENT`.
3. Enforce tenant scoping using `tenant_id` in auth context and request lifecycle.
4. Add secure password hashing (Argon2 or bcrypt with strong parameters).
5. Implement account state checks (`is_active`, soft-deleted users).
6. Ensure role mismatch handling does not leak account details.

### API Surface (minimum)
- `POST /auth/login`
- `POST /auth/register` (role-aware, least privilege)
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `GET /auth/me`

### Deliverables
- Backend modules under `backend/app/core/`, `backend/app/api/routes/`, and `backend/app/services/`.
- Dependency utilities for `require_roles(...)` and identity extraction.
- Security-focused tests in `testing/backend/` and `backend/tests/`.
- Auth threat model note in `backend/docs/auth-security.md`.

### Acceptance Criteria
- Unauthorized and forbidden paths return correct status codes.
- Tenant cross-access is blocked.
- Auth failures use safe, generic error responses.
- Critical auth behavior has automated tests.
