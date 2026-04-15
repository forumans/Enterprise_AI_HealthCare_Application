## ADDED Requirements

### Requirement: CloudFront /api/* behavior uses AllViewerExceptHostHeader
The CloudFront distribution SHALL have a `/api/*` cache behavior that uses the `AllViewerExceptHostHeader` origin request policy (ID: `b689b0a8-53d0-40ab-baf2-68738e2966ac`) with caching disabled. Without this policy, CloudFront forwards the viewer's `Host` header to API Gateway, which returns 403 and causes the CloudFront 403 error rule to serve `index.html` for all API calls.

#### Scenario: API request routed correctly through CloudFront
- **GIVEN** the `/api/*` behavior is configured with `AllViewerExceptHostHeader`
- **WHEN** `GET https://<cloudfront>/api/health` is requested
- **THEN** CloudFront SHALL forward the request to API Gateway with the API Gateway host header, and the response SHALL be JSON, not `index.html`

#### Scenario: Wrong origin request policy causes API calls to return HTML
- **GIVEN** the `/api/*` behavior uses the default origin request policy
- **WHEN** `GET https://<cloudfront>/api/health` is requested
- **THEN** API Gateway SHALL return 403, CloudFront's error rule SHALL serve `index.html`, and the client SHALL receive HTML instead of JSON — this scenario documents the known failure mode to avoid

---

### Requirement: CloudFront 403/404 error rules serve index.html for SPA routing
The CloudFront distribution SHALL have custom error rules mapping both 403 and 404 responses to `/index.html` with status 200. This enables React Router to handle client-side navigation to any path.

#### Scenario: Direct navigation to React route
- **GIVEN** a user navigates directly to `https://<cloudfront>/patient/appointments`
- **WHEN** CloudFront receives the request and S3 returns 403 (key not found)
- **THEN** CloudFront SHALL serve `/index.html` and React Router SHALL render the correct page

---

### Requirement: SAM template defines Lambda with NoEcho parameters for secrets
The SAM template (`backend/template.yaml`) SHALL declare `DatabaseUrl` and `JwtSecret` as `NoEcho: true` parameters. These parameters SHALL NOT be saved to `samconfig.toml`. They SHALL be passed via `--parameter-overrides` on every `sam deploy` invocation.

#### Scenario: Secrets not persisted to samconfig.toml
- **GIVEN** `sam deploy --guided` is run with `DatabaseUrl` and `JwtSecret` provided
- **WHEN** the deployment completes and `samconfig.toml` is inspected
- **THEN** `DatabaseUrl` and `JwtSecret` SHALL NOT appear in that file

#### Scenario: Deploy fails without required parameters
- **GIVEN** `samconfig.toml` exists but does not contain `DatabaseUrl`
- **WHEN** `sam deploy` is run without `--parameter-overrides`
- **THEN** SAM SHALL report a parameter validation error and SHALL NOT deploy the stack

---

### Requirement: Lambda handler instantiated at module level
The Mangum adapter SHALL be assigned to `handler = Mangum(app, lifespan="off")` at module level in `backend/app/main.py`. The `lifespan="off"` parameter SHALL disable FastAPI lifespan context managers. The `handler` object SHALL be reused across warm Lambda invocations.

#### Scenario: Module-level handler reused on warm invocation
- **GIVEN** a warm Lambda execution environment
- **WHEN** a second request arrives
- **THEN** the existing `handler` object SHALL process the request without re-importing the module or creating a new Mangum instance

---

### Requirement: Database engine uses pool_size=1 and max_overflow=0
The SQLAlchemy async engine SHALL be configured with `pool_size=1`, `max_overflow=0`, and `pool_pre_ping=True`. This prevents RDS connection exhaustion when Lambda scales to high concurrency.

#### Scenario: Connection count bounded by Lambda concurrency
- **GIVEN** 50 concurrent Lambda invocations each with a warm execution environment
- **WHEN** all environments maintain their DB connections
- **THEN** the total number of connections to RDS SHALL be at most 50 (one per environment)

---

### Requirement: Backend and frontend deployable independently
The backend (SAM) and frontend (S3 sync) deployment pipelines SHALL be independent. Deploying the frontend SHALL NOT require a backend deployment and vice versa.

#### Scenario: Frontend-only deployment
- **GIVEN** a change to a React component
- **WHEN** `aws s3 sync dist/ s3://<bucket>` and a CloudFront invalidation are run
- **THEN** the frontend update SHALL be live without any SAM deployment or Lambda changes

---

### Requirement: Smoke tests validate deployment health
After every deployment the operator SHALL verify: `GET /api/health` returns `{"status":"healthy","database":"connected"}`, `POST /api/auth/login` returns a valid JWT, and `GET /api/doctors` returns a JSON array.

#### Scenario: Post-deploy health check passes
- **GIVEN** a successful `sam deploy`
- **WHEN** `curl https://<cloudfront>/api/health` is executed
- **THEN** the response SHALL be `{"status":"healthy","database":"connected"}` with status 200 and SHALL NOT be HTML
