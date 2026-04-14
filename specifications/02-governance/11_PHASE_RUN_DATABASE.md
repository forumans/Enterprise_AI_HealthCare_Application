# Phase Run: Database

Implement this phase only:
- `docs/specifications/02-database/01_database_architecture_design.md`
- `docs/specifications/02-database/02_database_migrations_seeding.md`
- `docs/specifications/02-database/03_database_performance_optimization.md`

Use these reference docs as strict constraints:
- `specifications/02-governance/06_ANTI_PATTERNS.md`
- `specifications/02-governance/08_CI_MINIMUM_GATES.md`
- `specifications/02-governance/04_PHASE_CHECKPOINT_TEMPLATE.md`
- `specifications/02-governance/07_CONTRACT_CHANGE_POLICY.md`

Do not implement or modify the reference docs themselves.
Use them only to constrain implementation and reporting behavior.

Execution rules:
1. Implement only database scope.
2. Keep architecture separation (`frontend/backend/testing/infrastructure/deployment`).
3. Run targeted checks for migrations, models, and seed scripts.
4. Report start/end time and duration.
5. Return output in checkpoint template format.
