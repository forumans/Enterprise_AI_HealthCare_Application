# Integration Testing Specification

## Goal
Validate UI-to-backend contract behavior without requiring full multi-step user journeys.

## Runner
Playwright project: `integration`

Location: `test_healthcare_saas_app/tests/integration`

## Current Integration Tests

1. `api-health.integration.spec.ts`
   - verifies backend `/api/health` is reachable and returns success

2. `login-ui-backend.integration.spec.ts`
   - drives admin login form
   - confirms UI makes `POST /auth/login`
   - validates backend 401 behavior for invalid credentials

## Command
```bash
npm run test:integration
```

## Environment
- `FRONTEND_BASE_URL` (default `http://localhost:5173`)
- `API_BASE_URL` (default `http://localhost:8000`)

## Integration Test Rules

1. Assert HTTP contract + minimal UI reflection
2. Keep fixtures lightweight
3. Avoid broad feature-walkthroughs (those belong to E2E)
