# Prompt: Metrics and Alerting

## Prompt
Design and implement service, platform, and business metrics with alerting thresholds.

### Metrics Scope
- Backend API: request count, latency p50/p95/p99, error rate, saturation.
- Database: connection usage, query latency, deadlocks/timeouts.
- Infrastructure: ECS task health, CPU/memory, ALB target health.
- Product: login success rate, appointment booking success/failure.

### Requirements
1. Expose backend metrics endpoint compatible with collector.
2. Define SLO/SLI targets and corresponding alerts.
3. Wire critical alerts to an actionable channel.
4. Provide runbook links in alert metadata.

### Deliverables
- Metrics instrumentation in `backend/`.
- Alert policies in `infrastructure/monitoring/`.
- Operational docs in `deployment/runbooks/alerts.md`.
- Validation checks in `testing/observability/`.

### Acceptance Criteria
- At least one dashboard exists for API + DB + infra health.
- Alert noise is controlled (no duplicate low-signal alerts).
- Critical failure modes are covered by alerts.
