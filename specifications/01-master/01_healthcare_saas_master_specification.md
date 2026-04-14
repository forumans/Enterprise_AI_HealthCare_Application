# Master Prompt: Healthcare SaaS Application Generator

Use this prompt as the entrypoint in Claude Code or another code generation agent. It orchestrates all other prompts in `specifications/` and should be the first thing you run to build the full application from scratch.

---

## Prompt

You are a principal software architect and implementation lead. Build a production-ready, multi-tenant Healthcare SaaS platform following this specification set exactly.

### Hard Requirements

1. Lay out code under `healthcare_saas_app/` with these sub-projects:
   - `frontend/` — React + TypeScript + Vite SPA
   - `backend/` — FastAPI + Python 3.12 + SQLAlchemy 2.0 async + asyncpg
   - `docs/` — project documentation (architecture, API reference, local dev guide, deployment guide)
2. Keep backend stateless and 12-factor compatible. No file system writes except ephemeral `/tmp`.
3. Use PostgreSQL (AWS RDS target), JWT HS256 auth, RBAC (PATIENT / DOCTOR / ADMIN), per-tenant data isolation, audit logging.
4. Follow HIPAA-oriented engineering controls: least privilege IAM, PHI-safe logging, encryption in transit and at rest, no secrets in code or version control.
5. Deploy backend as an **AWS Lambda function** (python3.12) exposed via **API Gateway HTTP API**, defined with an **AWS SAM template** at `backend/template.yaml`.
6. Deploy frontend as a static site on **S3**, served via **CloudFront**. CloudFront routes `/api/*` to API Gateway; all other paths serve from S3.

### Reference Prompts (execute in this order)

| Step | Specification file | Domain |
|------|-------------------|--------|
| 1 | `specifications/03-database/01_database_architecture_design.md` | Schema design |
| 2 | `specifications/03-database/02_database_migrations_seeding.md` | Schema delivery and seeds |
| 3 | `specifications/04-backend/01_authentication_authorization.md` | JWT + RBAC |
| 4 | `specifications/04-backend/02_rate_limiting_caching.md` | Resilience |
| 5 | `specifications/04-backend/03_api_gateway_middleware.md` | Middleware stack |
| 6 | `specifications/05-frontend/01_frontend_architecture.md` | React SPA structure |
| 7 | `specifications/05-frontend/02_react_components_ui_library.md` | Component system |
| 8 | `specifications/05-frontend/03_state_management_data_flow.md` | State + data flow |
| 9 | `specifications/05-frontend/04_api_integration_data_fetching.md` | API client |
| 10 | `specifications/06-security/01_security_architecture_compliance.md` | Security controls |
| 11 | `specifications/06-security/02_encryption_data_protection.md` | Encryption |
| 12 | `specifications/06-security/03_access_control_permissions.md` | Permission matrix |
| 13 | `specifications/07-observability/01_logging_monitoring_strategy.md` | Structured logging |
| 14 | `specifications/07-observability/02_metrics_alerting_system.md` | Metrics + alerts |
| 15 | `specifications/07-observability/03_distributed_tracing.md` | Tracing |
| 16 | `specifications/08-testing/01_testing_strategy_master.md` | Test pyramid |
| 17 | `specifications/08-testing/02_backend_frontend_integration_prompt.md` | Integration tests |
| 18 | `specifications/08-testing/03_e2e_perf_security_prompt.md` | E2E + perf + security |
| 19 | `specifications/09-deployment/01_deployment_architecture_prompt.md` | AWS SAM deployment |
| 20 | `specifications/09-deployment/02_cicd_release_prompt.md` | CI/CD pipelines |

### Target Architecture

```
Browser
  └── CloudFront (CDN)
        ├── /api/* → API Gateway HTTP API
        │              └── Lambda (FastAPI + Mangum, python3.12)
        │                    └── RDS PostgreSQL (private VPC)
        │                    └── S3 (patient document storage)
        └── /* default → S3 (React static assets)
```

### Infrastructure Stack

| Component | Technology |
|-----------|-----------|
| Backend runtime | AWS Lambda, python3.12, 512 MB, 30s timeout |
| API edge | API Gateway HTTP API |
| IaC | AWS SAM (`backend/template.yaml`) |
| Frontend hosting | S3 + CloudFront |
| Database | RDS PostgreSQL (private subnets) |
| Document storage | S3 (private bucket, presigned URL access) |
| Secrets | Lambda environment variables via SAM parameter overrides (`NoEcho`) |
| Logs | CloudWatch Logs (`/aws/lambda/<function-name>`) |
| CI/CD | GitHub Actions |

### Backend Domain Scope

- Auth: register, login, forgot-password, reset-password
- Users + Tenants: multi-tenant isolation, soft-delete, admin management
- Doctors: profile, availability slots
- Patients: profile, medical history, prescriptions, documents
- Appointments: book, confirm, cancel, complete, status lifecycle
- Medical Records + Prescriptions: doctor-created after appointment
- Audit Logs: immutable write trail for all mutations

### Frontend Domain Scope

- Role-based dashboards: PATIENT, DOCTOR, ADMIN views
- Patient flows: register, book appointment, view history, upload documents
- Doctor flows: manage availability, view appointments, create records/prescriptions
- Admin flows: user management, appointment overview, system reports

### Non-Functional Targets

- API p95 latency < 500 ms for common endpoints (login, appointment list, profile)
- Lambda cold start mitigated by `pool_size=1, max_overflow=0` on DB engine
- Tenant data isolation enforced at middleware layer and in every query
- Idempotent, migration-first schema delivery
- Test pyramid with enforced CI quality gates (lint, type-check, unit, integration, E2E)

### Output Contract

1. Show a file-by-file plan before major edits.
2. Implement incrementally; run targeted checks after each component.
3. At completion, provide:
   - final directory tree for `frontend/` and `backend/`,
   - commands to run locally (Uvicorn + Vite),
   - SAM deployment commands,
   - known gaps and next actions.

### Quality Bar

- Production-safe defaults everywhere.
- No hardcoded secrets or credentials.
- No placeholder TODO-only architecture — every section must be runnable or explicitly scaffolded.
- Every protected route must enforce both authentication and the correct role.
- Every database query must scope to `tenant_id`.
