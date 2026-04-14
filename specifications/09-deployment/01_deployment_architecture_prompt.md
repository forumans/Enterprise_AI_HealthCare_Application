# Prompt: Deployment Architecture (Lambda + API Gateway + SAM)

## Prompt

Design and implement production deployment for this Healthcare SaaS application. The backend runs as an AWS Lambda function behind API Gateway HTTP API, defined with AWS SAM. The frontend is a React static site served from S3 via CloudFront.

---

### Target Platform

| Component | Technology |
|-----------|-----------|
| Backend runtime | AWS Lambda (python3.12, 512 MB memory, 30s timeout) |
| API edge | API Gateway HTTP API (not REST API — HTTP API is cheaper) |
| IaC | AWS SAM template (`backend/template.yaml`) |
| Frontend hosting | S3 static site + CloudFront distribution |
| Database | RDS PostgreSQL in private VPC subnets |
| Document storage | S3 private bucket (patient file uploads) |
| Secrets delivery | Lambda environment variables via SAM `--parameter-overrides` |
| Logs | CloudWatch Logs — `/aws/lambda/<function-name>` |
| ASGI adapter | Mangum — wraps FastAPI for Lambda invocation |

---

### CloudFront Routing Strategy

CloudFront must have exactly two cache behaviors:

| Behavior | Origin | Cache Policy | Origin Request Policy |
|----------|--------|-------------|----------------------|
| `/api/*` | API Gateway HTTP API custom origin | `CachingDisabled` | `AllViewerExceptHostHeader` |
| `*` (default) | S3 frontend bucket | Standard static caching | — |

**Critical:** The `/api/*` behavior must use `AllViewerExceptHostHeader` origin request policy. Without it, CloudFront forwards the viewer's `Host` header (the CloudFront domain) to API Gateway, which rejects it with 403. CloudFront's custom error rules then return `index.html` instead of JSON.

CloudFront custom error rule: `403 → /index.html` and `404 → /index.html` (SPA fallback for React Router).

---

### SAM Template Requirements (`backend/template.yaml`)

```yaml
Transform: AWS::Serverless-2016-10-31

Parameters:
  AppEnv:           { Type: String, Default: production }
  DatabaseUrl:      { Type: String, NoEcho: true }
  JwtSecret:        { Type: String, NoEcho: true }
  CorsOrigins:      { Type: String }
  DocumentsBucketName: { Type: String }
  LambdaSecurityGroupId: { Type: String }
  PrivateSubnetIds: { Type: String }

Globals:
  Function:
    Runtime: python3.12
    Handler: app.main.handler      # Mangum handler in main.py
    Timeout: 30
    MemorySize: 512
    Environment:
      Variables:
        APP_ENV: !Ref AppEnv
        DATABASE_URL: !Ref DatabaseUrl
        JWT_SECRET: !Ref JwtSecret
        CORS_ORIGINS: !Ref CorsOrigins
        S3_BUCKET_NAME: !Ref DocumentsBucketName
        DB_SCHEMA_INIT_ON_STARTUP: false

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

**Important:** Do not add a `RoleName` to the IAM role — it triggers `CAPABILITY_NAMED_IAM` which requires a different SAM flag and will cause deployment failures.

---

### Lambda Entry Point (`backend/app/main.py`)

The Mangum adapter must be instantiated at module level so it is reused across warm invocations:

```python
from mangum import Mangum

app = FastAPI(...)
# ... middleware and router registration ...

handler = Mangum(app, lifespan="off")
```

`lifespan="off"` disables FastAPI lifespan events that don't run cleanly inside Lambda.

---

### Database Connection Pooling for Lambda

Lambda scales horizontally by spawning new execution environments. Each environment must hold only one DB connection to avoid exhausting RDS connection limits:

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=1,
    max_overflow=0,
    pool_pre_ping=True,
)
```

`pool_pre_ping=True` detects stale connections after Lambda execution environment hibernation.

---

### AWS Prerequisites (must exist before `sam deploy`)

