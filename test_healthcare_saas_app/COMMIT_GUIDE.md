# Git Commit Guide - Testing Architecture Refresh

## Scope

This guide covers commits related to:

- backend unit tests
- frontend unit tests
- integration tests
- e2e tests
- testing documentation under `test_healthcare_saas_app/testing_docs`

## Primary Files to Include

### Backend unit tests
- `healthcare_saas_app/backend/tests/test_admin_appointment_metrics.py`
- `healthcare_saas_app/backend/tests/test_auth_login.py`

### Frontend unit tests
- `healthcare_saas_app/frontend/src/components/pages/systemDashboardStats.ts`
- `healthcare_saas_app/frontend/src/components/pages/systemDashboardStats.test.ts`
- `healthcare_saas_app/frontend/src/components/pages/SystemDashboardPage.tsx`

### Central test project
- `test_healthcare_saas_app/package.json`
- `test_healthcare_saas_app/playwright.config.ts`
- `test_healthcare_saas_app/tests/integration/*`
- `test_healthcare_saas_app/tests/e2e/*`
- `test_healthcare_saas_app/PROJECT_STRUCTURE.md`

### Testing docs
- `test_healthcare_saas_app/testing_docs/00_testing_suite_overview.md`
- `test_healthcare_saas_app/testing_docs/10_unit_testing.md`
- `test_healthcare_saas_app/testing_docs/20_integration_testing.md`
- `test_healthcare_saas_app/testing_docs/30_e2e_testing.md`
- `test_healthcare_saas_app/testing_docs/40_test_execution_matrix.md`
- `test_healthcare_saas_app/testing_docs/legacy/*` (archived strategy docs)

## Suggested Commit Message

```text
test: restructure suites into unit/integration/e2e with updated docs
```

## Suggested Commit Body

```text
- Add backend unit coverage for auth login and appointment metrics
- Add frontend unit coverage for system dashboard stats mapping
- Reorganize test_healthcare_saas_app into integration + e2e projects
- Update testing specifications under test_healthcare_saas_app/testing_docs
```
