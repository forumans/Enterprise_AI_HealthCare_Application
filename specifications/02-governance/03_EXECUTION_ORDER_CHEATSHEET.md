# Execution Order Cheat Sheet (Claude Code + Codex)

Use this sequence to generate the project reliably without long opaque runs.

## Working Rules
- Run prompts in phases, not all at once.
- After each phase, run a checkpoint before continuing.
- Keep architecture fixed: `frontend/`, `backend/`, `testing/`, `infrastructure/`, `deployment/`.
- Prefer short runs with visible progress updates.

## Phase Order
1. `docs/specifications/00-governance/*`
2. `docs/specifications/01-master/*`
3. `docs/specifications/02-database/*`
4. `docs/specifications/03-backend/*`
5. `docs/specifications/06-frontend/*`
6. `docs/specifications/04-security/*`
7. `docs/specifications/05-observability/*`
8. `docs/specifications/07-testing/*`
9. `docs/specifications/08-deployment/*`
10. `docs/specifications/09-aws/*`

## Per-Phase Checkpoint (Mandatory)
After each phase, ask the agent to:
1. Show changed file tree (only touched files).
2. Summarize what was implemented vs. prompt requirements.
3. Run targeted validation for that phase.
4. Report start/end time and duration.
5. List open risks before moving on.

## Claude Code Prompt Template
Use this for each phase:

```text
Implement only this phase: <PHASE_NAME>.
Use only these spec files as source of truth:
- <SPEC_FILE_1>
- <SPEC_FILE_2>

Do not start other phases.
Keep project boundaries strict:
frontend/, backend/, testing/, infrastructure/, deployment/.

Execution rules:
1) Show a short plan.
2) Implement in small steps with frequent progress updates.
3) Run targeted checks.
4) Report start time, end time, and elapsed duration.
5) Provide checkpoint summary and wait for my approval.
```

## Codex Prompt Template
Use this for each phase:

```text
Execute phase <PHASE_NAME> only.
Specs to follow:
- <SPEC_FILE_1>
- <SPEC_FILE_2>

Constraints:
- Do not touch files outside this phase unless required by dependencies.
- Preserve architecture separation: frontend/backend/testing/infrastructure/deployment.
- Keep logs concise and production-safe.

Required output:
1) Plan
2) Incremental implementation updates
3) Targeted verification results
4) Start/end timestamps and total duration
5) Checkpoint summary + blocked items
```

## Suggested Phase Bundles
- Phase A (Governance + Master):
  - `00-governance/*`
  - `01-master/01_healthcare_saas_master_specification.md`
- Phase B (Data + Core API):
  - `02-database/*`
  - `03-backend/*`
- Phase C (App UX):
  - `06-frontend/*`
- Phase D (Hardening):
  - `04-security/*`
  - `05-observability/*`
- Phase E (Validation + Delivery):
  - `07-testing/*`
  - `08-deployment/*`
  - `09-aws/*`

## Stop Conditions
Pause and request approval if:
- phase scope must be exceeded,
- major refactor is needed outside current phase,
- architecture boundary would be broken.

## Fast Validation Commands (Example)
- Backend: `cd backend && pytest -q`
- Frontend: `cd frontend && npm run test -- --runInBand`
- Integration: `cd testing && npm run test:integration`
- E2E smoke: `cd testing && npm run test:e2e:smoke`

Adjust commands to your actual package scripts.
