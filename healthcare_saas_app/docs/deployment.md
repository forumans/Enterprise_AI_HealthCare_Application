# Deployment Guide

The backend is deployed as an AWS Lambda function using AWS SAM. The frontend is a static React app hosted on S3 and served through CloudFront.

---

## Prerequisites

| Tool | Purpose |
|---|---|
| [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) | Interacting with AWS |
| [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) | Building and deploying Lambda |
| Python 3.12 | SAM build runtime |
| Node.js 18+ | Frontend build |
| Docker (optional) | `sam build --use-container` |

Configure the AWS CLI before deploying:
```bash
aws configure
```

---

## AWS Infrastructure Required Before Deploying

The SAM template deploys Lambda + API Gateway only. The following must already exist in your AWS account:

| Resource | Notes |
|---|---|
| VPC + private subnets | Where RDS and Lambda will run |
| RDS PostgreSQL instance | Must be in the private subnets |
| Security group for Lambda | Must be allowed inbound on RDS port 5432 |
| S3 bucket for documents | Private bucket for patient file uploads |
| S3 bucket for frontend | For the React app static files |
| CloudFront distribution | Serving the frontend + routing `/api/*` to API Gateway |

---

## Backend Deployment (AWS SAM)

### 1. Build

```bash
cd healthcare_saas_app/backend
sam build
```

This packages the FastAPI app and all dependencies into the `.aws-sam/build/` directory.

If you get a Python version mismatch error, build inside Docker instead:
```bash
sam build --use-container
```

### 2. Deploy (First Time)

```bash
sam deploy --guided
```

SAM will prompt for configuration values. Enter:

| Prompt | Value |
|---|---|
| Stack Name | `healthcare-backend` |
| AWS Region | e.g. `us-east-1` |
| AppEnv | `production` |
| DatabaseUrl | `postgresql+asyncpg://user:pass@rds-endpoint:5432/dbname` |
| JwtSecret | Your JWT signing secret |
| CorsOrigins | `https://your-cloudfront-domain.cloudfront.net` |
| DocumentsBucketName | Name of your S3 documents bucket |
| LambdaSecurityGroupId | Security group ID for Lambda (e.g. `sg-xxxxxxxx`) |
| PrivateSubnetIds | Comma-separated subnet IDs (e.g. `subnet-aaa,subnet-bbb`) |
| Allow SAM CLI IAM role creation | `Y` |
| Disable rollback | `N` |
| BackendFunction has no authentication | `Y` (auth handled by FastAPI JWT) |
| Save arguments to samconfig.toml | `Y` |

> `DatabaseUrl` and `JwtSecret` are marked `NoEcho` — they will not be saved to `samconfig.toml` for security. You must pass them on every deploy via `--parameter-overrides`.

### 3. Deploy (Subsequent Deployments)

```bash
sam build && sam deploy --parameter-overrides \
  "DatabaseUrl=postgresql+asyncpg://user:pass@rds-endpoint:5432/dbname" \
  "JwtSecret=your-jwt-secret" \
  "AppEnv=production" \
  "CorsOrigins=https://your-cloudfront-domain.cloudfront.net" \
  "DocumentsBucketName=your-documents-bucket" \
  "LambdaSecurityGroupId=sg-xxxxxxxx" \
  "PrivateSubnetIds=subnet-aaa,subnet-bbb"
```

On Windows PowerShell all parameters must be on a single line.

### 4. Deployment Output

After a successful deploy, SAM prints:

```
Outputs
-------
ApiUrl            https://<api-id>.execute-api.<region>.amazonaws.com
BackendFunctionArn  arn:aws:lambda:...
BackendFunctionName healthcare-backend-backend
```

The `ApiUrl` is your Lambda backend URL. This is the origin CloudFront will proxy `/api/*` to.

---

## Configure CloudFront to Route API Traffic to Lambda

After the first backend deploy, update the CloudFront distribution to forward `/api/*` requests to API Gateway instead of any previous backend (e.g. ALB):

1. In the AWS Console, open your CloudFront distribution
2. Go to **Behaviors** → edit the `/api/*` behavior
3. Set the **Origin** to a new custom origin pointing to `<api-id>.execute-api.<region>.amazonaws.com`
4. Set **Origin Protocol Policy** to `HTTPS Only`
5. Set **Origin Request Policy** to `AllViewerExceptHostHeader` (required — API Gateway rejects requests with the wrong `Host` header)
6. Save and wait for the distribution to deploy (~3–5 minutes)

---

## Frontend Deployment

### 1. Build

```bash
cd healthcare_saas_app/frontend
npm install
npm run build
```

This creates a `dist/` folder with the compiled React app.

### 2. Upload to S3

```bash
aws s3 sync dist/ s3://your-frontend-bucket --delete --region us-east-1
```

### 3. Invalidate CloudFront Cache

```bash
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

This forces CloudFront to serve the new version immediately rather than returning cached files.

---

## Lambda Function Configuration

The Lambda function is configured via environment variables. These are set at deploy time via SAM parameter overrides:

| Variable | Description |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | Async PostgreSQL connection string |
| `JWT_SECRET` | HS256 signing key |
| `JWT_ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_MINUTES` | Token TTL in minutes (default `30`) |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `DB_SCHEMA_INIT_ON_STARTUP` | `false` in production — use migrations |
| `S3_BUCKET_NAME` | S3 bucket for patient document uploads |
| `AWS_SECRETS_MANAGER_ENABLED` | `false` (env vars used directly) |

### Lambda Sizing

Defaults in `template.yaml`:

| Setting | Value | When to change |
|---|---|---|
| Memory | 512 MB | Increase to 1024 MB if cold starts are slow |
| Timeout | 30 s | Increase if complex queries time out |
| Runtime | python3.12 | Update when AWS deprecates this version |

---

## Database Schema Management

`DB_SCHEMA_INIT_ON_STARTUP` is `false` in production. Schema changes must be applied using the SQL migration scripts in `migrations/`:

```bash
# Apply migrations manually against the RDS instance
psql -h your-rds-endpoint -U healthcare_user -d healthcare_db -f migrations/001_initial_schema.sql
```

---

## IAM Permissions Required for Deployment

The AWS user or role running `sam deploy` needs:

- `lambda:*`
- `apigateway:*`
- `cloudformation:*`
- `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PassRole`
- `s3:PutObject`, `s3:GetObject` (SAM deployment bucket)
- `ec2:Describe*` (VPC placement)

---

## Rollback

SAM deploys via CloudFormation changesets. If a deployment fails, CloudFormation automatically rolls back to the previous working state (unless you disabled rollback with `--disable-rollback`).

To manually roll back to a specific version:
```bash
aws cloudformation cancel-update-stack --stack-name healthcare-backend
```

---

## Monitoring

After deployment, monitor the Lambda function in CloudWatch:

```bash
# Tail live logs (Git Bash / Linux)
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/healthcare-backend-backend \
  --follow --region us-east-1

# Check invocation metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=healthcare-backend-backend \
  --start-time 2026-01-01T00:00:00Z \
  --end-time 2026-12-31T00:00:00Z \
  --period 86400 \
  --statistics Sum \
  --region us-east-1
```