| Resource | Notes |
|----------|-------|
| VPC + private subnets | Lambda and RDS run in private subnets |
| RDS PostgreSQL instance | Must be reachable from Lambda security group on port 5432 |
| Lambda security group | Must allow outbound to RDS security group |
| S3 bucket — documents | Private; Lambda IAM role gets `s3:PutObject` + `s3:GetObject` |
| S3 bucket — frontend | Public static hosting or OAC-restricted for CloudFront |
| CloudFront distribution | Serves frontend + proxies `/api/*` to API Gateway |

---

### Deployment Flow

#### First deploy
```bash
cd healthcare_saas_app/backend
sam build
sam deploy --guided
# Enter all prompted parameters; save to samconfig.toml
# DatabaseUrl and JwtSecret are NoEcho — they are NOT saved to samconfig.toml
```

#### Subsequent deploys
```bash
sam build && sam deploy --parameter-overrides \
  "DatabaseUrl=<value>" \
  "JwtSecret=<value>" \
  "AppEnv=production" \
  "CorsOrigins=https://<cloudfront-domain>.cloudfront.net" \
  "DocumentsBucketName=<bucket>" \
  "LambdaSecurityGroupId=sg-<id>" \
  "PrivateSubnetIds=subnet-<a>,subnet-<b>"
```

On Windows PowerShell all `--parameter-overrides` must be on a single line.

#### Schema migrations
```bash
# Apply before deploying Lambda (schema must be current before code)
psql -h <rds-endpoint> -U <user> -d <db> -f migrations/001_initial_schema.sql
```

---

### Environment Separation

| Environment | Stack name | SAM config env | `AppEnv` |
|-------------|-----------|----------------|---------|
| Development | `healthcare-backend-dev` | `dev` | `dev` |
| Staging | `healthcare-backend-staging` | `staging` | `staging` |
| Production | `healthcare-backend` | `default` | `production` |

---

### Frontend Deployment

```bash
cd healthcare_saas_app/frontend
npm install
npm run build        # outputs to dist/

# Upload to S3
aws s3 sync dist/ s3://<frontend-bucket> --delete --region us-east-1

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id <DIST_ID> \
  --paths "/*"
```

The frontend uses relative paths for API calls in production — no `VITE_API_BASE_URL` needed because CloudFront handles routing. Set `VITE_API_BASE_URL` only for local development.

---

### Rollback

**Backend:** SAM deploys via CloudFormation changesets. Failed deployments auto-rollback. Manual rollback:
```bash
aws cloudformation cancel-update-stack --stack-name healthcare-backend
```

**Frontend:** Re-sync the previous `dist/` build to S3 and invalidate CloudFront.

---

### Smoke Tests (post-deploy)

```bash
BASE=https://<cloudfront-domain>.cloudfront.net

# 1. Health check
curl $BASE/api/health
# Expected: {"status":"healthy","database":"connected"}

# 2. Login
curl -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"<test-user>","password":"<password>"}'
# Expected: {"access_token":"...","role":"..."}

# 3. Doctors list (public)
curl $BASE/api/doctors
# Expected: JSON array of doctors
```

---

### Deliverables

- `backend/template.yaml` — SAM template defining Lambda + API Gateway + IAM
- `backend/app/main.py` — Mangum handler registered as `handler`
- `backend/app/core/database.py` — engine with `pool_size=1, max_overflow=0`
- `backend/app/core/storage.py` — S3 upload + presigned URL utility
- `docs/deployment.md` — narrative deployment guide
- `docs/local-development.md` — local Uvicorn + Vite setup

### Acceptance Criteria

- `sam build && sam deploy` succeeds from a clean checkout.
- `GET /api/health` returns `{"status":"healthy","database":"connected"}` after deploy.
- `POST /api/auth/login` returns a valid JWT.
- Frontend login works via the CloudFront URL.
- No API request returns HTML unexpectedly (would indicate routing misconfiguration).
- Backend and frontend can be deployed independently.
