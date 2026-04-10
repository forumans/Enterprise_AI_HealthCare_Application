# Phase Run: Deployment

Implement this phase only:
- `docs/specifications/08-deployment/01_deployment_architecture_prompt.md`
- `docs/specifications/08-deployment/02_cicd_release_prompt.md`
- `docs/specifications/09-aws/AWS_Checklist_15_Minute_StepByStep.md`

Use these reference docs as strict constraints:
- `docs/specifications/00-governance/Enterprise_Reference/06_ANTI_PATTERNS.md`
- `docs/specifications/00-governance/Enterprise_Reference/08_CI_MINIMUM_GATES.md`
- `docs/specifications/00-governance/Enterprise_Reference/04_PHASE_CHECKPOINT_TEMPLATE.md`
- `docs/specifications/00-governance/Enterprise_Reference/07_CONTRACT_CHANGE_POLICY.md`

Do not implement or modify the reference docs themselves.
Use them only to constrain implementation and reporting behavior.

Execution rules:
1. Implement only deployment/infrastructure scope.
2. Keep backend/frontend deploy flows independently operable.
3. Enforce migration-first backend rollout and rollback runbooks.
4. Run targeted CI/deploy validation checks.
5. Report start/end time and duration, then checkpoint summary.
