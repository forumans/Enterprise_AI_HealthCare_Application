# Prompt: Access Control and Permissions Matrix

## Prompt
Design and implement a complete access control model for Healthcare SaaS roles and tenant boundaries.

### Roles
- `ADMIN`: tenant administration and privileged management actions.
- `DOCTOR`: clinical operations within own tenant.
- `PATIENT`: self-service and own-record access only.

### Requirements
1. Build a permission matrix by role and endpoint/action.
2. Enforce both role checks and tenant ownership checks.
3. Add explicit policies for soft-delete/restore and admin-only actions.
4. Include denial logging for audit and troubleshooting.

### Deliverables
- `backend/docs/permission-matrix.md`
- Policy enforcement helpers in `backend/app/core/dependencies.py` (or equivalent)
- Route-level tests in `testing/backend/rbac/`
- Tenant isolation regression tests in `testing/integration/`

### Acceptance Criteria
- No endpoint relies on frontend-only role checks.
- Cross-tenant access attempts fail deterministically.
- Permission changes are centrally defined and test-backed.
