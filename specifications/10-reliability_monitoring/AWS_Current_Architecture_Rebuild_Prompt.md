# Prompt: Recreate the Current AWS Architecture (Healthcare SaaS)

## How to use this document
Copy the **Master Prompt** section into a code generation agent (for example Claude) and ask it to generate:
1) reproducible infrastructure artifacts, 2) deployment commands, and 3) a verification runbook.

This prompt is grounded in the current repository configuration and recent production fixes.

---

## Master Prompt (copy/paste)

You are a senior cloud/platform engineer. Recreate the **current** AWS architecture and deployment setup for this Healthcare SaaS app exactly, with minimal cost and no new paid services unless explicitly marked optional.

### 1) Objectives
- Recreate the current architecture used by this repository:
  - Frontend: React/Vite static site on S3 behind CloudFront
  - Backend: FastAPI on ECS Fargate behind an internet-facing ALB
  - Database: PostgreSQL on RDS
  - Secrets: AWS Secrets Manager
  - Logs: CloudWatch Logs
  - CI/CD: GitHub Actions for backend and frontend
- Preserve current routing strategy that avoids CloudFront behavior-limit issues:
  - Frontend calls CloudFront with API base URL ending in `/api`
  - CloudFront forwards `/api/*` to backend ALB origin
  - Default `*` behavior serves static frontend from S3

### 2) Hard Constraints
- Do not introduce new required paid services.
- Keep us-east-1 as region.
- Keep ECS/Fargate + ALB + RDS + S3 + CloudFront + Secrets Manager + CloudWatch.
- Preserve compatibility with existing repo workflows and file structure.
- Do not hardcode secret values in code or workflows.

### 3) Repository Ground Truth (must align with these files)
- Backend deploy workflow: `healthcare_saas_app/.github/workflows/backend-deploy.yml`
- Frontend deploy workflow: `healthcare_saas_app/.github/workflows/frontend-deploy.yml`
- ECS task definition: `healthcare_saas_app/infrastructure/ecs/task-definition.json`
- ALB template: `healthcare_saas_app/infrastructure/alb/application-load-balancer.json`
- Security groups: `healthcare_saas_app/infrastructure/security/security-groups.json`
- Backend app entrypoint/middleware routing: `healthcare_saas_app/backend/app/main.py`
- Frontend API base behavior: `healthcare_saas_app/frontend/src/api.ts`

### 4) Current Logical Architecture
- CloudFront distribution in front of frontend and API.
- S3 bucket hosts built frontend assets (default behavior).
- CloudFront behavior `/api/*` routes to backend ALB origin.
- ALB forwards to ECS service `healthcare-backend-service` in cluster `healthcare-cluster`.
- ECS task runs container `healthcare-backend` on port 8000.
- Backend reads runtime secrets from Secrets Manager:
  - `DATABASE_URL`
  - `JWT_SECRET`
  - `CORS_ORIGINS`
- Backend health endpoints used by ECS/ALB:
  - `/api/health`
  - `/api/health/ready`
  - `/api/health/live`
- RDS PostgreSQL is reachable from ECS via security group rules.

### 5) Required Resource/Name Baseline
Use these as defaults unless parameterized:
- Region: `us-east-1`
- ECR repo: `healthcare-backend`
- ECS cluster: `healthcare-cluster`
- ECS service: `healthcare-backend-service`
- ECS task family: `healthcare-backend`
- ALB name: `healthcare-backend-alb`
- CloudWatch log group: `/ecs/healthcare-backend`
- Secrets (names):
  - `healthcare-db-url`
  - `healthcare-jwt-secret`
  - `healthcare-cors-origins`

### 6) Critical Implementation Details
- Backend must expose business routes both unprefixed and prefixed with `/api` to preserve backward compatibility while enabling CloudFront simplification.
- Frontend `VITE_API_BASE_URL` must be `https://<cloudfront-domain>/api`.
- CloudFront must have exactly:
  - `/api/*` => backend ALB origin, `Managed-CachingDisabled`, `Managed-AllViewer`
  - `*` default => S3 frontend origin
- Ensure public auth endpoints under `/api` are excluded from auth middleware checks (`/api/auth/login`, `/api/auth/register`, `/api/auth/forgot-password`, `/api/auth/reset-password`, etc.).

### 7) Known Pitfalls (must include prevention)
- **Mixed content**: HTTPS frontend calling HTTP ALB directly. Fix by calling CloudFront HTTPS `/api` only.
- **Secrets format bug**: `DATABASE_URL` secret must be plaintext URL string, not JSON object string.
- **CloudFront stale cache**: API paths can return `<!doctype html>` from S3 if cached. Use invalidation (`/*`) after behavior or routing changes.
- **Behavior limits**: Avoid per-endpoint CloudFront behaviors; consolidate API under `/api/*`.
- **Auth 401 regression**: If `/api/auth/login` returns missing auth header, middleware exclusions for `/api` public routes are incomplete.

### 8) Networking/Security Expectations
- ALB SG allows inbound 80/443 from internet.
- ECS SG allows inbound 8000 from ALB SG only.
- RDS SG allows inbound 5432 from ECS SG only.
- ECS tasks use `awsvpc` network mode and Fargate launch type.
- Logs routed to CloudWatch (`awslogs` driver).

### 9) CI/CD Behavior to Recreate
- Backend workflow:
  - test backend
  - build/push image to ECR (sha + latest)
  - register task definition
  - force new ECS deployment
  - wait for service stability
- Frontend workflow:
  - test/type-check frontend
  - build Vite app
  - sync `dist/` to S3
  - set cache headers
  - invalidate CloudFront

### 10) Deliverables Required from You (the agent)
Produce all of the following:
1. **Architecture diagram (ASCII or Mermaid)** matching current flow.
2. **IaC-style artifacts** (or AWS CLI scripts) for:
   - ALB, target group, listeners
   - ECS task/service
   - Security groups
   - CloudFront behavior setup (`/api/*` + default)
3. **Secrets setup instructions** with explicit plaintext format examples.
4. **GitHub Actions variable/secret matrix** (required values, where used).
5. **Deployment runbook** (ordered, copy-paste commands).
6. **Smoke test checklist** for Patient, Doctor, Admin flows.
7. **Rollback plan** for backend and frontend.

### 11) Validation Criteria
Your output is only acceptable if all checks pass:
- `POST /api/auth/login` succeeds without requiring prior Authorization header.
- Frontend login works via CloudFront URL.
- Patient dashboard data loads.
- Doctors list loads in appointment scheduling.
- Doctor search pages return expected data.
- Admin routes function.
- No API request returns frontend HTML unexpectedly.

### 12) Output Format
Return these sections in order:
1. Assumptions & parameters table
2. Target AWS architecture
3. Infrastructure provisioning steps
4. CI/CD setup
5. Runtime configuration (env + secrets)
6. CloudFront routing and cache strategy
7. Verification and troubleshooting
8. Rollback

---

## Maintainer Notes
This specification reflects the current working architecture after production fixes related to CloudFront routing limits and `/api` proxy consolidation.
