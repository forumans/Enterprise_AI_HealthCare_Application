## ADDED Requirements

### Requirement: Prerequisites verified before first deployment
Before running `sam deploy`, the operator SHALL verify: AWS CLI is configured with valid credentials (`aws sts get-caller-identity` succeeds), SAM CLI version ≥ 1.90 is installed, Python 3.12 is available, Node.js 18+ is available, and `psql` is available for running migrations.

#### Scenario: Prerequisite check passes
- **GIVEN** an environment with all required tools installed
- **WHEN** each prerequisite command is run
- **THEN** all commands SHALL exit with status 0 and return expected version output

#### Scenario: Missing AWS credentials detected early
- **GIVEN** AWS CLI is not configured
- **WHEN** `aws sts get-caller-identity` is run
- **THEN** it SHALL return an error, alerting the operator before any deployment steps are attempted

---

### Requirement: Schema migration applied before first Lambda deployment
The operator SHALL apply `backend/migrations/001_initial_schema.sql` to the RDS instance via `psql` before running `sam deploy` for the first time. The migration SHALL be verified by running `\dt` and confirming all 14 tables are present.

#### Scenario: Schema applied to fresh database
- **GIVEN** a newly provisioned RDS PostgreSQL instance
- **WHEN** `psql -f migrations/001_initial_schema.sql` is run
- **THEN** all 14 tables SHALL be created and `\dt` SHALL list them all

---

### Requirement: SAM first deploy uses --guided to capture parameters
The first deployment SHALL use `sam deploy --guided` to interactively capture all parameters and save non-secret values to `samconfig.toml`. `DatabaseUrl` and `JwtSecret` SHALL NOT be saved to `samconfig.toml` due to their `NoEcho: true` declaration.

#### Scenario: Guided deploy saves non-secret parameters
- **GIVEN** `sam deploy --guided` completes successfully
- **WHEN** `samconfig.toml` is inspected
- **THEN** it SHALL contain `AppEnv`, `CorsOrigins`, `DocumentsBucketName`, `LambdaSecurityGroupId`, and `PrivateSubnetIds`, but SHALL NOT contain `DatabaseUrl` or `JwtSecret`

---

### Requirement: CloudFront /api/* behavior configured with AllViewerExceptHostHeader
The operator SHALL configure the CloudFront `/api/*` cache behavior to use the `AllViewerExceptHostHeader` origin request policy. This SHALL be done before running end-to-end smoke tests. If this policy is missing, API calls will return HTML instead of JSON.

#### Scenario: API call returns JSON via CloudFront
- **GIVEN** the `/api/*` behavior uses `AllViewerExceptHostHeader`
- **WHEN** `curl https://<cloudfront>/api/health` is run
- **THEN** the response SHALL be `{"status":"healthy","database":"connected"}` — not `index.html`

#### Scenario: Known failure mode documented
- **GIVEN** the `/api/*` behavior is missing the `AllViewerExceptHostHeader` policy
- **WHEN** `curl https://<cloudfront>/api/health` is run
- **THEN** the response SHALL be HTML (CloudFront error page returned `index.html`), which is the known symptom of this misconfiguration

---

### Requirement: CORS origins updated after CloudFront domain is known
After the CloudFront distribution is created and its domain is known, the backend SHALL be redeployed with `CorsOrigins` set to the exact CloudFront domain. This second `sam deploy` SHALL use `--parameter-overrides` to pass all parameters including the now-known CloudFront domain.

#### Scenario: CORS updated with CloudFront domain
- **GIVEN** the CloudFront distribution domain is `xxxx.cloudfront.net`
- **WHEN** `sam deploy --parameter-overrides "CorsOrigins=https://xxxx.cloudfront.net ..."` is run
- **THEN** the Lambda `CORS_ORIGINS` environment variable SHALL contain the exact CloudFront domain and browser preflight requests from that domain SHALL succeed

---

### Requirement: End-to-end smoke tests pass before first production use
After all infrastructure is configured, the operator SHALL verify: `GET /api/health` via CloudFront returns `{"database":"connected"}`, the frontend loads at the CloudFront URL, and login works for at least one role.

#### Scenario: Full smoke test passes
- **GIVEN** all infrastructure steps are complete
- **WHEN** the smoke test script is run against the CloudFront domain
- **THEN** health check, frontend load, and login SHALL all return successful responses
