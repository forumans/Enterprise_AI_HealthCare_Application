# API Contract Change Policy

## Policy
API contract changes must be declared before implementation and validated before merge.

## Required Workflow
1. Update OpenAPI contract (`backend/docs/openapi.yaml`).
2. Regenerate or update typed client types in frontend.
3. Add/update contract and integration tests.
4. Document migration notes for breaking changes.

## Change Types
- Non-breaking:
  - add optional fields,
  - add new endpoints,
  - add enum values only if clients tolerate it.
- Breaking:
  - remove/rename fields,
  - change response envelope,
  - change status code semantics,
  - tighten validation rules.

## Merge Criteria
- Contract diff reviewed.
- Client update completed.
- Contract/integration tests pass.
- Release note includes compatibility guidance.
