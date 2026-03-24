# test_healthcare_saas_app - Project Structure

## Current Purpose

Centralized orchestrator for the testing pyramid:

1. Backend unit tests
2. Frontend unit tests
3. Integration tests
4. E2E tests

## Directory Layout

```text
test_healthcare_saas_app/
  package.json
  playwright.config.ts
  tests/
    db_connection_test.py
    integration/
      api-health.integration.spec.ts
      login-ui-backend.integration.spec.ts
    e2e/
      admin-dashboard-metrics.e2e.spec.ts
```

## Notes

- Active Playwright projects are defined in `playwright.config.ts` as:
  - `integration`
  - `e2e`
- Backend/frontend unit tests are run from this project through script orchestration, while test files live in their source projects.

## Commands

```bash
npm run test:unit:backend
npm run test:unit:frontend
npm run test:integration
npm run test:e2e
npm test
```
