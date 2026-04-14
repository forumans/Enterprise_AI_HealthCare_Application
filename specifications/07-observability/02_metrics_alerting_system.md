# Prompt: Metrics and Alerting (Lambda + API Gateway)

## Prompt

Design and implement service, platform, and business metrics with alerting thresholds for this Healthcare SaaS application running on AWS Lambda + API Gateway.

---

### Metrics Scope

#### Lambda / API Layer (infrastructure)
- Invocation count (requests per minute/hour)
- Duration p50, p95, p99 (target p95 < 500ms for common endpoints)
- Error count and error rate (Lambda errors + API Gateway 4xx/5xx)
- Throttle count (Lambda concurrency limit hits)
- Cold start proxy: invocations with init duration (logged by Lambda as `Init Duration`)
- Concurrent executions

#### Database (RDS PostgreSQL)
- Active connections (Lambda pool: `pool_size=1` per execution environment)
- Query latency (tracked via SQLAlchemy event hooks or structured log timing)
- DB connection errors (logged in FastAPI exception handlers)
- RDS `DatabaseConnections` CloudWatch metric

#### Product / Business
- Login success rate (200 vs. 401 on `POST /api/auth/login`)
- Appointment booking success/failure rate
- Patient document upload success/failure rate
- Failed auth attempts per tenant (security signal)

---

### CloudWatch Metrics Sources

| Signal | Source | Namespace |
|--------|--------|-----------|
| Lambda invocations, errors, duration | Automatic | `AWS/Lambda` |
| API Gateway 4xx/5xx, latency | Automatic | `AWS/ApiGateway` |
| RDS connections, CPU, storage | Automatic | `AWS/RDS` |
| Application-level metrics | Structured log parsing (CloudWatch Logs Insights) | Custom |

---

### Requirements

1. **Structured log instrumentation in backend** — every request logs `duration_ms`, `status_code`, `endpoint`, `tenant_id` (no PHI). This enables CloudWatch Logs Insights queries as a lightweight metrics layer.

2. **CloudWatch Alarms** — define alarms for the critical failure modes below.

3. **SLO/SLI targets** — define and document the targets the alarms protect.

4. **Alert routing** — wire critical alarms to an SNS topic; SNS delivers to email or Slack webhook.

5. **Runbook links in alarm metadata** — every alarm description must reference a runbook file.

---

### SLO/SLI Targets

| Signal | SLI | SLO Target |
|--------|-----|-----------|
| API availability | (successful requests / total requests) | ≥ 99.5% per day |
| API latency (p95) | p95 of Lambda Duration | < 500ms |
| Login success rate | (200 responses / total login attempts) | ≥ 95% |
| DB connection errors | error count per hour | = 0 (alert on first occurrence) |
| Lambda error rate | (error invocations / total invocations) | < 1% |

---

### CloudWatch Alarms to Implement

```yaml
# Lambda error rate > 1% over 5 minutes
LambdaErrorRateAlarm:
  Namespace: AWS/Lambda
  MetricName: Errors
  Threshold: 1%  # use math expression: errors/invocations * 100

# Lambda p95 duration > 3000ms (approaching 30s timeout)
LambdaDurationAlarm:
  Namespace: AWS/Lambda
  MetricName: Duration
  ExtendedStatistic: p95
  Threshold: 3000  # milliseconds
  Period: 300

# API Gateway 5xx count > 10 in 5 minutes
ApiGateway5xxAlarm:
  Namespace: AWS/ApiGateway
  MetricName: 5XXError
  Threshold: 10
  Period: 300

# Lambda throttles > 0 (indicates concurrency limit hit)
LambdaThrottleAlarm:
  Namespace: AWS/Lambda
  MetricName: Throttles
  Threshold: 1
  Period: 60

# RDS connections > 80% of max_connections
RdsConnectionAlarm:
  Namespace: AWS/RDS
  MetricName: DatabaseConnections
  Threshold: 80  # tune based on RDS instance max_connections
```

---

### Deliverables

- Structured request logging in `backend/app/middleware/` (log `duration_ms`, `status_code`, `path`, `tenant_id`)
- CloudWatch Alarms defined in `backend/template.yaml` (SAM/CloudFormation) or `deployment/monitoring/alarms.yaml`
- SNS topic for alert delivery wired to alarms
- `deployment/runbooks/alerts.md` — for each alarm: what it means, how to investigate, how to resolve
- `testing/observability/` — smoke tests that verify health endpoints and log format

### Acceptance Criteria

- At least one CloudWatch dashboard covers Lambda invocations + duration + errors + API Gateway 4xx/5xx + RDS connections
- All critical alarms are defined and linked to an SNS topic
- No duplicate or low-signal alarms
- Every alarm description references a runbook
- Structured logs include `duration_ms` and `tenant_id` (no PHI in logs)
- `GET /api/health` returning `{"database":"connected"}` is the primary liveness signal for Lambda + RDS connectivity
