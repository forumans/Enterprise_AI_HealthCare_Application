# Testing Suite Overview (Current)

This document is the canonical testing strategy for the current codebase and supersedes older exploratory strategy docs in this folder.

## Current Test Stack

- **Backend unit tests**: Python `unittest` (under `healthcare_saas_app/backend/tests`)
- **Frontend unit tests**: `vitest` (under `healthcare_saas_app/frontend/src`)
- **Integration tests (UI + backend contracts)**: Playwright project `integration`
- **End-to-end tests (full user journey)**: Playwright project `e2e`
- **Central test orchestrator**: `test_healthcare_saas_app/package.json`

## Repository Layout

- `healthcare_saas_app/backend/tests/`
  - `test_admin_appointment_metrics.py`
  - `test_auth_login.py`
- `healthcare_saas_app/frontend/src/components/pages/`
  - `systemDashboardStats.ts`
  - `systemDashboardStats.test.ts`
- `test_healthcare_saas_app/tests/integration/`
  - `api-health.integration.spec.ts`
  - `login-ui-backend.integration.spec.ts`
- `test_healthcare_saas_app/tests/e2e/`
  - `admin-dashboard-metrics.e2e.spec.ts`

## Single Entry Point for Running Tests

From `test_healthcare_saas_app`:

```bash
npm test
```

This runs:
1. backend unit tests
2. frontend unit tests
3. integration tests
4. e2e tests

## Environment Expectations

- Backend running at `API_BASE_URL` (default `http://localhost:8000`)
- Frontend running at `FRONTEND_BASE_URL` (default `http://localhost:5173`)
- E2E login credentials for admin tests:
  - `ADMIN_E2E_EMAIL`
  - `ADMIN_E2E_PASSWORD`
