## ADDED Requirements

### Requirement: Backend and frontend CI/CD pipelines are independent
The project SHALL have two independent GitHub Actions workflows: one triggered by changes under `healthcare_saas_app/backend/**` and one triggered by changes under `healthcare_saas_app/frontend/**`. Either pipeline SHALL be triggerable independently without requiring the other to run.

#### Scenario: Backend change triggers only backend pipeline
- **GIVEN** a commit modifying only `backend/app/api/routes/auth.py`
- **WHEN** the commit is pushed to `main`
- **THEN** the backend pipeline SHALL trigger and the frontend pipeline SHALL NOT trigger

---

### Requirement: Backend pipeline runs lint, type check, and tests before deploying
The backend pipeline SHALL execute stages in order: (1) `ruff check` linting, (2) `mypy app/` type checking, (3) `pytest` with a 70% coverage gate, (4) database migration via `psql`, (5) `sam build`, (6) `sam deploy`. IF any stage fails, subsequent stages SHALL NOT run.

#### Scenario: Lint failure stops pipeline
- **GIVEN** a Python file with a style violation detected by `ruff`
- **WHEN** the backend CI pipeline runs
- **THEN** the lint stage SHALL fail and the deploy stage SHALL NOT execute

#### Scenario: Tests pass before deploy
- **GIVEN** all lint, type, and test stages pass
- **WHEN** the pipeline proceeds to deployment
- **THEN** the migration step SHALL run before `sam deploy`, and `sam deploy` SHALL only execute after the migration completes successfully

---

### Requirement: Database migration applied before Lambda code deployment
In the backend CI pipeline, the `psql` migration step SHALL execute and complete successfully before `sam deploy` is invoked. This ensures the new schema is in place before new Lambda code that depends on it is deployed.

#### Scenario: Migration runs before deploy
- **GIVEN** a new SQL migration file in `backend/migrations/`
- **WHEN** the CI pipeline runs on a push to `main`
- **THEN** `psql -f migrations/NNN_*.sql` SHALL complete before `sam deploy` begins

---

### Requirement: Secrets passed via GitHub Actions secrets, never in samconfig.toml
`DATABASE_URL` and `JWT_SECRET` SHALL be stored as GitHub Actions secrets and passed to `sam deploy` via `--parameter-overrides`. They SHALL NOT be committed to `samconfig.toml`, repository files, or appear in any pipeline log output.

#### Scenario: Secrets not in repository
- **GIVEN** the full repository including `samconfig.toml`
- **WHEN** all files are inspected for `DATABASE_URL` or `JWT_SECRET` values
- **THEN** no plaintext secret values SHALL appear in any committed file

#### Scenario: Deploy uses secrets from GitHub
- **GIVEN** `DATABASE_URL` is stored as a GitHub Actions secret
- **WHEN** the deploy step runs
- **THEN** the secret SHALL be injected via `${{ secrets.DATABASE_URL }}` in the `--parameter-overrides` argument and SHALL NOT be echoed to the pipeline log

---

### Requirement: Frontend pipeline runs type check, tests, and build before deploying
The frontend pipeline SHALL execute: (1) `npx tsc --noEmit`, (2) `npm run test`, (3) `npm run build`, (4) `aws s3 sync dist/ s3://$FRONTEND_BUCKET --delete`, (5) CloudFront cache invalidation. IF any stage fails, subsequent stages SHALL NOT run.

#### Scenario: Type error stops pipeline
- **GIVEN** a TypeScript type error in a component
- **WHEN** the frontend CI pipeline runs
- **THEN** `tsc --noEmit` SHALL fail and the S3 sync step SHALL NOT execute

#### Scenario: CloudFront invalidated after S3 sync
- **GIVEN** the S3 sync completes successfully
- **WHEN** the pipeline proceeds
- **THEN** `aws cloudfront create-invalidation --paths "/*"` SHALL be invoked to clear the CDN cache

---

### Requirement: Every production deploy is traceable to a commit SHA
The Lambda function description SHALL include the deploying commit SHA from `${{ github.sha }}`. SAM stack tags SHALL include `Environment=production`.

#### Scenario: Lambda description includes commit SHA
- **GIVEN** a deployment triggered by commit `abc1234`
- **WHEN** the Lambda function is inspected in the AWS Console after deployment
- **THEN** the function description SHALL contain `abc1234`

---

### Requirement: Rollback completable within 5 minutes
The backend SHALL be rollbackable by cancelling the in-flight CloudFormation stack update. The frontend SHALL be rollbackable by re-syncing the previous `dist/` build to S3 and invalidating CloudFront. Both rollback procedures SHALL be documented.

#### Scenario: Backend rollback via CloudFormation
- **GIVEN** a failed or unwanted `sam deploy`
- **WHEN** `aws cloudformation cancel-update-stack` is run
- **THEN** CloudFormation SHALL roll back to the previous stable state automatically
