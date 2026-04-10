# Prompt: API Middleware and Edge Behavior

## Prompt
Implement backend middleware and request pipeline behavior for production deployment behind ALB/API edge.

### Scope
- `backend/app/main.py`
- `backend/app/middleware/`
- Cross-cutting concerns for all API routes.

### Required Middleware Concerns
1. Request context propagation (`request_id`, `tenant_id`, `user_id`).
2. Security headers and CORS with environment-driven allowlist.
3. Tenant context extraction and enforcement.
4. Audit context capture for mutating operations.
5. Centralized exception handling with safe client responses.

### Health Endpoints
- `GET /api/health` -> dependency health, 200/503 semantics.
- `GET /api/health/ready` -> readiness, 200/503 semantics.
- `GET /api/health/live` -> process liveness, 200.

### Deliverables
- Middleware registration order documented in code and `backend/docs/middleware-order.md`.
- Structured error response format used consistently.
- Tests for middleware exclusion paths and auth-protected paths.

### Acceptance Criteria
- No middleware ordering conflicts (auth/tenant/audit/security).
- CORS and auth behavior is deterministic by environment config.
- Health endpoints are compatible with ECS/ALB health checks.
