## ADDED Requirements

### Requirement: Structured JSON logging on every request
Every HTTP request SHALL produce a structured JSON log entry containing exactly: `timestamp` (ISO 8601), `level`, `request_id` (UUID), `tenant_id` (UUID, or null for public paths), `path`, `method`, `status_code`, and `duration_ms`. No other fields SHALL be included in the access log entry.

#### Scenario: Request produces structured log
- **GIVEN** a successful `POST /api/appointments` request
- **WHEN** the request completes
- **THEN** a JSON log entry SHALL be emitted with all eight required fields and SHALL NOT include the request body, JWT token, or any PHI

#### Scenario: Public path log omits tenant_id
- **GIVEN** a request to `GET /api/health` with no authentication
- **WHEN** the access log is written
- **THEN** the `tenant_id` field SHALL be `null` and all other required fields SHALL be present

---

### Requirement: PHI must never appear in any log entry
The logging system SHALL never emit passwords, password hashes, JWT tokens, JWT signing secrets, patient names, dates of birth, addresses, medical diagnoses, symptoms, lab results, or insurance policy numbers in any log entry at any log level.

#### Scenario: Exception log contains no credentials
- **GIVEN** an unhandled exception during a request
- **WHEN** the exception is logged with a stack trace
- **THEN** the log entry SHALL contain the exception type and message but SHALL NOT contain the `Authorization` header value, JWT token, or any password value

---

### Requirement: Log level controlled by environment
Production and staging SHALL use log level `INFO`. Local development SHALL use `DEBUG`. Debug-level log entries SHALL NOT be emitted in production or staging environments.

#### Scenario: Debug logs suppressed in production
- **GIVEN** `APP_ENV=production`
- **WHEN** any request is processed
- **THEN** no `DEBUG` level log entries SHALL appear in CloudWatch Logs

#### Scenario: Debug logs available in development
- **GIVEN** `APP_ENV=dev`
- **WHEN** a request is processed
- **THEN** `DEBUG` level entries MAY be emitted to help diagnose issues locally

---

### Requirement: CloudWatch log group has 30-day retention
The Lambda log group (`/aws/lambda/<function-name>`) SHALL have a retention policy of 30 days. This SHALL be declared in the SAM template or a companion CloudFormation resource.

#### Scenario: Log retention policy set
- **GIVEN** the Lambda function is deployed
- **WHEN** the CloudWatch log group is inspected
- **THEN** the retention period SHALL be 30 days and logs older than 30 days SHALL be automatically deleted

---

### Requirement: CloudWatch alarms defined for critical failure modes
The system SHALL define CloudWatch alarms for: Lambda error rate > 1% over 5 minutes, Lambda p95 duration > 3000ms over 5 minutes, API Gateway 5XX count > 10 over 5 minutes, Lambda throttle count > 0 over 1 minute, and RDS `DatabaseConnections` exceeding 80% of max connections. All alarms SHALL be wired to an SNS topic.

#### Scenario: Lambda error rate alarm fires
- **GIVEN** Lambda errors exceed 1% of total invocations over a 5-minute window
- **WHEN** the `LambdaErrorRateAlarm` evaluates
- **THEN** the alarm SHALL transition to ALARM state and SHALL publish a notification to the configured SNS topic

#### Scenario: RDS connection alarm fires
- **GIVEN** RDS `DatabaseConnections` exceeds the configured threshold
- **WHEN** the `RdsConnectionAlarm` evaluates
- **THEN** the alarm SHALL transition to ALARM state, signalling that Lambda concurrency may need to be limited

---

### Requirement: SLO targets define alarm thresholds
The system SHALL define and document the following SLO targets: API availability ≥ 99.5% per day, API p95 latency < 500ms, login success rate ≥ 95%, DB connection errors = 0, Lambda error rate < 1%. Alarms SHALL be set at thresholds that protect these SLOs.

#### Scenario: Alarm threshold aligned with SLO
- **GIVEN** the API availability SLO of 99.5%
- **WHEN** the Lambda error rate alarm threshold is reviewed
- **THEN** the threshold SHALL be set at a level that would trigger before the SLO is breached (e.g. error rate > 1%)

---

### Requirement: Request ID enables end-to-end trace correlation
Every request SHALL be assigned a `request_id` UUID that is: stored in `request.state`, propagated via a `ContextVar` to service layer code, included in every log entry emitted during that request, and returned as the `X-Request-ID` response header.

#### Scenario: Single request traceable across all log entries
- **GIVEN** a request with `request_id = "3f2a1b4c-..."`
- **WHEN** CloudWatch Logs Insights is queried with `filter request_id = "3f2a1b4c-..."`
- **THEN** all log entries for that request — including middleware, service, and exception entries — SHALL be returned in the query results

#### Scenario: X-Request-ID present in response
- **GIVEN** any request to any endpoint
- **WHEN** the response is received
- **THEN** the `X-Request-ID` response header SHALL contain the UUID assigned to that request

---

### Requirement: GET /api/health is the primary liveness signal
`GET /api/health` returning `{"database":"connected"}` SHALL be the primary indicator of Lambda + RDS connectivity. Monitoring systems and post-deploy smoke tests SHALL use this endpoint as the first check. IF it returns `{"database":"disconnected"}` the operator SHALL check Lambda VPC config, security group rules, and RDS instance status.

#### Scenario: Health endpoint confirms DB connectivity
- **GIVEN** Lambda can reach RDS on port 5432
- **WHEN** `GET /api/health` is called
- **THEN** the response SHALL be `{"status":"healthy","database":"connected"}` with status 200

#### Scenario: Health endpoint reports disconnection
- **GIVEN** Lambda cannot reach RDS (e.g. security group misconfiguration)
- **WHEN** `GET /api/health` is called
- **THEN** the response SHALL be `{"status":"unhealthy","database":"disconnected"}` with status 503
