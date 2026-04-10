# Prompt: Logging and Monitoring Strategy

## Prompt
Implement observability foundations across `backend`, `infrastructure`, and `deployment`.

### Requirements
1. Use structured logs (JSON) with consistent fields:
   - timestamp, level, service, environment, request_id, tenant_id (when applicable).
2. Prevent PHI leakage in logs.
3. Define log levels per environment and avoid verbose production noise.
4. Centralize logs to CloudWatch (or equivalent) with retention policy.

### Deliverables
- Logging configuration in `backend/app/main.py` and shared logging utilities.
- `deployment/observability/logging-runbook.md`.
- `infrastructure/` settings for log groups and retention.
- Tests/assertions in `testing/observability/` for log format and redaction.

### Acceptance Criteria
- Request flows are traceable by request id.
- Production runtime paths do not emit debug logs by default.
- Error logs are actionable but scrubbed of sensitive data.
