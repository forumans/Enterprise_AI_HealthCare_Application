# Prompt: Observability — Logging, Metrics, and Tracing

## Prompt

Implement observability foundations for this Healthcare SaaS application running on AWS Lambda + API Gateway. Covers structured logging, CloudWatch metrics and alarms, SLO targets, and request tracing.

---

### Structured Logging

#### Log Format (JSON)

Every request log entry must include:

```json
{
  "timestamp": "2025-01-01T00:00:00Z",
  "level": "INFO",
  "request_id": "uuid",
  "tenant_id": "uuid",
  "path": "/api/appointments",
  "method": "POST",
  "status_code": 200,
  "duration_ms": 45
}
```

PHI must **never** appear in logs:
- No patient names, dates of birth, addresses
- No medical diagnoses, symptoms, or lab results
- No passwords, password hashes, or JWT tokens
- No insurance policy numbers

The `tenant_id` UUID is acceptable (it is an opaque identifier, not PHI).

#### Log Levels by Environment

| Environment | Level | Notes |
|-------------|-------|-------|
| Production | `INFO` | Request summaries, errors — no debug noise |
| Staging | `INFO` | Same as production |
| Development | `DEBUG` | Full request/response detail allowed |

Gate debug logs:
```python
if settings.app_env == "dev":
    logger.debug("[request body]", extra={"body": body})
```

#### CloudWatch Log Groups

Lambda writes to `/aws/lambda/<function-name>` automatically.

Set retention policy on the log group:
```yaml
# In SAM template or separate CloudFormation resource
LogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub "/aws/lambda/${BackendFunction}"
    RetentionInDays: 30
```

---

### Request Logging Middleware

Implement in `backend/app/middleware/` as a FastAPI middleware:

```python
import time
import uuid
import logging
import json

logger = logging.getLogger("healthcare.access")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.monotonic()

        response = await call_next(request)

        duration_ms = int((time.monotonic() - start) * 1000)
        tenant_id = getattr(request.state, "tenant_id", None)

        logger.info(json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "INFO",
            "request_id": request_id,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }))

        response.headers["X-Request-ID"] = request_id
        return response
```

---

### Metrics Scope

#### Lambda / API Layer

- Invocation count (requests per minute/hour)
- Duration p50, p95, p99 — target p95 < 500ms for common endpoints
- Error count and error rate (Lambda errors + API Gateway 4xx/5xx)
- Throttle count (Lambda concurrency limit hits)
- Cold starts — logged by Lambda as `Init Duration` in CloudWatch Logs
- Concurrent executions

#### Database (RDS PostgreSQL)

- Active connections — Lambda pool: `pool_size=1` per execution environment
- Query latency — tracked via structured log timing
- DB connection errors — logged in FastAPI exception handlers
- RDS `DatabaseConnections` CloudWatch metric

#### Business / Product

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

### SLO/SLI Targets

| Signal | SLI | SLO Target |
|--------|-----|-----------|
| API availability | successful requests / total requests | ≥ 99.5% per day |
| API latency (p95) | p95 of Lambda Duration | < 500ms |
| Login success rate | 200 responses / total login attempts | ≥ 95% |
| DB connection errors | error count per hour | = 0 (alert on first occurrence) |
| Lambda error rate | error invocations / total invocations | < 1% |

---

### CloudWatch Alarms

Define in `backend/template.yaml` (SAM) or a separate `deployment/monitoring/alarms.yaml`:

```yaml
# Lambda error rate > 1% over 5 minutes
LambdaErrorRateAlarm:
  Namespace: AWS/Lambda
  MetricName: Errors
  Threshold: 1%  # use math expression: errors/invocations * 100
  Period: 300
  EvaluationPeriods: 1

# Lambda p95 duration > 3000ms (approaching 30s timeout)
LambdaDurationAlarm:
  Namespace: AWS/Lambda
  MetricName: Duration
  ExtendedStatistic: p95
  Threshold: 3000  # milliseconds
  Period: 300
  EvaluationPeriods: 1

# API Gateway 5xx count > 10 in 5 minutes
ApiGateway5xxAlarm:
  Namespace: AWS/ApiGateway
  MetricName: 5XXError
  Threshold: 10
  Period: 300
  EvaluationPeriods: 1

# Lambda throttles > 0 (indicates concurrency limit hit)
LambdaThrottleAlarm:
  Namespace: AWS/Lambda
  MetricName: Throttles
  Threshold: 1
  Period: 60
  EvaluationPeriods: 1

# RDS connections > 80% of max_connections
RdsConnectionAlarm:
  Namespace: AWS/RDS
  MetricName: DatabaseConnections
  Threshold: 80  # tune based on RDS instance max_connections
  Period: 300
  EvaluationPeriods: 2
```

Wire all alarms to an SNS topic. SNS delivers to email or a Slack webhook. Every alarm description must include a link to the relevant runbook in `deployment/runbooks/alerts.md`.

---

### Useful CloudWatch Logs Insights Queries

```sql
-- Login failure rate in the last hour
fields @timestamp, status_code, path
| filter path = "/api/auth/login" and status_code = 401
| stats count() as failed_logins by bin(5m)

-- Slow requests (> 1s) by endpoint
fields @timestamp, path, duration_ms
| filter duration_ms > 1000
| stats avg(duration_ms) as avg_ms, count() as count by path
| sort count desc

-- Errors per tenant
fields @timestamp, tenant_id, status_code
| filter status_code >= 500
| stats count() as errors by tenant_id
| sort errors desc
```

---

### Request Tracing

#### Lightweight Tracing (CloudWatch)

Propagate `request_id` through the entire request lifecycle:
- Attach to `request.state.request_id` in middleware
- Pass to service layer via function parameters or context
- Include in all log entries for the request
- Return as `X-Request-ID` response header

This allows tracing a single user action across all log entries using CloudWatch Logs Insights:
```sql
fields @timestamp, path, status_code, duration_ms
| filter request_id = "3f2a1b4c-..."
| sort @timestamp asc
```

#### PHI-Safe Trace Metadata

Trace spans must never include:
- Patient identifiers beyond `user_id` (opaque UUID)
- Medical record content
- Authentication tokens

Acceptable trace fields: `request_id`, `tenant_id`, `path`, `method`, `status_code`, `duration_ms`.

---

### Health Check as Primary Liveness Signal

`GET /api/health` is the primary signal for Lambda + RDS connectivity:

```json
{"status": "healthy", "database": "connected"}
```

If `database` is `"disconnected"`, check:
1. Lambda VPC config (correct subnets)
2. Lambda security group outbound rules (allow port 5432)
3. RDS security group inbound rules (allow from Lambda SG)
4. RDS instance status in Console

---

### Deliverables

- `backend/app/middleware/request_logging.py` — structured JSON access log middleware
- `backend/template.yaml` — CloudWatch alarms and log group retention
- `deployment/runbooks/alerts.md` — for each alarm: what it means, how to investigate, how to resolve
- `deployment/monitoring/dashboard.json` — CloudWatch dashboard covering Lambda + API Gateway + RDS

### Acceptance Criteria

- Every request emits a structured JSON log with `request_id`, `tenant_id`, `path`, `status_code`, `duration_ms`.
- No PHI appears in any log output.
- CloudWatch alarms fire to SNS topic for all defined thresholds.
- Every alarm description references a runbook.
- CloudWatch dashboard covers Lambda invocations, duration, errors, API Gateway 4xx/5xx, RDS connections.
- `GET /api/health` is the primary liveness check — alert directly on its failure.
