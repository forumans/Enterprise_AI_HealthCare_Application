# Phase Run: Testing

Implement this phase only:
- `docs/specifications/07-testing/01_testing_strategy_master.md`
- `docs/specifications/07-testing/02_backend_frontend_integration_prompt.md`
- `docs/specifications/07-testing/03_e2e_perf_security_prompt.md`

Use these reference docs as strict constraints:
- `docs/specifications/00-governance/Enterprise_Reference/06_ANTI_PATTERNS.md`
- `docs/specifications/00-governance/Enterprise_Reference/08_CI_MINIMUM_GATES.md`
- `docs/specifications/00-governance/Enterprise_Reference/04_PHASE_CHECKPOINT_TEMPLATE.md`
- `docs/specifications/00-governance/Enterprise_Reference/07_CONTRACT_CHANGE_POLICY.md`

Do not implement or modify the reference docs themselves.
Use them only to constrain implementation and reporting behavior.

Execution rules:
1. Implement only testing scope under `testing/`.
2. Cover RBAC, tenant isolation, and critical user journeys.
3. Define per-PR smoke suites and deeper scheduled suites.
4. Run targeted test commands and summarize pass/fail.
5. Report start/end time and duration, then checkpoint summary.
