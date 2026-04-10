# Prompt: Backend-Frontend Integration Testing

## Prompt
Implement integration tests validating contracts between `frontend/` and `backend/`.

### Focus Areas
1. Auth login/logout and session persistence.
2. Role-based access and route protection.
3. Appointment create/read/update flows.
4. Error contract handling and user feedback behavior.

### Deliverables
- `testing/integration/` specs for API + UI interaction.
- Test fixtures for multi-role users and tenants.
- CI job that executes integration tests with ephemeral test DB.

### Acceptance Criteria
- Breaking API contract changes are detected before merge.
- Cross-tenant access attempts fail in integration tests.
- Health/readiness endpoints are validated in deploy smoke tests.
