# Prompt: Database Schema Design

## Prompt

You are the database architect for a multi-tenant Healthcare SaaS platform. Design and implement the full database layer using SQLAlchemy 2.0 async ORM with asyncpg on PostgreSQL (AWS RDS target).

---

### Hard Rules

1. UUID primary keys on every table (`gen_random_uuid()` default).
2. `tenant_id` foreign key on every tenant-owned table — enforced in every query.
3. `created_at TIMESTAMP NOT NULL DEFAULT NOW()` on every table.
4. Soft-delete via `deleted_at TIMESTAMP` + `deleted_by UUID` on all mutable business entities. Audit logs are immutable (no soft-delete).
5. No PHI in table or column names; keep column names generic.
6. Foreign keys with explicit ON DELETE behavior.
7. Composite and covering indexes for all hot query paths.
8. No `updated_at` — soft-delete pattern makes it unnecessary; use audit logs for change history.

---

### Entity Overview

```
tenants
  └── users (tenant_id)
        ├── doctors (user_id)
        │     ├── doctor_availability (doctor_id)
        │     └── appointments (doctor_id)
        │           ├── medical_records (appointment_id)
        │           │     └── prescriptions (medical_record_id)
        │           │           └── pharmacies (pharmacy_id)
        │           └── audit_logs (record_id)
        ├── patients (user_id)
        │     ├── appointments (patient_id)
        │     └── patient_documents (patient_id)
        └── admins (user_id)
```

---

### SQLAlchemy Models

File location: `backend/app/models/`

#### Base and Mixins (`backend/app/models/base.py`)

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import UUID, DateTime, func
import uuid

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

class SoftDeleteMixin(TimestampMixin):
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
```

#### Enums (`backend/app/models/enums.py`)

```python
import enum

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    PATIENT = "PATIENT"

class SlotStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"

class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
```

#### All Models

| Model | Table | Key columns |
|-------|-------|------------|
| `Tenant` | `tenants` | `id`, `name`, `domain` |
| `User` | `users` | `id`, `tenant_id`, `email`, `password_hash`, `role`, `is_active` |
| `Doctor` | `doctors` | `id`, `tenant_id`, `user_id`, `full_name`, `specialty`, `license_number`, `phone`, `date_of_birth` |
| `Patient` | `patients` | `id`, `tenant_id`, `user_id`, `full_name`, `phone`, `insurance_provider`, `insurance_policy_number`, `date_of_birth`, `gender`, `address_*` |
| `Admin` | `admins` | `id`, `tenant_id`, `user_id`, `full_name`, `phone` |
| `DoctorAvailability` | `doctor_availability` | `id`, `tenant_id`, `doctor_id`, `slot_time`, `status` (SlotStatus), `block_reason` |
| `Pharmacy` | `pharmacies` | `id`, `tenant_id`, `name`, `address`, `phone` |
| `Appointment` | `appointments` | `id`, `tenant_id`, `doctor_id`, `patient_id`, `slot_id`, `appointment_time`, `status` (AppointmentStatus), `notes` |
| `MedicalRecord` | `medical_records` | `id`, `tenant_id`, `appointment_id` (unique), `symptoms`, `diagnosis`, `lab_results` |
| `Prescription` | `prescriptions` | `id`, `tenant_id`, `medical_record_id` (unique), `pharmacy_id`, `medication_details` |
| `PatientDocument` | `patient_documents` | `id`, `tenant_id`, `patient_id`, `document_name`, `document_type`, `file_path` (S3 key), `signed_at` |
| `AuditLog` | `audit_logs` | `id`, `tenant_id`, `table_name`, `record_id`, `action_type`, `old_data` (JSONB), `new_data` (JSONB), `performed_by`, `performed_at` |

---

### Database Configuration (`backend/app/core/database.py`)

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

_engine = create_async_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    pool_size=1,       # Lambda: one connection per execution environment
    max_overflow=0,    # No extra connections — prevents RDS exhaustion at scale
)

AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

def get_engine():
    return _engine
```

**Why `pool_size=1, max_overflow=0`:** Lambda scales by spawning new execution environments. If each environment held multiple connections, a burst of 100 concurrent requests would open 400+ DB connections. One connection per environment keeps RDS within its `max_connections` limit regardless of Lambda concurrency.

---

### Required Indexes

```sql
-- Auth hot path
CREATE UNIQUE INDEX idx_users_tenant_email ON users(tenant_id, lower(email));
CREATE INDEX idx_users_tenant ON users(tenant_id);

-- Profile lookups
CREATE INDEX idx_doctors_tenant ON doctors(tenant_id);
CREATE INDEX idx_patients_tenant ON patients(tenant_id);

-- Appointment queries (patient/doctor dashboard, status filter)
CREATE INDEX idx_appointments_tenant ON appointments(tenant_id);
CREATE INDEX idx_appointments_patient ON appointments(patient_id, status);
CREATE INDEX idx_appointments_doctor ON appointments(doctor_id, status);
CREATE INDEX idx_appointments_time ON appointments(appointment_time);

-- Availability slot lookup
CREATE INDEX idx_availability_doctor_time ON doctor_availability(doctor_id, slot_time, status);

-- Document lookup by patient
CREATE INDEX idx_documents_patient ON patient_documents(patient_id, tenant_id);

-- Audit log queries
CREATE INDEX idx_audit_logs_tenant_time ON audit_logs(tenant_id, performed_at DESC);
CREATE INDEX idx_audit_logs_record ON audit_logs(record_id, table_name);
```

---

### Hot-Path Query Patterns

| Endpoint | Query pattern | Key index |
|----------|--------------|-----------|
| Login | `SELECT users WHERE tenant_id=? AND lower(email)=?` | `idx_users_tenant_email` |
| Patient appointments | `SELECT appointments WHERE patient_id=? AND status IN (...)` | `idx_appointments_patient` |
| Doctor today's appointments | `SELECT appointments WHERE doctor_id=? AND DATE(appointment_time)=today` | `idx_appointments_doctor` |
| Available slots | `SELECT doctor_availability WHERE doctor_id=? AND slot_time>=? AND status='AVAILABLE'` | `idx_availability_doctor_time` |
| Soft-delete filtering | All queries include `WHERE deleted_at IS NULL` | (covered by above indexes) |

---

### Schema Initialization

**Local development:** Set `DB_SCHEMA_INIT_ON_STARTUP=true` in `.env`. FastAPI calls `Base.metadata.create_all()` on startup.

**Production (Lambda):** Set `DB_SCHEMA_INIT_ON_STARTUP=false`. Schema must already exist via SQL migration (see `01-database/02-migrations-seeds.md`).

```python
# backend/app/main.py — startup handler
if settings.db_schema_init_on_startup:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

---

### Deliverables

- `backend/app/models/` — one file per model or a single `models.py`
- `backend/app/models/base.py` — `Base`, `TimestampMixin`, `SoftDeleteMixin`
- `backend/app/models/enums.py` — `UserRole`, `SlotStatus`, `AppointmentStatus`
- `backend/app/core/database.py` — engine, session factory, `get_db()` dependency, `get_engine()`
- `backend/docs/database-model.md` — ERD-level summary with entity relationships

### Acceptance Criteria

- All 12 models import cleanly.
- `get_db()` yields a valid `AsyncSession`.
- Engine uses `pool_size=1, max_overflow=0`.
- `DB_SCHEMA_INIT_ON_STARTUP=true` creates all tables on a fresh database.
- All soft-deletable models include `deleted_at` and `deleted_by`.
- No query is written without a `tenant_id` filter.
