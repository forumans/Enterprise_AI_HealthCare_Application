# Prompt: CI/CD and Release Engineering (SAM + Lambda)

## Prompt

Implement CI/CD pipelines for this Healthcare SaaS application. The backend deploys via AWS SAM (no Docker container push, no ECR). The frontend deploys to S3 with CloudFront cache invalidation. Both pipelines run independently in GitHub Actions.

---

### Backend Pipeline (GitHub Actions)

**Trigger:** Push or PR to `main` with changes under `healthcare_saas_app/backend/**`.

**Stages:**

1. **Lint and type checks**
   - `ruff check .` — linting
   - `mypy app/` — type checking

2. **Unit and integration tests**
   - `pytest` with coverage gate (minimum 70%)
   - Tests run against a local PostgreSQL service container in the CI job

3. **SAM build**
   - `sam build` — packages Lambda function and dependencies
   - Validates template: `sam validate`

4. **Database migration** (production deploy only)
   - Apply any new SQL files under `migrations/` against RDS
   - Schema must be current before Lambda code is deployed
   - Use `psql` with RDS endpoint and credentials from GitHub secrets

5. **SAM deploy**
   - `sam deploy` with `--parameter-overrides` for all parameters
   - `DatabaseUrl` and `JwtSecret` sourced from GitHub secrets (never in samconfig.toml)
   - Targets environment-specific stack name based on branch

**Example workflow snippet:**
```yaml
- name: SAM build
  run: sam build
  working-directory: healthcare_saas_app/backend

- name: SAM deploy
  run: >
    sam deploy
    --no-confirm-changeset
    --no-fail-on-empty-changeset
    --parameter-overrides
    "AppEnv=production
    DatabaseUrl=${{ secrets.DATABASE_URL }}
    JwtSecret=${{ secrets.JWT_SECRET }}
    CorsOrigins=${{ secrets.CORS_ORIGINS }}
    DocumentsBucketName=${{ secrets.DOCUMENTS_BUCKET }}
    LambdaSecurityGroupId=${{ secrets.LAMBDA_SG_ID }}
    PrivateSubnetIds=${{ secrets.PRIVATE_SUBNET_IDS }}"
  working-directory: healthcare_saas_app/backend
```

---

### Frontend Pipeline (GitHub Actions)

**Trigger:** Push or PR to `main` with changes under `healthcare_saas_app/frontend/**`.

**Stages:**

1. **Lint and type checks**
   - `npm run lint` — ESLint
   - `npx tsc --noEmit` — TypeScript type checking

2. **Unit tests**
   - `npm run test` — Vitest with coverage gate

3. **Build**
   - `npm run build` — Vite production build
   - Artifacts: `dist/` directory

4. **Deploy to S3**
   - `aws s3 sync dist/ s3://$FRONTEND_BUCKET --delete`

5. **CloudFront cache invalidation**
   - `aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"`

---

### GitHub Actions Secrets Required

| Secret name | Used by | Description |
|-------------|---------|-------------|
| `AWS_ACCESS_KEY_ID` | Both | IAM user for deployments |
| `AWS_SECRET_ACCESS_KEY` | Both | IAM user for deployments |
| `AWS_REGION` | Both | e.g. `us-east-1` |
| `DATABASE_URL` | Backend | `postgresql+asyncpg://user:pass@host:5432/db` |
| `JWT_SECRET` | Backend | HS256 signing secret (random, ≥ 32 chars) |
| `CORS_ORIGINS` | Backend | CloudFront domain, e.g. `https://xxxx.cloudfront.net` |
| `DOCUMENTS_BUCKET` | Backend | S3 bucket name for patient documents |
| `LAMBDA_SG_ID` | Backend | Security group ID for Lambda VPC placement |
| `PRIVATE_SUBNET_IDS` | Backend | Comma-separated subnet IDs |
| `FRONTEND_BUCKET` | Frontend | S3 bucket name for static assets |
| `CLOUDFRONT_DIST_ID` | Frontend | CloudFront distribution ID |

---

### IAM Permissions for Deploy User

The IAM user running `sam deploy` needs these permissions (managed or inline):

- `lambda:*`
- `apigateway:*`
- `cloudformation:*`
- `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PassRole`, `iam:GetRole`, `iam:DetachRolePolicy`, `iam:DeleteRole`
- `s3:PutObject`, `s3:GetObject`, `s3:CreateBucket` (SAM deployment bucket)
- `ec2:DescribeVpcs`, `ec2:DescribeSubnets`, `ec2:DescribeSecurityGroups`
- `cloudfront:CreateInvalidation`

Note: `iam:*` in the role list requires `--capabilities CAPABILITY_IAM` in `sam deploy`. Do **not** use named roles in the SAM template as that would require `CAPABILITY_NAMED_IAM`.

---

### Release Versioning

- Every deployment artifact is traced to a commit SHA (Lambda function description includes `${{ github.sha }}`).
- Deployment environment is tagged in SAM stack tags: `Environment=production`.
- Git tags (`v1.0.0`, `v1.1.0`) mark release points; patch versions for hotfixes.

---

### Rollback

**Backend:**
```bash
# CloudFormation automatically rolls back failed deployments.
# For manual rollback to previous changeset:
aws cloudformation cancel-update-stack --stack-name healthcare-backend
```

**Frontend:**
```bash
# Re-sync previous dist/ build to S3, then invalidate
aws s3 sync <previous-dist>/ s3://$FRONTEND_BUCKET --delete
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

---

### Migration Safety Rules

1. All SQL migrations are applied **before** the new Lambda code is deployed.
2. Migrations must be backward-compatible with the previous Lambda version (old code must still run against the new schema).
3. Non-destructive changes only (no column drops in the same migration as column additions).
4. Each migration file is named `NNN_description.sql` and applied in order.
5. Never use `DB_SCHEMA_INIT_ON_STARTUP=true` in production — that is for local development only.

---

### Deliverables

- `.github/workflows/backend-deploy.yml` — SAM build, test, migrate, deploy
- `.github/workflows/frontend-deploy.yml` — type-check, test, build, S3 sync, invalidate
- `deployment/runbooks/release.md` — ordered deployment steps for a new release
- `deployment/runbooks/rollback.md` — rollback steps for backend and frontend
- `deployment/runbooks/migrations.md` — how to author, test, and apply SQL migrations

### Acceptance Criteria

- Pipeline failures are fast and informative; no silent failures.
- Backend and frontend pipelines are independently triggerable.
- Every production deploy is traceable to a commit SHA.
- Rollback can be completed within 5 minutes for both backend and frontend.
- `DatabaseUrl` and `JwtSecret` are never stored in samconfig.toml or logs.
