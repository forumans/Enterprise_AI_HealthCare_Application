# Prompt: Distributed Tracing

## Prompt
Implement request tracing across the stack for root-cause analysis and performance diagnostics.

### Requirements
1. Instrument backend request lifecycle with OpenTelemetry-compatible tracing.
2. Propagate trace context across middleware, DB calls, and outbound integrations.
3. Correlate traces with logs via shared ids.
4. Keep trace metadata PHI-safe.

### Deliverables
- Tracing setup in `backend/`.
- Collector/export config in `infrastructure/observability/`.
- `deployment/runbooks/tracing-debug.md`.
- Smoke tests in `testing/observability/` for trace creation and propagation.

### Acceptance Criteria
- One user action can be followed end-to-end in trace UI.
- Slow spans identify backend and DB bottlenecks.
- Trace sampling strategy is environment-aware.
