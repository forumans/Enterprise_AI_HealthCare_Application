## ADDED Requirements

### Requirement: Middleware stack order
The FastAPI application SHALL register middleware in the following order (outermost first): `SecurityHeadersMiddleware`, `TenantContextMiddleware`, `CORSMiddleware`. This ensures security headers are added to every response including CORS preflight responses, and tenant context is available to all downstream handlers.

#### Scenario: Middleware executes in correct order
- **GIVEN** a request to a protected endpoint
- **WHEN** the request is processed
- **THEN** CORS headers SHALL be evaluated first on the inbound path, then the JWT SHALL be validated, and security headers SHALL be appended to the outbound response

---

### Requirement: CORS configured in FastAPI only
The system SHALL configure CORS exclusively via FastAPI's `CORSMiddleware`. API Gateway SHALL NOT be configured to add CORS headers. The `allow_origins` list SHALL be populated from the `CORS_ORIGINS` environment variable. In production the list SHALL contain only the CloudFront domain. In local development it SHALL also allow `http://127.0.0.1:5173` and `http://localhost:5173`.

#### Scenario: CORS preflight from CloudFront domain
- **GIVEN** `CORS_ORIGINS` is set to `https://example.cloudfront.net`
- **WHEN** a browser sends an OPTIONS preflight from `https://example.cloudfront.net`
- **THEN** the response SHALL include `Access-Control-Allow-Origin: https://example.cloudfront.net` with status 200

#### Scenario: CORS rejected from unknown origin
- **GIVEN** `CORS_ORIGINS` does not include `https://attacker.com`
- **WHEN** a request arrives with `Origin: https://attacker.com`
- **THEN** the response SHALL NOT include `Access-Control-Allow-Origin` for that origin

#### Scenario: No duplicate CORS headers
- **GIVEN** CORS is configured only in FastAPI and not at API Gateway
- **WHEN** a CORS-enabled request passes through CloudFront and API Gateway to Lambda
- **THEN** each CORS header SHALL appear exactly once in the response — not duplicated

---

### Requirement: Lambda entry point via Mangum
The module `backend/app/main.py` SHALL define a module-level `handler = Mangum(app, lifespan="off")`. The `handler` object SHALL be the Lambda entry point declared in the SAM template as `Handler: app.main.handler`. The `lifespan="off"` parameter SHALL disable FastAPI lifespan context managers because Lambda does not guarantee shutdown events.

#### Scenario: Lambda cold start
- **GIVEN** a new Lambda execution environment
- **WHEN** the module is imported by the Lambda runtime
- **THEN** `handler` SHALL be a valid callable Mangum adapter wrapping the FastAPI `app`

#### Scenario: Warm invocation reuses handler
- **GIVEN** a Lambda execution environment that has already handled at least one request
- **WHEN** a subsequent request arrives
- **THEN** the same `handler`, `app`, and database `engine` module-level objects SHALL be reused without re-initialisation

---

### Requirement: Settings loaded from environment variables
All application settings SHALL be read from environment variables via a frozen `Settings` dataclass. The application SHALL fail fast on startup if `DATABASE_URL` or `JWT_SECRET` are absent or empty.

#### Scenario: Required variable missing
- **GIVEN** `DATABASE_URL` is not set in the environment
- **WHEN** the application starts
- **THEN** startup SHALL raise a configuration error before accepting any requests

#### Scenario: All settings accessible via singleton
- **GIVEN** the `settings` module-level singleton is instantiated
- **WHEN** any module imports `from app.core.config import settings`
- **THEN** `settings.database_url`, `settings.jwt_secret`, `settings.cors_origins`, and all other defined fields SHALL be accessible without additional calls

---

### Requirement: Request ID propagated through request lifecycle
Every request SHALL be assigned a unique `request_id` UUID by the middleware. The `request_id` SHALL be stored in `request.state` and in a `ContextVar` so it is accessible in service layer code. The `request_id` SHALL be included in every structured log entry and returned in the `X-Request-ID` response header.

#### Scenario: Request ID in log output
- **GIVEN** a request processed by the application
- **WHEN** any logger emits a message during that request
- **THEN** the log entry SHALL include the `request_id` assigned to that request

#### Scenario: Request ID in response header
- **GIVEN** any request to any endpoint
- **WHEN** the response is returned
- **THEN** the response SHALL include an `X-Request-ID` header containing the UUID assigned to that request

---

### Requirement: Rate limiting on auth endpoints
The system SHALL enforce rate limits on sensitive endpoints: `POST /auth/login` at 10 requests per minute per IP, `POST /auth/forgot-password` at 5 requests per minute per IP, `POST /auth/reset-password` at 5 requests per minute per IP. WHEN a rate limit is exceeded the system SHALL return `429 Too Many Requests` with a `Retry-After: 60` header. For production scale, rate limiting SHOULD be implemented at AWS WAF on CloudFront or API Gateway rather than in-process.

#### Scenario: Login rate limit exceeded
- **GIVEN** 10 failed login attempts from the same IP within one minute
- **WHEN** an 11th request arrives from that IP
- **THEN** the system SHALL return `429 {"detail": "Too many requests. Please retry after 60 seconds."}` with `Retry-After: 60`

---

### Requirement: Unhandled exceptions return safe 500 response
The application SHALL register a global exception handler that catches all unhandled exceptions. The handler SHALL log the exception with a stack trace for internal diagnostics and SHALL return `500 {"detail": "An internal error occurred. Please try again."}` to the client. Stack traces and internal error details SHALL NOT be exposed in the API response.

#### Scenario: Unexpected exception in route handler
- **GIVEN** a route handler that raises an unexpected RuntimeError
- **WHEN** the exception propagates to the global handler
- **THEN** the client SHALL receive `500 {"detail": "An internal error occurred. Please try again."}` and the internal stack trace SHALL appear only in CloudWatch logs, not in the response body
