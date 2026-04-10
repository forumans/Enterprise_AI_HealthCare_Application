# Prompt: Security Architecture and Compliance Controls

## Prompt
Define and implement core security architecture for a multi-tenant Healthcare SaaS deployment.

### Required Project Boundaries
Keep security work partitioned by project:
- `backend/`: auth, authorization, input validation, audit.
- `frontend/`: secure token handling and route guards.
- `infrastructure/`: network boundaries, IAM, encryption configuration.
- `deployment/`: secret injection and CI security checks.
- `testing/`: security regression tests.

### Minimum Controls
1. Least privilege IAM and service-to-service access.
2. Strict tenant isolation and role-based access checks.
3. PHI-safe logs and error handling.
4. Security headers and transport security.
5. Secret management via environment and AWS Secrets Manager.
6. Audit logging for privileged and data-mutating operations.

### Deliverables
- `backend/docs/security-controls.md`
- `infrastructure/security/` policies and SG rules
- `deployment/security/ci-security-gates.md`
- `testing/security/` plan and executable checks

### Acceptance Criteria
- No hardcoded secrets in source control.
- Access decisions are testable and traceable.
- Threats for auth, tenancy, and data exposure are explicitly addressed.
