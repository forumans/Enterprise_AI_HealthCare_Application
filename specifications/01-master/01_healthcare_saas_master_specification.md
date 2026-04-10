# Master Prompt: Healthcare SaaS Multi-Project Generator

Use this prompt as the entrypoint in Claude Code or OpenAI Codex. It orchestrates all other prompts in `docs/specifications`.

## Prompt
You are a principal software architect and implementation lead. Build a production-ready, multi-tenant Healthcare SaaS platform from this repository using a **multi-project** layout.

### Hard Requirements
1. Create and maintain separate projects:
   - `frontend/` (React + TypeScript + Vite)
   - `backend/` (FastAPI + Python + SQLAlchemy + Alembic)
   - `testing/` (unit/integration/e2e/perf/security test suites and runners)
   - `infrastructure/` (Terraform and cloud resource definitions)
   - `deployment/` (CI/CD workflows, scripts, runbooks, release automation)
2. Do not collapse these into one monolith. Keep boundaries explicit.
3. Keep backend stateless and 12-factor compatible.
4. Use PostgreSQL (AWS RDS target), JWT auth, RBAC, tenant isolation, audit logging.
5. Follow HIPAA-oriented engineering controls (least privilege, PHI-safe logging, encryption in transit/at rest).

### Reference Prompts (execute in this order)
1. `docs/specifications/02-database/01_database_architecture_design.md`
2. `docs/specifications/02-database/02_database_migrations_seeding.md`
3. `docs/specifications/03-backend/01_authentication_authorization.md`
4. `docs/specifications/03-backend/03_api_gateway_middleware.md`
5. `docs/specifications/06-frontend/01_frontend_architecture.md`
6. `docs/specifications/06-frontend/04_api_integration_data_fetching.md`
7. `docs/specifications/04-security/01_security_architecture_compliance.md`
8. `docs/specifications/05-observability/01_logging_monitoring_strategy.md`
9. `docs/specifications/07-testing/01_testing_strategy_master.md`
10. `docs/specifications/08-deployment/01_deployment_architecture_prompt.md`

### Required Architecture
```text
healthcare_saas_app/
  frontend/
  backend/
  testing/
  infrastructure/
  deployment/
  docs/specifications/
```

### Scope
- Backend domains: auth, users, tenants, patients, doctors, appointments, medical records, prescriptions, audit logs.
- Frontend domains: role-based dashboards and workflows for patient, doctor, admin.
- Infrastructure: VPC, ALB, ECS Fargate service(s), ECR, RDS PostgreSQL, S3 + CloudFront, CloudWatch, Secrets Manager.
- Deployment: GitHub Actions with separate backend/frontend pipelines and environment promotion.

### Non-Functional Targets
- API p95 latency under 500ms for common endpoints.
- Health/readiness/liveness endpoints with correct HTTP semantics.
- Tenant data isolation by policy and code.
- Idempotent, migration-first deploy flow.
- Test pyramid with enforced CI quality gates.

### Output Contract
1. Show a file-by-file plan before major edits.
2. Implement incrementally and run targeted checks after each component.
3. At the end, provide:
   - final tree for `frontend`, `backend`, `testing`, `infrastructure`, `deployment`,
   - commands to run locally,
   - CI/CD pipeline summary,
   - known gaps and next actions.

### Quality Bar
- Production-safe defaults.
- No hardcoded secrets.
- No placeholder TODO-only architecture.
- Every generated area must be runnable or clearly scaffolded with executable next steps.
