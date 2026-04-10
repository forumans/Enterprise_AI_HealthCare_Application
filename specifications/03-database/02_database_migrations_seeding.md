# Prompt: Migration-First Database Delivery

## Prompt
You are responsible for database change management in `backend/`. Implement a migration-first workflow using Alembic and safe seed data generation.

### Requirements
1. Configure Alembic in `backend/migrations/` with repeatable environment setup.
2. Generate baseline migration from current models.
3. Add migration templates/checks for:
   - new columns with defaults,
   - backfills,
   - index creation,
   - rollback compatibility.
4. Implement non-PHI seed data for local and test environments.
5. Ensure app startup does not require `create_all` in production.

### Deliverables
- `backend/migrations/` with documented revision workflow.
- `backend/scripts/seed_dev_data.py` and `backend/scripts/seed_test_data.py`.
- `backend/docs/migrations-runbook.md` with upgrade/downgrade commands.
- CI step that runs migration checks before backend tests.

### Constraints
- No destructive schema operations without explicit migration steps.
- Seeding must be deterministic when provided a seed value.
- Test fixtures must avoid real patient-identifiable data.

### Acceptance Criteria
- `alembic upgrade head` provisions the schema.
- Seeds run cleanly on empty DB.
- Rollback of latest migration is verified in CI or documented test script.
