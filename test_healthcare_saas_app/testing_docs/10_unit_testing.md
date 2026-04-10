# Unit Testing Specification

## Goal
Keep unit tests fast, deterministic, and independent from running services.

## Backend Unit Tests

Location: `healthcare_saas_app/backend/tests`

### Current coverage
- `test_admin_appointment_metrics.py`
  - window boundary helper behavior
  - appointment metrics endpoint response mapping
- `test_auth_login.py`
  - login fails with 401 when user does not exist
  - login returns expected payload when credentials are valid

### Command
```bash
python -m unittest ..\healthcare_saas_app\backend\tests\test_admin_appointment_metrics.py ..\healthcare_saas_app\backend\tests\test_auth_login.py
```

## Frontend Unit Tests

Location: `healthcare_saas_app/frontend/src/components/pages`

### Current coverage
- `systemDashboardStats.test.ts`
  - doctor/patient counts exclude deleted/inactive users
  - appointment metric values map correctly into dashboard state

### Command
```bash
npm --prefix ../healthcare_saas_app/frontend run test -- src/components/pages/systemDashboardStats.test.ts
```

## Unit Test Design Rules

1. No live DB/network calls
2. Prefer pure function tests where possible
3. Mock only external boundaries
4. Keep runtime under ~1s per test file for local workflows
