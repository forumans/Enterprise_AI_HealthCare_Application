# Local Development

This guide walks through running the full stack locally: backend on Uvicorn and frontend on Vite.

---

## Prerequisites

| Tool | Minimum Version | Notes |
|---|---|---|
| Python | 3.12+ | Match the Lambda runtime |
| Node.js | 18+ | For the React frontend |
| PostgreSQL | 12+ | Local database |
| Git | Any | |

---

## 1. Clone the Repository

```bash
git clone https://github.com/forumans/Enterprise_AI_HealthCare_Application.git
cd Enterprise_AI_HealthCare_Application
```

---

## 2. Create a Python Virtual Environment

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Backend Dependencies

```bash
pip install -r healthcare_saas_app/backend/requirements.txt
```

`requirements.txt` pins **exact** versions - the same ones the AWS Lambda runs - so local, the tests
and AWS behave the same. Install into the project's `.venv`, not your system Python: other tools on
the machine share the system interpreter and can need different versions (e.g. `click`).

---

## 4. Set Up a Local PostgreSQL Database

```sql
-- Run in psql as a superuser
CREATE USER healthcare_user WITH PASSWORD 'DevPassword';
CREATE DATABASE healthcare_saas_db_local OWNER healthcare_user;
GRANT ALL PRIVILEGES ON DATABASE healthcare_saas_db_local TO healthcare_user;
```

Test the connection:
```bash
psql -U healthcare_user -d healthcare_saas_db_local -c "SELECT version();"
```

---

## 5. Configure Backend Environment Variables

Create `healthcare_saas_app/backend/.env` (this file is gitignored):

```bash
cp healthcare_saas_app/backend/.env.example healthcare_saas_app/backend/.env
```

Edit `.env` with your local values:

```env
DATABASE_URL=postgresql+asyncpg://healthcare_user:DevPassword@localhost:5432/healthcare_saas_db_local
JWT_SECRET=local-dev-secret-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=30
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174
DB_SCHEMA_INIT_ON_STARTUP=true
APP_ENV=dev
```

> `DB_SCHEMA_INIT_ON_STARTUP=true` causes FastAPI to auto-create all database tables on startup. Set to `false` in production.

---

## 6. Run the Backend

```bash
# Activate the project's .venv first (step 2) - otherwise "uvicorn" may be the system Python's,
# running different package versions than AWS
cd healthcare_saas_app/backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

To make sure you're on the venv: `python -c "import sys, sqlalchemy; print(sys.executable, sqlalchemy.__version__)"`
should print a path inside `.venv` and the version pinned in `requirements.txt`.

The backend starts at `http://127.0.0.1:8000`.

**Useful URLs:**
- Health check: `http://127.0.0.1:8000/api/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 7. Install Frontend Dependencies

```bash
cd healthcare_saas_app/frontend
npm install
```

---

## 8. Configure Frontend Environment Variables

Create `healthcare_saas_app/frontend/.env.local` (this file is gitignored):

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 9. Run the Frontend

```bash
cd healthcare_saas_app/frontend
npm run dev
```

The frontend starts at `http://127.0.0.1:5173` (or `5174` if 5173 is busy).

---

## 10. Register a Test User

With both servers running, open `http://127.0.0.1:5173` in your browser and register via the UI, or use curl:

```bash
# Register a patient
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"patient@test.com","password":"Password123","full_name":"Test Patient"}'

# Log in
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"patient@test.com","password":"Password123"}'
```

---

## Testing with SAM Local (Optional)

SAM local simulates the Lambda + API Gateway execution environment using Docker. Use this for a final pre-deploy verification.

**Prerequisites:** Docker Desktop must be running.

**Create `healthcare_saas_app/backend/local-env.json`** (gitignored):

```json
{
  "BackendFunction": {
    "DATABASE_URL": "postgresql+asyncpg://healthcare_user:DevPassword@host.docker.internal:5432/healthcare_saas_db_local",
    "JWT_SECRET": "local-dev-secret",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_TOKEN_MINUTES": "30",
    "CORS_ORIGINS": "http://localhost:5173,http://localhost:5174",
    "DB_SCHEMA_INIT_ON_STARTUP": "true",
    "S3_BUCKET_NAME": "your-documents-bucket",
    "APP_ENV": "production"
  }
}
```

> Use `host.docker.internal` (not `localhost`) — Docker containers cannot reach the host machine via `localhost`.

**Build and start:**

```bash
cd healthcare_saas_app/backend
sam build
sam local start-api --env-vars local-env.json --port 8000
```

The API is available at `http://127.0.0.1:8000`, identical to Uvicorn. Cold starts take ~5s on the first request (Docker container initialisation).

---

## Running Tests

```bash
# Backend tests (run from healthcare_saas_app - the tests import `backend.app...`;
# backend/.env must be loaded into the environment, e.g. via your shell or IDE)
cd healthcare_saas_app
python -m unittest discover -s backend/tests -t .

# Frontend unit tests
cd healthcare_saas_app/frontend
npm run test

# E2E tests (requires both servers running)
cd healthcare_saas_app
npx playwright test --config=playwright.simple.config.ts

# View E2E report
npx playwright show-report
```

