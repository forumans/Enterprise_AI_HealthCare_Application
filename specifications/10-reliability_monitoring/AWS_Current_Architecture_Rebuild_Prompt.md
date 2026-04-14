# Prompt: Recreate the Current AWS Architecture (Healthcare SaaS)

## How to use this document

Copy the **Master Prompt** section into a code generation agent (Claude Code, Codex, etc.) and ask it to generate:
1. Reproducible infrastructure artifacts
2. Deployment commands
3. A verification runbook

This prompt reflects the current production architecture after migrating from ECS Fargate + ALB to Lambda + API Gateway.

---

## Master Prompt (copy/paste)

You are a senior cloud/platform engineer. Recreate the **current** AWS architecture and deployment setup for this Healthcare SaaS application exactly, using AWS SAM for backend IaC and GitHub Actions for CI/CD.

### 1) Objectives

Recreate the current architecture:
- Frontend: React/Vite static site built to `dist/`, hosted on S3, served via CloudFront
- Backend: FastAPI wrapped with Mangum ASGI adapter, deployed as AWS Lambda (python3.12, 512 MB, 30s timeout)
- API edge: API Gateway HTTP API (cheaper than REST API)
- Routing: CloudFront proxies `/api/*` to API Gateway; default behavior serves S3 frontend
- Database: PostgreSQL on RDS in private VPC subnets
- Document storage: S3 private bucket; presigned URLs for downloads
- Secrets: Lambda environment variables injected at deploy time via SAM `--parameter-overrides`
- Logs: CloudWatch Logs at `/aws/lambda/<function-name>`

### 2) Hard Constraints

- Backend is deployed via `sam build && sam deploy` — no Docker image push, no ECR.
- No ECS, no ALB, no Secrets Manager (secrets are Lambda env vars).
- Keep `us-east-1` as the primary region.
- No new required paid services.
- No hardcoded secrets in code, config files, or workflows.
- `DatabaseUrl` and `JwtSecret` SAM parameters must be `NoEcho: true` — never persisted to samconfig.toml.

### 3) Repository Ground Truth

All infrastructure definitions are in these files — align with them exactly:

| Purpose | File |
|---------|------|
| SAM template (Lambda + API Gateway + IAM) | `healthcare_saas_app/backend/template.yaml` |
| FastAPI app + Mangum handler | `healthcare_saas_app/backend/app/main.py` |
| DB engine (pool_size=1) | `healthcare_saas_app/backend/app/core/database.py` |
| S3 upload utility + presigned URLs | `healthcare_saas_app/backend/app/core/storage.py` |
| App config (env vars) | `healthcare_saas_app/backend/app/core/config.py` |
| Frontend API client | `healthcare_saas_app/frontend/src/api.ts` |
| SQL schema migrations | `healthcare_saas_app/backend/migrations/` |

### 4) Current Logical Architecture

```
Browser
  └── CloudFront (CDN)
        ├── /api/*  → API Gateway HTTP API (custom origin)
        │                └── Lambda function (FastAPI + Mangum)
        │                      ├── RDS PostgreSQL (VPC private subnets)
        │                      └── S3 (patient document storage)
        └── /* (default) → S3 bucket (static React assets)
```

### 5) CloudFront Routing Details

- Default behavior (`*`): S3 origin, standard caching, SPA fallback (403/404 → `/index.html`)
- API behavior (`/api/*`):
  - Origin: `<api-id>.execute-api.us-east-1.amazonaws.com`
  - Protocol: HTTPS only
  - Cache policy: `CachingDisabled` (managed policy ID: `4135ea2d-6df8-44a3-9df3-4b5a84be39ad`)
  - Origin request policy: `AllViewerExceptHostHeader` (managed policy ID: `b689b0a8-53d0-40ab-baf2-68738e2966ac`)

**Why `AllViewerExceptHostHeader` is mandatory:** API Gateway rejects requests with the viewer's `Host` header (the CloudFront domain). Without this policy, CloudFront forwards the wrong `Host`, API Gateway returns 403, and CloudFront's SPA fallback serves `index.html` for every API request.

### 6) SAM Template Structure

```yaml
Transform: AWS::Serverless-2016-10-31

Parameters:
  AppEnv:                { Type: String, Default: production }
  DatabaseUrl:           { Type: String, NoEcho: true }
  JwtSecret:             { Type: String, NoEcho: true }
  CorsOrigins:           { Type: String }
  DocumentsBucketName:   { Type: String }
  LambdaSecurityGroupId: { Type: String }
  PrivateSubnetIds:      { Type: String }

Globals:
  Function:
    Runtime: python3.12
    Handler: app.main.handler
    Timeout: 30
    MemorySize: 512
    Environment:
      Variables:
        APP_ENV: !Ref AppEnv
        DATABASE_URL: !Ref DatabaseUrl
        JWT_SECRET: !Ref JwtSecret
        CORS_ORIGINS: !Ref CorsOrigins
        S3_BUCKET_NAME: !Ref DocumentsBucketName
        DB_SCHEMA_INIT_ON_STARTUP: "false"

Resources:
  BackendFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      VpcConfig:
        SecurityGroupIds: [!Ref LambdaSecurityGroupId]
        SubnetIds: !Split [",", !Ref PrivateSubnetIds]
      Policies:
        - S3CrudPolicy: { BucketName: !Ref DocumentsBucketName }
      Events:
        ApiProxy:
          Type: HttpApi
          Properties:
            Path: /{proxy+}
            Method: ANY
```

