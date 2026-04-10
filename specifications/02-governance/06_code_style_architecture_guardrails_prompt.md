# Prompt: Code Style and Architecture Guardrails

## Prompt
Define coding and architecture guardrails that code-generation agents must follow.

### Rules
1. Keep business logic out of route handlers; use service layer.
2. Keep frontend data access centralized via API client/hooks.
3. Avoid production debug noise; logs must be environment-gated.
4. Use explicit module boundaries and avoid circular dependencies.
5. Enforce naming conventions and file organization patterns.
6. Keep interfaces typed and contract-driven.

### Deliverables
- `docs/engineering/architecture-guardrails.md`
- Lint/config rules and static checks enforcing guardrails.
- Example anti-patterns and approved patterns.

### Acceptance Criteria
- Generated code follows consistent project structure.
- Regressions in layering/style are caught in CI.
