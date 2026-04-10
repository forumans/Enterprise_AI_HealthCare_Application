# Phase Run: Database

Implement this phase only:
- `docs/specifications/02-database/01_database_architecture_design.md`
- `docs/specifications/02-database/02_database_migrations_seeding.md`
- `docs/specifications/02-database/03_database_performance_optimization.md`

Use these reference docs as strict constraints:
- `docs/specifications/00-governance/Enterprise_Reference/06_ANTI_PATTERNS.md`
- `docs/specifications/00-governance/Enterprise_Reference/08_CI_MINIMUM_GATES.md`
- `docs/specifications/00-governance/Enterprise_Reference/04_PHASE_CHECKPOINT_TEMPLATE.md`
- `docs/specifications/00-governance/Enterprise_Reference/07_CONTRACT_CHANGE_POLICY.md`

Do not implement or modify the reference docs themselves.
Use them only to constrain implementation and reporting behavior.

Execution rules:
1. Implement only database scope.
2. Keep architecture separation (`frontend/backend/testing/infrastructure/deployment`).
3. Run targeted checks for migrations, models, and seed scripts.
4. Report start/end time and duration.
5. Return output in checkpoint template format.
