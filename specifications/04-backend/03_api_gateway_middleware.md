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

### Deployment Context

This backend runs as an AWS Lambda function wrapped with the **Mangum ASGI adapter**. The adapter translates API Gateway HTTP API events into ASGI requests before they reach FastAPI middleware. Middleware must be compatible with stateless, single-invocation Lambda execution:

- No in-memory state that persists across requests (use `contextvars` or request-scoped state only)
- `lifespan="off"` in Mangum — FastAPI lifespan events do not run in Lambda
- CORS is handled entirely within `CORSMiddleware` in FastAPI — API Gateway must NOT be configured to add CORS headers (doing so causes duplicate headers that break browsers)

### Acceptance Criteria
- No middleware ordering conflicts (auth/tenant/audit/security).
- CORS and auth behavior is deterministic by environment config.
- Health endpoints respond correctly to both direct API Gateway invocations and CloudFront-proxied requests.
- All middleware is stateless and safe for concurrent Lambda execution environments.
