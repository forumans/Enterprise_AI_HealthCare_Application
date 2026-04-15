# Healthcare SaaS — Specification-Driven Design

This directory contains all prompts needed to rebuild this application from scratch using a code generation agent (Claude Code, Codex, or equivalent).

---

## What Gets Built

A production-ready, multi-tenant Healthcare SaaS platform with:
- **Backend:** FastAPI (Python 3.12) + SQLAlchemy 2.0 async + asyncpg, deployed as AWS Lambda via SAM
- **Frontend:** React 18 + TypeScript + Vite SPA, hosted on S3 behind CloudFront
- **Database:** PostgreSQL (AWS RDS), 14 tables, UUID PKs, soft-delete, multi-tenant isolation
- **Auth:** Stateless JWT HS256, RBAC (PATIENT / DOCTOR / ADMIN), token in React context
- **Storage:** S3 for patient documents, presigned URLs for downloads
- **Deployment:** CloudFront → API Gateway HTTP API → Lambda; SAM IaC; GitHub Actions CI/CD

---

## Execution Order

Run specs in this order. Each builds on the previous.

| Step | File | What the agent produces |
|------|------|------------------------|
| 0 | `00-master.md` | Full project scaffolding and orientation |
| 1 | `01-database/01-schema.md` | SQLAlchemy models, database config |
| 2 | `01-database/02-migrations-seeds.md` | SQL migration files, seed scripts |
| 3 | `02-backend/01-auth-rbac.md` | JWT auth, RBAC middleware, password hashing |
| 4 | `02-backend/02-api-endpoints.md` | All FastAPI routes and service layer |
| 5 | `02-backend/03-middleware-config.md` | Middleware stack, Lambda/Mangum config, rate limiting |
| 6 | `02-backend/04-storage.md` | S3 upload utility, presigned URL generation |
| 7 | `03-frontend/01-architecture-routing.md` | React SPA, routing, protected layouts |
| 8 | `03-frontend/02-components-ui.md` | Reusable component system |
| 9 | `03-frontend/03-state-api-client.md` | React Query, auth context, typed API client |
| 10 | `04-security/01-security-controls.md` | Permission matrix, encryption, security headers |
| 11 | `05-testing/01-test-strategy.md` | Unit, integration, E2E, security tests |
| 12 | `06-deployment/01-aws-infrastructure.md` | SAM template, Lambda, CloudFront config |
| 13 | `06-deployment/02-cicd-pipelines.md` | GitHub Actions workflows |
| 14 | `06-deployment/03-bootstrap-checklist.md` | First AWS deploy, step-by-step |
| 15 | `07-observability/01-logging-metrics-tracing.md` | Structured logs, CloudWatch alarms, tracing |

---

## Constraints Every Agent Must Follow

- No hardcoded secrets. No credentials in source files.
- No ECS, ALB, ECR, or Secrets Manager. Backend deploys via SAM to Lambda only.
- No Alembic. Schema managed via versioned SQL files in `backend/migrations/`.
- `DB_SCHEMA_INIT_ON_STARTUP=true` for local dev only. Always `false` in production.
- CORS handled in FastAPI only — never at API Gateway.
- JWT token stored in React Context, never `localStorage`.
- Every protected route enforces both authentication and the correct role.
- Every database query scopes to `tenant_id`.
- PHI must never appear in logs, error messages, or cache keys.

---

## Local Development Quick-Start (after building from specs)

```bash
# Backend
cd healthcare_saas_app/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with local DB credentials
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (separate terminal)
cd healthcare_saas_app/frontend
npm install
echo "VITE_API_BASE_URL=http://127.0.0.1:8000" > .env.local
npm run dev
```

Frontend: http://127.0.0.1:5173 | Backend: http://127.0.0.1:8000 | Swagger: http://127.0.0.1:8000/docs
