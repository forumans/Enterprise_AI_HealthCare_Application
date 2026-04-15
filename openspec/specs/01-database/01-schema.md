## ADDED Requirements

### Requirement: UUID primary keys
Every table SHALL use a UUID primary key with a server-side default of `gen_random_uuid()`. No auto-increment integer IDs are permitted.

#### Scenario: New record created
- **GIVEN** a database table with a UUID primary key column
- **WHEN** a new row is inserted without specifying an ID
- **THEN** the database SHALL generate a UUID automatically using `gen_random_uuid()`

---

### Requirement: Tenant isolation column
Every tenant-owned table SHALL include a `tenant_id UUID NOT NULL` column with a foreign key reference to `tenants(id)`. Every query against a tenant-owned table SHALL include a `WHERE tenant_id = <current_tenant>` filter.

#### Scenario: Query scoped to tenant
- **GIVEN** an authenticated request with a `tenant_id` claim in the JWT
- **WHEN** any service method queries a tenant-owned table
- **THEN** the query SHALL include `WHERE tenant_id = <jwt.tenant_id>` and SHALL NOT return rows belonging to any other tenant

#### Scenario: Cross-tenant access attempt
- **GIVEN** a valid JWT for Tenant A
- **WHEN** a request attempts to read or modify a record owned by Tenant B
- **THEN** the system SHALL return no results or a 403/404 response and SHALL NOT expose Tenant B data

---

### Requirement: Created-at timestamp
Every table SHALL include a `created_at TIMESTAMP NOT NULL DEFAULT NOW()` column. No `updated_at` column is required; change history is tracked via audit logs.

#### Scenario: Record creation timestamp
- **GIVEN** a table with a `created_at` column
- **WHEN** a new row is inserted
- **THEN** `created_at` SHALL be populated automatically by the database default and SHALL NOT be null

---

### Requirement: Soft-delete pattern
All mutable business entity tables SHALL include `deleted_at TIMESTAMP` and `deleted_by UUID` columns. Logical deletion SHALL set `deleted_at` to the current timestamp and `deleted_by` to the acting user's ID. All queries against soft-deletable tables SHALL filter with `WHERE deleted_at IS NULL`. Audit log records are immutable and SHALL NOT have soft-delete columns.

#### Scenario: Soft-delete a user
- **GIVEN** an active user record with `deleted_at = NULL`
- **WHEN** an admin deletes the user
- **THEN** the system SHALL set `deleted_at = NOW()` and `deleted_by = <admin_user_id>` and SHALL NOT physically remove the row

#### Scenario: Soft-deleted record excluded from queries
- **GIVEN** a user whose `deleted_at` is not null
- **WHEN** any list or lookup query runs against the users table
- **THEN** the query SHALL include `WHERE deleted_at IS NULL` and the deleted user SHALL NOT appear in results

#### Scenario: Restore soft-deleted user
- **GIVEN** a user record with `deleted_at` set
- **WHEN** an admin restores the user
- **THEN** the system SHALL set `deleted_at = NULL` and `deleted_by = NULL`

---

### Requirement: Entity relationship hierarchy
The system SHALL implement the following entity hierarchy: `tenants` → `users` → `doctors | patients | admins`. Appointments SHALL reference both `doctor_id` and `patient_id`. Medical records SHALL reference `appointment_id` (one-to-one). Prescriptions SHALL reference `medical_record_id` (one-to-one) and optionally `pharmacy_id`. Patient documents SHALL reference `patient_id`.

#### Scenario: Doctor profile creation
- **GIVEN** a registered user with role DOCTOR
- **WHEN** the doctor registration flow completes
- **THEN** the system SHALL create a `doctors` row linked to the `users` row via `user_id` with a `UNIQUE` constraint

#### Scenario: Appointment referential integrity
- **GIVEN** a valid doctor and patient in the same tenant
- **WHEN** an appointment is booked
- **THEN** the `appointments` row SHALL reference valid `doctor_id`, `patient_id`, and optionally `slot_id` foreign keys

