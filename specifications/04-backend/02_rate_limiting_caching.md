# Prompt: Backend Rate Limiting and Caching

## Prompt
You are responsible for API resilience and performance controls in `backend/`.

### Constraints
- Maintain strict project separation (`frontend/backend/testing/infrastructure/deployment`).
- Preserve HIPAA-safe behavior: no PHI in cache keys or logs.

### Requirements
1. Implement request rate limiting with role-aware and endpoint-aware policies.
2. Add short-lived caching for non-sensitive read endpoints:
   - doctor availability,
   - dashboard aggregates,
   - reference lookups (pharmacies, static metadata).
3. Define cache invalidation strategy for write operations.
4. Protect login and password-reset endpoints with stricter limits.

### Deliverables
- Middleware and/or dependency logic in `backend/app/middleware/` and `backend/app/core/`.
- Config knobs via env variables for limit windows and cache TTLs.
- Test coverage in `testing/backend/` for throttling and cache invalidation behavior.
- Operational guide in `deployment/runbooks/rate-limit-cache-ops.md`.

### Acceptance Criteria
- Limits return clear `429` responses with retry semantics.
- Cache usage measurably reduces repeated query load.
- Sensitive endpoints are never cached.
- Behavior is configurable per environment.
