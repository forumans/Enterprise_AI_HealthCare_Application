# Prompt: Database Schema Delivery and Seeding

## Prompt

You are responsible for database schema delivery and seed data in `backend/`. Implement a migration-first workflow using plain SQL files and safe seed data generation. This project does NOT use Alembic — schema is managed via versioned SQL scripts applied manually or in CI.

---

### Schema Delivery Strategy

There are two modes, controlled by the `DB_SCHEMA_INIT_ON_STARTUP` environment variable:

| Mode | When used | Behavior |
|------|-----------|---------|
| `DB_SCHEMA_INIT_ON_STARTUP=true` | Local development only | FastAPI auto-creates all tables on startup via SQLAlchemy `create_all` |
| `DB_SCHEMA_INIT_ON_STARTUP=false` | Production (Lambda) | Tables must already exist; schema managed via SQL migration scripts |

**Never set `DB_SCHEMA_INIT_ON_STARTUP=true` in production.** The Lambda function must start against a pre-existing schema.

---

### Migration File Conventions

Location: `backend/migrations/`

Naming: `NNN_description.sql` where `NNN` is a zero-padded sequence number.

```
backend/migrations/
├── 001_initial_schema.sql        # All tables, enums, indexes, foreign keys
├── 002_add_pharmacy_table.sql    # Example additive migration
└── 003_add_slot_block_reason.sql # Example column addition
```

Each migration file must:
- Be idempotent where possible (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`)
- Only add or modify — never DROP a column or table in the same migration that adds new ones
- Be backward-compatible with the previous running Lambda version (old code + new schema must work)
- Apply in order — `001` before `002` before `003`

---

### Initial Schema (`001_initial_schema.sql`)

The initial migration must create all entities in dependency order:

```sql
-- 1. Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Enums
CREATE TYPE user_role AS ENUM ('ADMIN', 'DOCTOR', 'PATIENT');
CREATE TYPE slot_status AS ENUM ('AVAILABLE', 'BOOKED', 'BLOCKED');
CREATE TYPE appointment_status AS ENUM ('SCHEDULED', 'CONFIRMED', 'CANCELLED', 'COMPLETED');

-- 3. tenants (root entity, no FK dependencies)
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 4. users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL,
    password_hash TEXT NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(id),
    UNIQUE (tenant_id, email)
);

-- 5. doctors
CREATE TABLE IF NOT EXISTS doctors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id),
    full_name VARCHAR(255) NOT NULL,
    specialty VARCHAR(255),
    license_number VARCHAR(100),
    phone VARCHAR(20),
    date_of_birth DATE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(id)
);

-- 6. patients
CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id),
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    insurance_provider VARCHAR(255),
    insurance_policy_number VARCHAR(255),
    date_of_birth DATE,
    gender VARCHAR(20),
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(id)
);

-- 7. admins
CREATE TABLE IF NOT EXISTS admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id),
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(id)
);

-- 8. doctor_availability
CREATE TABLE IF NOT EXISTS doctor_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    doctor_id UUID NOT NULL REFERENCES doctors(id),
    slot_time TIMESTAMP NOT NULL,
    status slot_status NOT NULL DEFAULT 'AVAILABLE',
    block_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 9. pharmacies
CREATE TABLE IF NOT EXISTS pharmacies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    address TEXT,
    phone TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(id)
);

-- 10. appointments
CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    doctor_id UUID NOT NULL REFERENCES doctors(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    slot_id UUID REFERENCES doctor_availability(id),
    appointment_time TIMESTAMP NOT NULL,
    status appointment_status NOT NULL DEFAULT 'SCHEDULED',
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(id)
);

-- 11. medical_records
CREATE TABLE IF NOT EXISTS medical_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    appointment_id UUID NOT NULL UNIQUE REFERENCES appointments(id),
    symptoms TEXT,
    diagnosis TEXT,
    lab_results TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(id)
);

-- 12. prescriptions
CREATE TABLE IF NOT EXISTS prescriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    medical_record_id UUID NOT NULL UNIQUE REFERENCES medical_records(id),
    pharmacy_id UUID REFERENCES pharmacies(id),
    medication_details TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(id)
);

