# Phase Run: Backend

Implement this phase only:
- `docs/specifications/03-backend/01_authentication_authorization.md`
- `docs/specifications/03-backend/02_rate_limiting_caching.md`
- `docs/specifications/03-backend/03_api_gateway_middleware.md`

Use these reference docs as strict constraints:
- `docs/specifications/00-governance/Enterprise_Reference/06_ANTI_PATTERNS.md`
- `docs/specifications/00-governance/Enterprise_Reference/08_CI_MINIMUM_GATES.md`
- `docs/specifications/00-governance/Enterprise_Reference/04_PHASE_CHECKPOINT_TEMPLATE.md`
- `docs/specifications/00-governance/Enterprise_Reference/07_CONTRACT_CHANGE_POLICY.md`

Do not implement or modify the reference docs themselves.
Use them only to constrain implementation and reporting behavior.

Execution rules:
1. Implement only backend scope.
2. Keep service-layer boundaries and avoid route-heavy business logic.
3. Run targeted checks for auth, RBAC, middleware, and health endpoint semantics.
4. Report start/end time and duration.
5. Return output in checkpoint template format.
