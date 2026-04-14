# Master Prompt: Healthcare SaaS Application Generator

Use this as the entry-point prompt. It gives the agent full context, constraints, and the execution plan before any domain-specific spec is run.

---

## Prompt

You are a principal software architect and full-stack engineer. Build a production-ready, multi-tenant Healthcare SaaS platform following this specification exactly. Every decision must align with the constraints below.

---

### Project Layout

All code lives under `healthcare_saas_app/`:

```
healthcare_saas_app/
├── backend/          # FastAPI application + SAM template
│   ├── app/
│   │   ├── api/routes/
│   │   ├── core/          # config, database, security, storage, dependencies
│   │   ├── middleware/
│   │   ├── models/
│   │   └── services/
│   ├── migrations/        # Versioned SQL files (001_initial_schema.sql, ...)
│   ├── scripts/           # Seed scripts
│   ├── tests/
│   ├── template.yaml      # AWS SAM template
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api.ts         # Centralized API client
│   │   ├── App.tsx
│   │   ├── app/           # types, access, breadcrumbs, routeBreadcrumbs
│   │   ├── components/
│   │   │   ├── common/
│   │   │   ├── layout/
│   │   │   └── pages/
│   │   ├── hooks/
│   │   ├── types/
│   │   ├── constants/
│   │   ├── config/
│   │   └── utils/
│   ├── package.json
│   └── vite.config.ts
└── docs/                  # Architecture, API reference, local dev, deployment guides
```

---

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend language | Python 3.12 |
| Backend framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| ASGI adapter | Mangum (Lambda wrapper) |
| Frontend | React 18 + TypeScript + Vite |
| Router | React Router DOM v6 |
| Server state | TanStack React Query v5 |
| Unit tests (backend) | pytest + pytest-asyncio |
| Unit tests (frontend) | Vitest |
| E2E tests | Playwright |
| Database | PostgreSQL (AWS RDS) |
| Document storage | AWS S3 (private bucket) |
| Backend runtime | AWS Lambda (python3.12, 512 MB, 30s) |
| API edge | AWS API Gateway HTTP API |
| IaC | AWS SAM (`backend/template.yaml`) |
| Frontend hosting | AWS S3 + CloudFront |
| CI/CD | GitHub Actions |

---

### Hard Rules (never break these)

1. **No ECS, no ALB, no ECR, no Secrets Manager** — backend deploys via SAM to Lambda only.
2. **No Alembic** — schema managed via versioned SQL files in `backend/migrations/`. `DB_SCHEMA_INIT_ON_STARTUP=true` is for local dev only.
3. **No hardcoded secrets** — all secrets are environment variables set via SAM `--parameter-overrides`.
4. **CORS in FastAPI only** — do not configure CORS at API Gateway.
5. **JWT in React Context** — never `localStorage` or `sessionStorage`.
6. **Every protected route** enforces authentication AND the correct RBAC role.
7. **Every database query** filters by `tenant_id`.
8. **No PHI in logs** — never log emails, names, diagnoses, or tokens.
9. **Lambda connection pool** — `pool_size=1, max_overflow=0` on the SQLAlchemy engine.
10. **`lifespan="off"`** in the Mangum handler — FastAPI lifespan events don't run in Lambda.

---

### Domain Scope

**Backend domains:**
- Auth: register, login, forgot-password, reset-password
- Tenants + Users: multi-tenant isolation, soft-delete, admin user management
- Doctors: profile, availability slots (AVAILABLE / BOOKED / BLOCKED)
- Patients: profile, medical history, prescriptions, document uploads
- Appointments: book → confirm → complete / cancel status lifecycle
- Medical Records: doctor-created after appointment completion
- Prescriptions: linked to medical records, optional pharmacy reference
- Pharmacies: reference list for prescription routing
- Audit Logs: immutable write trail for all mutations

**Frontend domains:**
- Public: login, patient registration, doctor registration, admin registration
- Patient: appointments, medical history, prescriptions, documents, profile
- Doctor: appointments, availability, profile
- Admin: dashboard, user management, appointment overview

---

### API Route Prefix

All routes are accessible both with and without the `/api` prefix to support CloudFront `/api/*` proxying:
- `GET /health` and `GET /api/health` both work
- `POST /auth/login` and `POST /api/auth/login` both work

---

### CloudFront Architecture

```
Browser
  └── CloudFront
        ├── /api/*  ──► API Gateway HTTP API
        │                    └── Lambda (FastAPI + Mangum)
        │                          ├── RDS PostgreSQL (VPC private)
        │                          └── S3 (document storage)
        └── /*      ──► S3 (React static assets)
```

The `/api/*` CloudFront behavior must use `AllViewerExceptHostHeader` origin request policy. Without it, API Gateway returns 403 (wrong Host header) and CloudFront serves `index.html` for every API call.

---

### Execution Plan

Run the specs in this order. Validate each step before continuing.

1. **Database schema** (`01-database/01-schema.md`) — create all 14 SQLAlchemy models and DB config
2. **Migrations + seeds** (`01-database/02-migrations-seeds.md`) — SQL migration files, seed scripts
3. **Auth + RBAC** (`02-backend/01-auth-rbac.md`) — JWT, password hashing, middleware, RBAC guards
4. **API endpoints** (`02-backend/02-api-endpoints.md`) — all routes and service layer
5. **Middleware + config** (`02-backend/03-middleware-config.md`) — request pipeline, Lambda config
6. **S3 storage** (`02-backend/04-storage.md`) — document upload and presigned URL utility
7. **Frontend architecture** (`03-frontend/01-architecture-routing.md`) — SPA, routing, protected layouts
8. **Frontend components** (`03-frontend/02-components-ui.md`) — reusable component library
9. **State + API client** (`03-frontend/03-state-api-client.md`) — React Query, auth context, typed client
10. **Security controls** (`04-security/01-security-controls.md`) — permission matrix, encryption, headers
11. **Test strategy** (`05-testing/01-test-strategy.md`) — unit, integration, E2E, security tests
12. **AWS infrastructure** (`06-deployment/01-aws-infrastructure.md`) — SAM template, Lambda, CloudFront
13. **CI/CD** (`06-deployment/02-cicd-pipelines.md`) — GitHub Actions for backend and frontend
14. **Observability** (`07-observability/01-logging-metrics-tracing.md`) — structured logs, alarms, tracing

---

### Output Contract

After completing all specs:

1. Provide the final directory tree for `backend/` and `frontend/`.
2. Provide commands to run locally (Uvicorn + Vite).
3. Provide the SAM build + deploy commands.
4. List any known gaps or TODOs with priority.

### Quality Bar

- Production-safe defaults everywhere.
- Every generated module is importable and runnable.
- No placeholder TODO-only files — everything must be executable or explicitly scaffolded with next steps.
