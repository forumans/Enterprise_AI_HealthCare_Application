# Phase Run Template (Claude Code / Codex)

Copy this template for each phase run.

## Prompt
Implement this phase only:
- `<PHASE_PROMPT_PATH_1>`
- `<PHASE_PROMPT_PATH_2>` (optional)

Use these reference docs as strict constraints:
- `docs/specifications/00-governance/Enterprise_Reference/06_ANTI_PATTERNS.md`
- `docs/specifications/00-governance/Enterprise_Reference/08_CI_MINIMUM_GATES.md`
- `docs/specifications/00-governance/Enterprise_Reference/04_PHASE_CHECKPOINT_TEMPLATE.md`

Do not implement or modify the reference docs themselves.
Use them only to constrain implementation and reporting behavior.

## Execution Rules
1. Scope lock:
   - Only implement the requested phase.
   - Do not start next phase tasks.
2. Architecture lock:
   - Preserve `frontend/`, `backend/`, `testing/`, `infrastructure/`, `deployment/` separation.
3. Progress:
   - Provide short progress updates regularly.
4. Validation:
   - Run targeted checks relevant to this phase.
5. Reporting:
   - Include start time, end time, and elapsed duration.
   - End with output in `PHASE_CHECKPOINT_TEMPLATE` format.

## Optional Additional Constraints
- Add contract enforcement:
  - `docs/specifications/00-governance/Enterprise_Reference/07_CONTRACT_CHANGE_POLICY.md`
- Add handoff format:
  - `docs/specifications/00-governance/Enterprise_Reference/05_SESSION_HANDOFF_TEMPLATE.md`

## Example (Backend Phase)
Implement this phase only:
- `docs/specifications/03-backend/01_authentication_authorization.md`
- `docs/specifications/03-backend/03_api_gateway_middleware.md`

Use these reference docs as strict constraints:
- `docs/specifications/00-governance/Enterprise_Reference/06_ANTI_PATTERNS.md`
- `docs/specifications/00-governance/Enterprise_Reference/08_CI_MINIMUM_GATES.md`
- `docs/specifications/00-governance/Enterprise_Reference/04_PHASE_CHECKPOINT_TEMPLATE.md`

Do not implement or modify the reference docs themselves.
