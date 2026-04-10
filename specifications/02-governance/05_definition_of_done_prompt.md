# Prompt: Definition of Done and Quality Gates

## Prompt
Define repository-wide Definition of Done (DoD) and enforceable quality gates for changes.

### DoD Minimums
1. Lint and type checks pass for frontend and backend.
2. Unit and integration tests pass for touched areas.
3. Security checks pass (dependency and secret scans).
4. Migrations included for schema changes.
5. Docs updated for behavior/config changes.
6. Observability impact considered for new critical paths.

### Deliverables
- `deployment/quality/definition-of-done.md`
- CI gates mapping in deployment workflows.
- Pull request checklist template.

### Acceptance Criteria
- DoD is machine-enforced where possible.
- Teams can evaluate “ready to merge” with objective checks.
