# Phase Run: Deployment

Implement this phase only:
- `specifications/09-deployment/01_deployment_architecture_prompt.md`
- `specifications/09-deployment/02_cicd_release_prompt.md`
- `specifications/10-reliability_monitoring/AWS_Checklist_15_Minute_StepByStep.md`

Use these reference docs as strict constraints:
- `specifications/02-governance/06_ANTI_PATTERNS.md`
- `specifications/02-governance/08_CI_MINIMUM_GATES.md`
- `specifications/02-governance/04_PHASE_CHECKPOINT_TEMPLATE.md`
- `specifications/02-governance/07_CONTRACT_CHANGE_POLICY.md`

Do not implement or modify the reference docs themselves.
Use them only to constrain implementation and reporting behavior.

Execution rules:
1. Implement only deployment/infrastructure scope.
2. Keep backend/frontend deploy flows independently operable.
3. Enforce migration-first backend rollout and rollback runbooks.
4. Run targeted CI/deploy validation checks.
5. Report start/end time and duration, then checkpoint summary.