-- 13. patient_documents
CREATE TABLE IF NOT EXISTS patient_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    patient_id UUID NOT NULL REFERENCES patients(id),
    document_name VARCHAR(255) NOT NULL,
    document_type VARCHAR(100),
    file_path TEXT NOT NULL,   -- S3 object key
    signed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(id)
);

-- 14. audit_logs (immutable — no soft delete)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action_type VARCHAR(20) NOT NULL,  -- INSERT, UPDATE, DELETE
    old_data JSONB,
    new_data JSONB,
    performed_by UUID REFERENCES users(id),
    performed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_users_tenant_email ON users(tenant_id, lower(email));
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_doctors_tenant ON doctors(tenant_id);
CREATE INDEX IF NOT EXISTS idx_patients_tenant ON patients(tenant_id);
CREATE INDEX IF NOT EXISTS idx_appointments_tenant ON appointments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);
CREATE INDEX IF NOT EXISTS idx_doctor_availability_doctor ON doctor_availability(doctor_id, slot_time);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id, performed_at);
```

---

### Applying Migrations

**Local development:**
```bash
psql -U healthcare_user -d healthcare_saas_db_local \
  -f migrations/001_initial_schema.sql
```

**Production (before each Lambda deploy):**
```bash
psql -h <rds-endpoint> -U <user> -d <dbname> \
  -f migrations/001_initial_schema.sql
# Apply any newer migration files in order:
# -f migrations/002_*.sql
# -f migrations/003_*.sql
```

**CI/CD — apply in GitHub Actions before `sam deploy`:**
```bash
psql -h $RDS_ENDPOINT -U $DB_USER -d $DB_NAME \
  -f healthcare_saas_app/backend/migrations/001_initial_schema.sql
```

---

### Seed Data

**Purpose:** Non-PHI seed data for local development and integration tests.

**Location:** `backend/scripts/`

```
backend/scripts/
├── seed_dev_data.py       # Creates tenant, admin user, sample doctor and patient
└── seed_test_data.py      # Minimal fixtures for test isolation
```

**Rules:**
- No real patient-identifiable data (names, emails, phone numbers must be clearly synthetic)
- Seeds must be deterministic — running twice produces the same state (use upsert, not plain insert)
- Default credentials for seed users must be clearly marked as development-only and must not pass password complexity requirements for production

**Example seed user structure:**
```python
# seed_dev_data.py
SEED_TENANT = {"name": "Demo Clinic", "domain": "demo.local"}
SEED_ADMIN = {"email": "admin@demo.local", "password": "DevOnly!123", "full_name": "Demo Admin"}
SEED_DOCTOR = {"email": "doctor@demo.local", "password": "DevOnly!123", "full_name": "Demo Doctor", "specialty": "General Practice"}
SEED_PATIENT = {"email": "patient@demo.local", "password": "DevOnly!123", "full_name": "Demo Patient"}
```

---

### Constraints

- No `alembic` dependency — do not add it to `requirements.txt`
- No destructive schema operations (`DROP COLUMN`, `DROP TABLE`) without a corresponding explicit migration step
- Test fixtures avoid any real PHI — names, emails, and IDs must be obviously synthetic
- Seeding must not fail if the data already exists (use `ON CONFLICT DO NOTHING` or equivalent)

---

### Deliverables

- `backend/migrations/001_initial_schema.sql` — full initial schema
- `backend/scripts/seed_dev_data.py` — dev environment seed script
- `backend/scripts/seed_test_data.py` — test fixture seed script
- `backend/docs/migrations-runbook.md` — how to author, apply, and verify migrations

### Acceptance Criteria

- Running `001_initial_schema.sql` against an empty PostgreSQL database creates all 14 tables
- Running it again on the same database produces no errors (`IF NOT EXISTS` throughout)
- `seed_dev_data.py` completes without errors on a freshly migrated database
- Running seeds twice is idempotent
- No Alembic imports or configuration files exist in the codebase
