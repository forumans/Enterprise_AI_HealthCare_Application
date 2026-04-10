# End-to-End (E2E) Testing Specification

## Goal
Validate critical end-user flows across frontend + backend in real browser conditions.

## Runner
Playwright project: `e2e`

Location: `test_healthcare_saas_app/tests/e2e`

## Current E2E Tests

- `admin-dashboard-metrics.e2e.spec.ts`
  - logs in as admin (env-driven credentials)
  - navigates to system dashboard
  - verifies appointment metrics API call succeeds
  - verifies tenant name and metrics widgets are visible

## Command
```bash
npm run test:e2e
```

## Required Environment Variables

- `ADMIN_E2E_EMAIL`
- `ADMIN_E2E_PASSWORD`

If these are not set, the admin E2E test is skipped by design.

## E2E Test Rules

1. Cover business-critical paths only
2. Keep assertions stable and user-visible
3. Prefer env-configured credentials/seeding over hardcoded values
4. Keep E2E suite minimal to reduce CI runtime