---

### Requirement: Database connection pool for Lambda
The SQLAlchemy async engine SHALL be configured with `pool_size=1` and `max_overflow=0`. The engine SHALL use `pool_pre_ping=True` to detect stale connections after Lambda execution environment hibernation.

#### Scenario: Lambda concurrency scale-out
- **GIVEN** 100 concurrent Lambda invocations each with their own execution environment
- **WHEN** each environment initialises its database engine
- **THEN** each environment SHALL hold at most 1 database connection, keeping total RDS connections at or below the Lambda concurrency count

#### Scenario: Stale connection after idle period
- **GIVEN** a Lambda execution environment that has been idle for an extended period
- **WHEN** the next request arrives and the engine attempts to use an existing connection
- **THEN** `pool_pre_ping=True` SHALL detect the stale connection and establish a fresh one before executing the query

---

### Requirement: Schema initialisation mode
The system SHALL support two schema delivery modes controlled by the `DB_SCHEMA_INIT_ON_STARTUP` environment variable. WHEN `DB_SCHEMA_INIT_ON_STARTUP=true` the application SHALL call `Base.metadata.create_all()` on startup. WHEN `DB_SCHEMA_INIT_ON_STARTUP=false` the application SHALL skip `create_all()` and assume the schema already exists. The production Lambda deployment SHALL always run with `DB_SCHEMA_INIT_ON_STARTUP=false`.

#### Scenario: Local development startup
- **GIVEN** `DB_SCHEMA_INIT_ON_STARTUP=true` in the local `.env` file
- **WHEN** the FastAPI application starts
- **THEN** the system SHALL create all tables if they do not exist, enabling a fresh local database to be used without running SQL migration scripts manually

#### Scenario: Lambda cold start
- **GIVEN** `DB_SCHEMA_INIT_ON_STARTUP=false` set in the SAM template environment variables
- **WHEN** the Lambda function initialises
- **THEN** the system SHALL NOT attempt `create_all()` and SHALL assume the schema was applied by the SQL migration pipeline before deployment

---

### Requirement: Required database indexes
The system SHALL create indexes for all hot query paths: `idx_users_tenant_email` (unique, on `tenant_id, lower(email)`), `idx_appointments_patient` (on `patient_id, status`), `idx_appointments_doctor` (on `doctor_id, status`), `idx_availability_doctor_time` (on `doctor_id, slot_time, status`), and `idx_audit_logs_tenant_time` (on `tenant_id, performed_at DESC`).

#### Scenario: Login query performance
- **GIVEN** the `idx_users_tenant_email` unique index exists
- **WHEN** the login service executes `SELECT * FROM users WHERE tenant_id=? AND lower(email)=?`
- **THEN** the query SHALL use the index and SHALL NOT perform a full table scan

#### Scenario: Patient appointment list performance
- **GIVEN** the `idx_appointments_patient` index exists
- **WHEN** the patient appointments endpoint queries `WHERE patient_id=? AND status IN (...)`
- **THEN** the query SHALL use the covering index and return results efficiently even with a large appointments table

---

### Requirement: SQLAlchemy model structure
The system SHALL define all models using SQLAlchemy 2.0 declarative style with `Mapped` type annotations. A `TimestampMixin` SHALL provide `created_at`. A `SoftDeleteMixin` SHALL extend `TimestampMixin` and provide `deleted_at` and `deleted_by`. All business entity models SHALL inherit from `SoftDeleteMixin`.

#### Scenario: Model import
- **GIVEN** the `backend/app/models/` directory
- **WHEN** any model file is imported
- **THEN** all model classes SHALL be importable without errors and SHALL be registered with the SQLAlchemy `Base` metadata

#### Scenario: Enum usage in models
- **GIVEN** the `UserRole`, `SlotStatus`, and `AppointmentStatus` Python enums defined in `models/enums.py`
- **WHEN** a model column uses one of these enums as its type
- **THEN** the column SHALL only accept values defined in the enum and SHALL map to the corresponding PostgreSQL enum type
