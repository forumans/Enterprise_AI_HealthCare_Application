# Prompt: API Contract First

## Prompt
Define API contracts before implementation. Produce OpenAPI-first backend contracts used by both `backend/` and `frontend/`.

### Requirements
1. Define route groups: auth, tenants, users, patients, doctors, appointments, records, prescriptions, admin.
2. Standardize error envelope and status-code behavior.
3. Define pagination, filtering, and sorting conventions.
4. Define request/response schemas with strict typing and examples.
5. Add versioning strategy (for example `/api/v1`).

### Deliverables
- OpenAPI spec file in `backend/docs/openapi.yaml`.
- Frontend API types generated or hand-authored from the contract.
- Contract tests in `testing/integration/` for critical endpoints.

### Acceptance Criteria
- Frontend consumes typed contracts without ad-hoc schema assumptions.
- Contract-breaking changes are detected in CI.
