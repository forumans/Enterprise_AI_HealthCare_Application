# Prompt: Testing Strategy Master

## Prompt
Design and implement a full testing strategy in the standalone `testing/` project, integrated with `frontend/`, `backend/`, `infrastructure/`, and `deployment/`.

### Objectives
1. Build a test pyramid with fast unit tests, focused integration tests, and critical e2e flows.
2. Enforce tenant isolation and RBAC behavior in tests.
3. Include security and performance checks in CI.

### Required Structure
```text
testing/
  frontend/
  backend/
  integration/
  e2e/
  performance/
  security/
  fixtures/
  runbooks/
```

### Deliverables
- Unified test execution docs and scripts.
- CI matrix covering backend, frontend, integration, and e2e.
- Baseline quality gates (coverage, pass thresholds, lint/type checks).

### Acceptance Criteria
- Critical patient/doctor/admin workflows are test-covered.
- Tenant and permission regressions are explicitly tested.
- CI blocks merges on failing critical suites.
