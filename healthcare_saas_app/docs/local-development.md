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
cd healthcare_saas_app/backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

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
# Backend unit tests (from backend directory)
cd healthcare_saas_app/backend
pytest

# Frontend unit tests
cd healthcare_saas_app/frontend
npm run test

# E2E tests (requires both servers running)
cd healthcare_saas_app
npx playwright test --config=playwright.simple.config.ts

# View E2E report
npx playwright show-report
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
