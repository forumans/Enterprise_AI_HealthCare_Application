# Prompt: Database Performance and Reliability

## Prompt
You are the database performance engineer for a multi-tenant Healthcare SaaS system. Optimize PostgreSQL design and access patterns used by `backend/`.

### Context
- Project boundaries must remain separate: `frontend/`, `backend/`, `testing/`, `infrastructure/`, `deployment/`.
- Backend uses async SQLAlchemy and Alembic migrations.
- Database target is AWS RDS PostgreSQL.

### Objectives
1. Identify and optimize hot-path queries:
   - auth/login and tenant resolution,
   - appointment listing (today/week/all),
   - patient/doctor/admin dashboard aggregates,
   - soft-delete filtering.
2. Add and validate indexes for read-heavy paths.
3. Define safe archival strategy for historical audit/appointment data.
4. Add performance guardrails in tests and observability.

### Required Deliverables
- `backend/docs/query-profiles.md` with top query patterns and expected complexity.
- Migration files adding indexes and constraints where needed.
- `testing/performance/` scripts for query/load checks.
- Alert thresholds for DB saturation in observability docs.

### Acceptance Criteria
- No full-table scans on primary dashboard and appointment paths under normal filters.
- Tenant-scoped queries use index-backed predicates.
- p95 API latency target remains feasible (<500ms for common endpoints).
- All index additions are migration-based and rollback-safe.
