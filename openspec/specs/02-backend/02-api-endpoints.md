## ADDED Requirements

### Requirement: Dual-prefix route registration
Every route SHALL be registered twice: once at its base path (e.g. `/health`) and once with the `/api` prefix (e.g. `/api/health`). This supports CloudFront proxying `/api/*` to API Gateway while also allowing direct Lambda invocation without the prefix.

#### Scenario: API route accessible with /api prefix
- **GIVEN** a running application
- **WHEN** `GET /api/health` is requested
- **THEN** the system SHALL return the same response as `GET /health`

#### Scenario: API route accessible without /api prefix
- **GIVEN** a running application
- **WHEN** `GET /health` is requested
- **THEN** the system SHALL return `{"status": "healthy", "database": "connected"}`

---

### Requirement: Health endpoints
The system SHALL expose three health endpoints: `GET /health` (liveness + DB check), `GET /health/ready` (readiness check including database), `GET /health/live` (simple liveness, no DB check). WHEN the database is unreachable, `GET /health` and `GET /health/ready` SHALL return status 503.

#### Scenario: Healthy system
- **GIVEN** the application is running and RDS is reachable
- **WHEN** `GET /health` is called
- **THEN** the system SHALL return `{"status": "healthy", "database": "connected"}` with status 200

#### Scenario: Database unreachable
- **GIVEN** the database connection is unavailable
- **WHEN** `GET /health` is called
- **THEN** the system SHALL return `{"status": "unhealthy", "database": "disconnected"}` with status 503

---

### Requirement: Appointment booking creates atomic slot reservation
WHEN a patient books an appointment, the system SHALL atomically: (1) verify the `doctor_availability` slot is `AVAILABLE` and belongs to the same tenant, (2) create the `appointments` row with status `SCHEDULED`, and (3) update the slot status to `BOOKED`. Both writes SHALL occur in a single database transaction.

#### Scenario: Successful appointment booking
- **GIVEN** an AVAILABLE slot for a doctor in the same tenant as the patient
- **WHEN** `POST /appointments` is called by an authenticated PATIENT
- **THEN** an appointment SHALL be created with status SCHEDULED and the slot status SHALL become BOOKED in the same transaction

#### Scenario: Booking an already-booked slot
- **GIVEN** a slot with status BOOKED
- **WHEN** a second patient attempts to book the same slot
- **THEN** the system SHALL return 409 or 422 and SHALL NOT create a duplicate appointment

---

### Requirement: Appointment cancellation reverts slot
WHEN an appointment is cancelled, the system SHALL set the appointment status to `CANCELLED` and SHALL revert the linked `doctor_availability` slot status from `BOOKED` back to `AVAILABLE`, all within a single database transaction.

#### Scenario: Patient cancels appointment
- **GIVEN** a SCHEDULED or CONFIRMED appointment with a linked slot
- **WHEN** the owning patient calls `DELETE /appointments/{id}`
- **THEN** the appointment status SHALL become CANCELLED and the slot SHALL revert to AVAILABLE

#### Scenario: Wrong patient cannot cancel
- **GIVEN** an appointment owned by Patient A
- **WHEN** Patient B calls `DELETE /appointments/{appointment_a_id}`
- **THEN** the system SHALL return 403 or 404 and SHALL NOT cancel the appointment

---

### Requirement: Appointment status lifecycle enforcement
Appointment status SHALL follow the lifecycle: `SCHEDULED → CONFIRMED → COMPLETED` with `CANCELLED` reachable from `SCHEDULED` or `CONFIRMED`. Transitions outside this path SHALL be rejected. Only DOCTOR or ADMIN SHALL call `PUT /appointments/{id}/status`.

#### Scenario: Doctor confirms appointment
- **GIVEN** an appointment in SCHEDULED status
- **WHEN** the assigned doctor calls `POST /appointments/{id}/confirm`
- **THEN** the appointment status SHALL become CONFIRMED

#### Scenario: Invalid status transition
- **GIVEN** an appointment in COMPLETED status
- **WHEN** any user attempts to set status back to SCHEDULED
- **THEN** the system SHALL return 422 and SHALL NOT update the appointment

---

### Requirement: Service layer isolates business logic
All business logic SHALL live in service classes under `backend/app/services/`. Route handlers SHALL only perform HTTP concerns: request validation, dependency injection, and response shaping. Service methods SHALL accept `AsyncSession` and `CurrentIdentity`; they SHALL NOT accept raw `Request` objects.

#### Scenario: Route delegates to service
- **GIVEN** a `POST /appointments` request with valid data
- **WHEN** the route handler executes
- **THEN** the route handler SHALL call `AppointmentService.book(payload)` for business logic and SHALL NOT contain direct database queries in the route function body

---

### Requirement: Audit log on every mutation
Every INSERT, UPDATE, and DELETE operation on a business entity SHALL result in an `AuditLog` entry written in the same database transaction. The audit entry SHALL capture `table_name`, `record_id`, `action_type`, `old_data` (JSONB), `new_data` (JSONB), `performed_by`, and `performed_at`. Audit logs SHALL be append-only and SHALL NOT be soft-deleted.

#### Scenario: User update is audited
- **GIVEN** an admin updating a user's profile
- **WHEN** the update transaction commits
- **THEN** an `audit_logs` row SHALL exist recording the old and new state, the action type `UPDATE`, and the admin's `user_id` as `performed_by`

#### Scenario: Audit log cannot be deleted
- **GIVEN** an audit log entry
- **WHEN** any service or admin action attempts to delete or soft-delete it
- **THEN** the system SHALL reject the operation — audit logs have no `deleted_at` column and no delete endpoint

---

### Requirement: All list endpoints scoped to tenant
Every list endpoint (users, appointments, doctors, patients, documents, etc.) SHALL filter results by the `tenant_id` from the authenticated user's JWT. Cross-tenant data SHALL never appear in any list response.

#### Scenario: Admin lists tenant users
- **GIVEN** two tenants with users in each
- **WHEN** an ADMIN from Tenant A calls `GET /admin/users`
- **THEN** the response SHALL contain only Tenant A users and SHALL NOT include any users from Tenant B

---

### Requirement: Document list returns presigned download URLs
WHEN a patient lists their uploaded documents via `GET /patient/documents`, each document entry in the response SHALL include a `download_url` field containing a presigned S3 GET URL valid for 1 hour. The URL SHALL allow the client to download the file directly from S3 without routing through Lambda.

#### Scenario: Document list with presigned URLs
- **GIVEN** a patient with one or more uploaded documents
- **WHEN** `GET /patient/documents` is called
- **THEN** each document object SHALL include a non-empty `download_url` that expires in 3600 seconds and can be used to download the file from S3 directly
