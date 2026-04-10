# test_healthcare_saas_app

Centralized test orchestration workspace for the Healthcare Application.

## What this project runs

- Backend unit tests (`unittest` in `../healthcare_saas_app/backend/tests`)
- Frontend unit tests (`vitest` in `../healthcare_saas_app/frontend/src`)
- Integration tests (`Playwright` in `tests/integration`)
- End-to-end tests (`Playwright` in `tests/e2e`)

## Commands

```bash
npm run test:db:check
npm run test:unit:backend
npm run test:unit:frontend
npm run test:integration
npm run test:e2e
npm test
```

`test:db:check` and `test:unit:backend` always use:

`postgresql+asyncpg://test_user:password@localhost/test_healthcare_db`

## Required running services for integration/E2E

- Frontend at `FRONTEND_BASE_URL` (default: `http://localhost:5173`)
- Backend at `API_BASE_URL` (default: `http://localhost:8000`)

Start backend with the test DB URL (PowerShell):

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://test_user:password@localhost/test_healthcare_db"
python -m uvicorn healthcare_saas_app.backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

## E2E admin credentials

Set before running `npm run test:e2e`:

- `ADMIN_E2E_EMAIL`
- `ADMIN_E2E_PASSWORD`

If either variable is missing, the admin E2E test is skipped.
