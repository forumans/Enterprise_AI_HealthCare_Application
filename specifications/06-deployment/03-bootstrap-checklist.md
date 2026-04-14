# Prompt: AWS Bootstrap Checklist (First Deploy)

## Prompt

Provide a step-by-step checklist to stand up this Healthcare SaaS application on AWS from scratch. A contributor with AWS CLI access and the repo cloned should be able to complete a first deploy in approximately 20 minutes.

---

## Prerequisites

Validate all before starting:

```bash
# AWS CLI configured
aws sts get-caller-identity

# SAM CLI installed
sam --version   # requires >= 1.90

# Python 3.12 available
python3.12 --version

# Node.js 18+
node --version

# PostgreSQL client (for migrations)
psql --version
```

Set your region:
```bash
export AWS_DEFAULT_REGION=us-east-1
```

---

## Step 1: Provision AWS Prerequisites

These resources must exist before SAM deploy. Create them in the AWS Console or via CLI.

### 1a. VPC + Private Subnets
Lambda and RDS must run in private subnets. Note the:
- VPC ID
- At least 2 private subnet IDs (for RDS multi-AZ)
- Security group ID for Lambda (allow outbound to RDS on 5432)
- Security group ID for RDS (allow inbound from Lambda SG on 5432)

### 1b. RDS PostgreSQL Instance
```bash
# Minimum: db.t3.micro, PostgreSQL 15, private subnets
# Note the endpoint, port, username, password, and database name
```

### 1c. S3 Bucket — Patient Documents (private)
```bash
aws s3api create-bucket \
  --bucket healthcare-patient-documents \
  --region us-east-1

aws s3api put-public-access-block \
  --bucket healthcare-patient-documents \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### 1d. S3 Bucket — Frontend Static Assets
```bash
aws s3api create-bucket \
  --bucket healthcare-frontend-assets \
  --region us-east-1
```

---

## Step 2: Apply Database Schema

```bash
psql -h <rds-endpoint> -U <username> -d <dbname> \
  -f healthcare_saas_app/backend/migrations/001_initial_schema.sql
```

Verify:
```bash
psql -h <rds-endpoint> -U <username> -d <dbname> -c "\dt"
# Should show: tenants, users, doctors, patients, admins, appointments, etc.
```

---

## Step 3: Deploy Backend (SAM)

```bash
cd healthcare_saas_app/backend
sam build
sam deploy --guided
```

When prompted, enter:

| Prompt | Value |
|--------|-------|
| Stack Name | `healthcare-backend` |
| AWS Region | `us-east-1` |
| AppEnv | `production` |
| DatabaseUrl | `postgresql+asyncpg://user:pass@<rds-endpoint>:5432/<dbname>` |
| JwtSecret | A random string ≥ 32 characters |
| CorsOrigins | `https://<your-cloudfront-domain>.cloudfront.net` (update after Step 5) |
| DocumentsBucketName | `healthcare-patient-documents` |
| LambdaSecurityGroupId | `sg-xxxxxxxx` |
| PrivateSubnetIds | `subnet-aaa,subnet-bbb` |
| Allow SAM CLI IAM role creation | `Y` |
| Disable rollback | `N` |
| BackendFunction has no authentication | `Y` (FastAPI handles auth) |
| Save arguments to samconfig.toml | `Y` |

> **Note:** `DatabaseUrl` and `JwtSecret` are `NoEcho` — they will NOT be saved to `samconfig.toml`. You must pass them via `--parameter-overrides` on every subsequent deploy.

After deploy, note the output:
```
ApiUrl: https://<api-id>.execute-api.us-east-1.amazonaws.com
```

---

## Step 4: Smoke Test the Backend

```bash
API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com

# Health check
curl $API_URL/api/health
# Expected: {"status":"healthy","database":"connected"}

# Public doctors endpoint
curl $API_URL/api/doctors
# Expected: [] or list of doctors
```

