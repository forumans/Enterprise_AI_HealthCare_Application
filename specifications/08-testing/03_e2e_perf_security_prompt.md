# Prompt: End-to-End, Performance, and Security Testing

## Prompt
Implement high-value non-unit tests in `testing/` to validate real-world readiness.

### End-to-End Coverage
- Admin user management and soft-delete/restore.
- Doctor availability and appointment lifecycle.
- Patient auth and appointment booking journey.

### Performance Coverage
- API load tests for auth, appointments, dashboard metrics.
- Basic frontend performance budget checks.

### Security Coverage
- RBAC negative tests.
- Tenant isolation regression tests.
- Auth brute-force/rate-limit behavior checks.

### Deliverables
- `testing/e2e/`, `testing/performance/`, and `testing/security/` suites.
- CI stages for scheduled deep tests and per-PR smoke subsets.
- Runbooks for interpreting failures in `testing/runbooks/`.

### Acceptance Criteria
- Critical production workflows pass in e2e.
- Performance regressions trigger actionable alerts.
- Security checks catch common privilege and tenancy regressions.