### PostgreSQL integration tests

`backend/tests/integration` runs the core scheduling flows against a real PostgreSQL database:
- **Migration 003:** every value is preserved; reruns, rollback and invalid data are handled safely.
- **Slots:** 8 AM–11 PM default generation, including across daylight-saving changes; the rolling 7-day top-up; and concurrent loads.
- **Appointments:** book → cancel → rebook through the booking trigger, double-booking rejection, and the clinic-local "today" and week views.
- **Reschedule & cancel:** patients and doctors moving an appointment (details and status kept, old slot freed, audit logged); rejection of taken, past, same-time, completed and cross-doctor double-booked slots; ownership checks; and patients/doctors cancelling confirmed appointments.
- **Support staff:** registration, profile, patient/doctor search (name, email, phone, `*`), booking/updating/rescheduling/cancelling on behalf of patients and doctors, and blocking/unblocking doctors' slots.
- **Admin accounts:** role-based user search, changing login email and resetting password by user id, deactivating/activating (no self-deactivation, at least one active admin), and soft delete.
- **Permissions:** who may change which appointments and slots; booked slots can't be blocked or deleted.
- **Migration 004:** the evening-slot backfill.
- **End-to-end HTTP (`test_http_flows.py`):** starts the real backend with uvicorn on a free local port and drives the support staff, admin account and permission flows through login, JWTs, middleware and role guards.

Database-free unit tests (always run) cover route role guards (`test_role_access.py`), the shared search helper and request validation (`test_search_and_validation.py`), and route registration.

They are **skipped** unless `HC_TEST_PG_ADMIN_URL` points at a *disposable* server. Each test creates its own `hc_it_<random>` database from `baseline_schema_pre_003.sql` and drops it afterwards, so never point it at a server holding data you care about:

```bash
docker run -d --name hc-test-pg -e POSTGRES_PASSWORD=test -p 55440:5432 postgres:17
export HC_TEST_PG_ADMIN_URL=postgresql://postgres:test@localhost:55440/postgres   # PowerShell: $env:HC_TEST_PG_ADMIN_URL="..."
python -m unittest discover -s backend/tests -t .
docker rm -f hc-test-pg
```

---

## Common Issues

### `asyncpg` connection refused
Ensure PostgreSQL is running and the connection string is correct:
```bash
pg_isready -h localhost -p 5432
```

### `DB_SCHEMA_INIT_ON_STARTUP` errors
If you see table-not-found errors, make sure `DB_SCHEMA_INIT_ON_STARTUP=true` is set and restart the backend. The tables are created on startup.

### CORS errors in browser
Ensure `CORS_ORIGINS` includes the exact origin your frontend is running on (check the port number in the Vite output).

### Frontend can't reach backend
Check `VITE_API_BASE_URL` in `.env.local` matches the port Uvicorn is listening on.

### `S3_BUCKET_NAME` not set warning
Document uploads will fail locally unless you set a real S3 bucket name and have AWS credentials configured. For local testing without S3, skip document upload tests.

### Something works locally but fails on AWS with a time-related error
Lambda's system clock runs in UTC. Any code that calls `datetime.now()` without a timezone returns your machine's local time locally but UTC on Lambda. If a time comparison behaves differently between environments, check that the code uses `datetime.now(timezone.utc)` rather than bare `datetime.now()`.

See the [Datetime and Timezone Convention](architecture.md#datetime-and-timezone-convention) section in the architecture guide for the full set of rules.

---

## Keeping local and AWS aligned

| Layer | How it stays aligned | How to check |
|---|---|---|
| Code | Deploy from a clean `master` with `aws_env_spin_up/scripts/deploy-update.ps1` | `git status` clean and `HEAD` = `origin/master` |
| Python packages | Exact pins in `backend/requirements.txt` (SAM builds the Lambda from it) | `pip install -r requirements.txt` in `.venv`; run the tests |
| Database schema | Run every migration on both: locally with `psql`/pgAdmin as `postgres`, on AWS with `run-migration.ps1` | `run-migration.ps1 -SchemaSnapshot <file>` then `python compare_schema.py <file>` (both in `aws_env_spin_up/scripts`) |
| Frontend | `deploy-update.ps1` builds from the same lockfile and `.env.production` | Build locally and compare `dist/` with the files CloudFront serves |

Differences that are expected and fine: `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `APP_ENV`, `HOST`/`PORT`
(local-only), the data itself, and the database `TimeZone` setting (AWS `UTC`, local `America/New_York` -
every timestamp column is `timestamptz` and the backend binds aware datetimes, so it only changes how
tools like pgAdmin display times). Document uploads need `S3_BUCKET_NAME`, which only AWS sets, so
`POST /api/documents` and `/api/patient/documents` fail locally (no screen uses them yet).