Do NOT add a `RoleName` to the Lambda execution role — named roles require `CAPABILITY_NAMED_IAM` and will break standard `sam deploy`.

### 7) Lambda Entry Point

```python
# backend/app/main.py (bottom of file)
from mangum import Mangum
handler = Mangum(app, lifespan="off")
```

### 8) Database Connection Pooling

Lambda instances scale horizontally. Each instance holds exactly one DB connection:

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=1,
    max_overflow=0,
    pool_pre_ping=True,
)
```

### 9) Security Architecture

- Lambda VPC placement: private subnets, security group allows outbound to RDS on port 5432
- RDS security group: inbound 5432 from Lambda security group only
- S3 documents bucket: private; Lambda IAM role has `s3:PutObject` + `s3:GetObject`
- CORS: handled entirely in FastAPI `CORSMiddleware` — API Gateway does NOT add CORS headers
- JWT: HS256, validated in `TenantContextMiddleware` on every protected request
- Public paths bypass middleware: `/api/auth/*`, `/api/health*`, `/api/doctors`, `/api/doctors/register`, `/api/admin/register`, `/api/doctor/availability/*`

### 10) CloudWatch Log Group

```
/aws/lambda/healthcare-backend-backend
```

Tail logs during troubleshooting:
```bash
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/healthcare-backend-backend \
  --follow --region us-east-1
```

### 11) Known Pitfalls (must include prevention)

| Pitfall | Symptom | Prevention |
|---------|---------|-----------|
| Wrong CloudFront origin request policy | `/api/*` returns HTML | Use `AllViewerExceptHostHeader` on `/api/*` behavior |
| NoEcho params in samconfig.toml | Params missing on next deploy | Always pass via `--parameter-overrides` |
| Windows PowerShell multi-line override | Parse error on deploy | Put all overrides on one line |
| Named IAM role in SAM template | `CAPABILITY_NAMED_IAM` error | Remove `RoleName` from IAM resource |
| Stack in ROLLBACK_COMPLETE | Can't deploy | Delete stack and redeploy from scratch |
| Lambda can't reach RDS | DB disconnected | Check SG inbound/outbound rules on port 5432 |
| CORS blocked on API call | Browser CORS error | `CORS_ORIGINS` env var must exactly match CloudFront domain |
| Duplicate CORS headers | API returns CORS header twice | Never configure CORS at API Gateway — FastAPI only |

### 12) CI/CD Behavior to Recreate

**Backend pipeline** (on push to `main`, path filter `healthcare_saas_app/backend/**`):
1. Lint (`ruff check`) + type check (`mypy`)
2. Unit tests (`pytest`) with PostgreSQL service container
3. `sam build` + `sam validate`
4. Apply SQL migrations via `psql` (before code deploy)
5. `sam deploy --no-confirm-changeset --parameter-overrides ...` (DatabaseUrl + JwtSecret from GitHub secrets)

**Frontend pipeline** (on push to `main`, path filter `healthcare_saas_app/frontend/**`):
1. Lint + type check (`npx tsc --noEmit`)
2. Unit tests (`npm run test`)
3. `npm run build`
4. `aws s3 sync dist/ s3://<bucket> --delete`
5. `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"`

### 13) Deliverables Required from You (the agent)

Produce all of the following:

1. **Architecture diagram (Mermaid)** matching current CloudFront → API Gateway → Lambda → RDS flow
2. **SAM template** (`backend/template.yaml`) with all parameters, globals, function, and IAM role
3. **GitHub Actions workflows** for backend (SAM) and frontend (S3) deployments
4. **GitHub Actions secrets matrix** — every secret name, where it's used, format
5. **Deployment runbook** — ordered copy-paste commands for first deploy and subsequent deploys
6. **Smoke test checklist** — health check, login (PATIENT/DOCTOR/ADMIN), appointment booking
7. **Rollback plan** — backend (CloudFormation rollback) and frontend (S3 re-sync)
8. **CloudFront configuration** — both behaviors with exact policy names/IDs

### 14) Validation Criteria

Output is only acceptable if all checks pass:
- `POST /api/auth/login` succeeds without requiring prior Authorization header
- `GET /api/health` returns `{"status":"healthy","database":"connected"}`
- Frontend loads at CloudFront domain
- Patient dashboard data loads after login
- Doctor availability slots load in appointment scheduling
- No API request unexpectedly returns HTML
- Admin routes return data for ADMIN-role tokens; return 403 for PATIENT/DOCTOR tokens

### 15) Output Format

Return sections in this order:
1. Architecture diagram
2. SAM template
3. Lambda entry point and DB pooling
4. GitHub Actions workflows
5. GitHub Actions secrets matrix
6. CloudFront routing configuration
7. Deployment runbook (first deploy + subsequent)
8. Smoke test checklist
9. Rollback plan
10. Known pitfalls and mitigations
