# Prompt: Data Initialization and Tenant Bootstrap

## Prompt
Define how environments are initialized with deterministic, non-PHI seed data and baseline tenant setup.

### Requirements
1. Create a tenant bootstrap routine:
   - default tenant metadata,
   - baseline admin account,
   - role setup.
2. Define deterministic seed datasets for local and test environments.
3. Keep seeded data realistic enough for integration and e2e tests.
4. Ensure no production PHI is ever copied into seed fixtures.

### Deliverables
- Seeding scripts in `backend/scripts/`.
- Test fixtures in `testing/fixtures/`.
- Seed runbook in `deployment/runbooks/data-bootstrap.md`.

### Acceptance Criteria
- Fresh environment can be initialized in one command sequence.
- Seed runs are repeatable with a fixed seed parameter.
