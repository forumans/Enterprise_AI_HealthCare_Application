## ADDED Requirements

### Requirement: No Alembic — SQL-file-based migrations only
The system SHALL manage schema changes exclusively through versioned SQL files in `backend/migrations/`. Alembic SHALL NOT be used. `alembic` SHALL NOT appear in `requirements.txt`.

#### Scenario: New migration authored
- **GIVEN** a schema change is required
- **WHEN** a developer authors the migration
- **THEN** the change SHALL be written as a new `.sql` file named `NNN_description.sql` in `backend/migrations/`, where `NNN` is a zero-padded sequence number

#### Scenario: Alembic not present
- **GIVEN** the project repository
- **WHEN** `requirements.txt` is inspected
- **THEN** `alembic` SHALL NOT appear as a dependency

---

### Requirement: Migration file idempotency
Each migration file SHALL use `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and `CREATE TYPE IF NOT EXISTS` guards so that running the same file twice against an already-migrated database produces no errors.

#### Scenario: Re-run migration on existing schema
- **GIVEN** `001_initial_schema.sql` has already been applied to a database
- **WHEN** the same file is applied again (e.g. in CI retries)
- **THEN** the system SHALL complete without errors and the schema SHALL be unchanged

---

### Requirement: Backward-compatible migrations
Each migration SHALL be backward-compatible with the previous running Lambda version. Old application code SHALL continue to function against the new schema. A single migration file SHALL NOT both add a new column and drop an existing column.

#### Scenario: Deploy with zero downtime
- **GIVEN** a migration that adds a new nullable column to `appointments`
- **WHEN** the migration is applied while the previous Lambda version is still serving traffic
- **THEN** the previous Lambda code SHALL continue to operate correctly because it does not reference the new column

---

### Requirement: Migrations applied before Lambda deployment
In CI/CD, database migrations SHALL be applied to RDS before the new Lambda code is deployed. The migration step SHALL use `psql` with credentials from GitHub secrets.

#### Scenario: CI/CD migration step ordering
- **GIVEN** a GitHub Actions workflow for the backend
- **WHEN** the pipeline runs on a push to `main`
- **THEN** the `psql` migration step SHALL complete successfully before the `sam deploy` step begins

---

### Requirement: Initial schema covers all 14 tables
The `001_initial_schema.sql` migration SHALL create all 14 tables in correct foreign-key dependency order: `tenants`, `users`, `doctors`, `patients`, `admins`, `doctor_availability`, `pharmacies`, `appointments`, `medical_records`, `prescriptions`, `patient_documents`, `audit_logs`, and all required indexes and PostgreSQL enum types.

#### Scenario: Fresh database migration
- **GIVEN** an empty PostgreSQL database
- **WHEN** `001_initial_schema.sql` is applied via `psql`
- **THEN** all 14 tables SHALL exist, all enum types SHALL be created, and all required indexes SHALL be present

#### Scenario: Verify table count
- **GIVEN** a database where `001_initial_schema.sql` has been applied
- **WHEN** `\dt` is run in psql
- **THEN** at least 14 tables SHALL be listed including `tenants`, `users`, `appointments`, and `audit_logs`

---

### Requirement: Deterministic seed data
Seed scripts SHALL be deterministic: running the same script twice SHALL produce the same state. Seeds SHALL use `ON CONFLICT DO NOTHING` or upsert semantics. Seed data SHALL use clearly synthetic, non-PHI values (e.g. `demo.local` email domain).

#### Scenario: Seed script run twice
- **GIVEN** a freshly migrated database
- **WHEN** `seed_dev_data.py` is run twice consecutively
- **THEN** no errors SHALL occur and the database SHALL contain exactly the same number of seeded rows after the second run as after the first

#### Scenario: Seed data is non-PHI
- **GIVEN** the seed scripts in `backend/scripts/`
- **WHEN** the seed data values are reviewed
- **THEN** all email addresses SHALL use the `demo.local` domain, all names SHALL be clearly synthetic (e.g. "Demo Doctor"), and no real patient-identifiable information SHALL appear

---

### Requirement: Separate dev and test seed scripts
The system SHALL provide `seed_dev_data.py` for local development (creates a tenant, admin, doctor, and patient) and `seed_test_data.py` for integration test fixtures. Test seed data SHALL be minimal and scoped to test isolation.

#### Scenario: Dev seed creates usable local environment
- **GIVEN** a freshly migrated local database
- **WHEN** `seed_dev_data.py` is executed
- **THEN** a demo tenant, admin user, doctor user, and patient user SHALL be created and the application SHALL be immediately usable for local testing

#### Scenario: Test seed is minimal
- **GIVEN** an integration test suite
- **WHEN** `seed_test_data.py` is referenced as a fixture
- **THEN** it SHALL create only the minimum data required for test isolation and SHALL NOT create unrelated records that could cause test interference
