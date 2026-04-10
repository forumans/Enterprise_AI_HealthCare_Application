# Prompt: Database Architecture and Multi-Tenant Design

## Prompt
You are the database architect for a Healthcare SaaS platform. Design and implement the database layer in `backend/` for PostgreSQL on AWS RDS.

### Goals
- Multi-tenant schema with strong tenant isolation.
- Healthcare core entities with auditability.
- Operationally safe schema for production migrations.

### Required Entities
- `tenants`, `users`, `admins`, `doctors`, `patients`
- `appointments`, `medical_records`, `prescriptions`, `pharmacies`
- `audit_logs` (immutable append-only behavior)

### Hard Rules
1. Use UUID primary keys.
2. Include `created_at`, `updated_at`, and soft-delete fields where needed.
3. Enforce tenant isolation (`tenant_id`) on tenant-owned tables.
4. Add unique and composite indexes for hot query paths.
5. Keep PHI out of non-essential tables.
6. Model foreign keys and cascade behavior explicitly.

### Deliverables
- SQLAlchemy models in `backend/app/models/`.
- Database session/config in `backend/app/core/database.py`.
- ERD-level markdown summary in `backend/docs/database-model.md`.
- Query/index rationale in `backend/docs/database-performance-notes.md`.

### Acceptance Criteria
- Core workflows are representable: auth, appointments, clinical notes, prescriptions.
- Tenant-scoped queries are first-class and index-backed.
- Audit trail supports who/when/what change tracking.
- No schema choices that block future partitioning and archiving.