If health returns `{"database":"disconnected"}` — check Lambda VPC config, security group outbound rules, and RDS security group inbound rules.

---

## Step 5: Deploy Frontend

```bash
cd healthcare_saas_app/frontend
npm install
npm run build

aws s3 sync dist/ s3://healthcare-frontend-assets --delete --region us-east-1
```

---

## Step 6: Set Up CloudFront

### 6a. Create CloudFront Distribution
In the AWS Console, create a new distribution:
- Origin 1: S3 bucket (`healthcare-frontend-assets`) — use OAC or public access
- Default cache behavior: serves S3 origin; 403/404 error pages → `/index.html`

### 6b. Add `/api/*` Cache Behavior
- Path pattern: `/api/*`
- Origin: Custom origin pointing to `<api-id>.execute-api.us-east-1.amazonaws.com`
- Protocol: HTTPS only
- Cache policy: `CachingDisabled`
- Origin request policy: **`AllViewerExceptHostHeader`** (ID: `b689b0a8-53d0-40ab-baf2-68738e2966ac`)

**Critical:** Without `AllViewerExceptHostHeader`, CloudFront forwards the viewer's `Host` header to API Gateway, which returns 403. The 403 error rule then returns `index.html` — API calls silently return HTML instead of JSON.

### 6c. Note the CloudFront Domain
```
https://xxxxxxxxxxxx.cloudfront.net
```

---

## Step 7: Update CORS Origins

Redeploy backend with the correct CloudFront domain:

```bash
cd healthcare_saas_app/backend
sam deploy --parameter-overrides \
  "AppEnv=production DatabaseUrl=<value> JwtSecret=<value> \
  CorsOrigins=https://xxxxxxxxxxxx.cloudfront.net \
  DocumentsBucketName=healthcare-patient-documents \
  LambdaSecurityGroupId=sg-xxxxxxxx PrivateSubnetIds=subnet-aaa,subnet-bbb"
```

---

## Step 8: End-to-End Smoke Tests

```bash
BASE=https://xxxxxxxxxxxx.cloudfront.net

# API health via CloudFront
curl $BASE/api/health
# Expected: {"status":"healthy","database":"connected"}

# Frontend loads
curl -I $BASE/
# Expected: HTTP/2 200 with Content-Type: text/html

# Login (requires a registered user — register via API or UI first)
curl -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"TestPassword123"}'
# Expected: {"access_token":"...","role":"ADMIN",...}
```

---

## Known Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Wrong CloudFront origin request policy | `GET /api/health` returns HTML instead of JSON | Set `AllViewerExceptHostHeader` on `/api/*` behavior |
| NoEcho params not in samconfig.toml | `Parameters [DatabaseUrl, JwtSecret] must have values` | Always pass via `--parameter-overrides` |
| Windows PowerShell parameter overrides | Deploy fails with parse error | Put all `--parameter-overrides` on one line |
| Lambda can't reach RDS | `{"database":"disconnected"}` | Check SG outbound (Lambda) and SG inbound (RDS) on port 5432 |
| Stack in ROLLBACK_COMPLETE | Can't deploy — stack broken | `aws cloudformation delete-stack --stack-name healthcare-backend` then redeploy |
| CORS error on login | Browser blocks preflight | Ensure `CORS_ORIGINS` Lambda env var matches exact CloudFront domain |
| Frontend shows old version | Cached assets in CloudFront | `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"` |

---

## Success Criteria

- [ ] `GET /api/health` returns `{"status":"healthy","database":"connected"}` via CloudFront
- [ ] Frontend loads at `https://<cloudfront-domain>.cloudfront.net`
- [ ] Login works for PATIENT, DOCTOR, and ADMIN roles
- [ ] Appointment booking flow completes end-to-end
- [ ] Patient document upload works (requires S3 bucket + IAM policy)
- [ ] No API request returns HTML unexpectedly
