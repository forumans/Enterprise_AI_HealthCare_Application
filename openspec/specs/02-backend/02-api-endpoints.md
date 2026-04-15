# Prompt: API Endpoints and Service Layer

## Prompt

Implement all FastAPI routes and their corresponding service layer for this Healthcare SaaS backend. Every route is tenant-scoped and role-protected where appropriate.

---

### Route Structure

```
backend/app/api/routes/
├── auth.py          # register, login, forgot/reset password
├── doctors.py       # doctor profile, availability, registration
├── patients.py      # patient profile, medical history, prescriptions, documents
├── appointments.py  # book, list, cancel, confirm, complete
├── admin.py         # user management, reports, system
└── health.py        # /health, /health/ready, /health/live

backend/app/services/
├── auth_service.py
├── doctor_service.py
├── patient_service.py
├── appointment_service.py
└── admin_service.py
```

Business logic lives in services; routes handle only HTTP concerns (validation, auth, response shaping).

---

### Health Endpoints (Public)

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/health` | `{"status":"healthy","database":"connected","version":"1.0.0"}` or 503 |
| `GET` | `/health/ready` | `{"status":"ready","checks":{"database":true,"api":true}}` or 503 |
| `GET` | `/health/live` | `{"status":"alive","timestamp":"..."}` |

---

### Auth Endpoints (Public)

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `/auth/register` | `{email, password, full_name}` | `{user_id, email, role, tenant_id}` |
| `POST` | `/auth/login` | `{email, password}` | `{access_token, role, tenant_id, user_name, user_id}` |
| `POST` | `/auth/forgot-password` | `{email}` | `{message: "If account exists, reset link sent"}` |
| `POST` | `/auth/reset-password` | `{token, new_password}` | `{message: "Password updated"}` |

---

### Doctor Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/doctors` | Public | List all active doctors (id, name, specialty) |
| `POST` | `/doctors/register` | Public | Register a new doctor account |
| `GET` | `/doctors/me` | DOCTOR | Get own doctor profile |
| `PUT` | `/doctor/profile` | DOCTOR | Update own profile (specialty, phone, etc.) |
| `GET` | `/doctor/availability/{doctor_id}/ndays` | Public | Get available slots for doctor over N days |
| `POST` | `/doctor/availability` | DOCTOR | Create availability slots |
| `PUT` | `/doctor/availability/{slot_id}` | DOCTOR | Update slot status (BLOCKED, AVAILABLE) |
| `GET` | `/doctor/appointments/all` | DOCTOR | All appointments for this doctor |
| `GET` | `/doctor/appointments/today` | DOCTOR | Today's appointments |
| `GET` | `/doctor/appointments/upcoming` | DOCTOR | Upcoming appointments |
| `GET` | `/doctor/appointments/weekly` | DOCTOR | This week's appointments |

---

### Patient Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/patient/me` | PATIENT | Get own patient profile |
| `PUT` | `/patient/profile` | PATIENT | Update own profile |
| `GET` | `/patient/appointments/upcoming` | PATIENT | Upcoming appointments |
| `GET` | `/patient/medical-history` | PATIENT | List medical records for this patient |
| `GET` | `/patient/prescriptions` | PATIENT | List prescriptions for this patient |
| `GET` | `/patient/documents` | PATIENT | List uploaded documents (with presigned download URLs) |
| `POST` | `/patient/documents` | PATIENT | Upload a document (multipart/form-data) |

---

### Appointment Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/appointments` | PATIENT | Book an appointment `{doctor_id, slot_id, appointment_time, notes}` |
| `DELETE` | `/appointments/{id}` | PATIENT | Cancel own appointment (sets status=CANCELLED) |
| `PUT` | `/appointments/{id}/status` | DOCTOR, ADMIN | Update status `{status: CONFIRMED|COMPLETED|CANCELLED}` |
| `POST` | `/appointments/{id}/confirm` | DOCTOR | Confirm appointment |

**Appointment status lifecycle:**
```
SCHEDULED → CONFIRMED → COMPLETED
          ↘ CANCELLED
```

When an appointment is booked, the linked `doctor_availability` slot status changes from `AVAILABLE` → `BOOKED`.
When an appointment is cancelled, the slot reverts to `AVAILABLE`.

---

### Medical Records and Prescriptions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/medical-records` | DOCTOR | Create medical record for completed appointment `{appointment_id, symptoms, diagnosis, lab_results}` |
| `POST` | `/prescriptions` | DOCTOR | Create prescription `{medical_record_id, pharmacy_id, medication_details}` |
| `GET` | `/pharmacies` | DOCTOR, PATIENT, ADMIN | List available pharmacies |

---

### Admin Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/admin/register` | Public | Register new admin account |
| `GET` | `/admin/users` | ADMIN | List all users in tenant (with role/status filter) |
| `DELETE` | `/admin/users/{id}` | ADMIN | Soft-delete a user |
| `POST` | `/admin/users/{id}/restore` | ADMIN | Restore soft-deleted user |
| `POST` | `/admin/reset-password` | ADMIN | Reset any user's password `{user_id, new_password}` |
| `GET` | `/admin/appointments` | ADMIN | List all appointments in tenant |
| `GET` | `/admin/reports` | ADMIN | System-level metrics and counts |
| `GET` | `/admin/audit-logs` | ADMIN | Recent audit log entries |

---

### Standard Response Shapes

**Success (list):**
```json
[{ "id": "uuid", ... }]
```

**Success (single):**
```json
{ "id": "uuid", ... }
```

**Error:**
```json
{ "detail": "Human-readable error message" }
```

**Validation error (422):**
```json
{
  "detail": [
    { "loc": ["body", "email"], "msg": "invalid email", "type": "value_error" }
  ]
}
```

---

### Service Layer Pattern

Services receive the `AsyncSession` and `CurrentIdentity` (tenant + role). They never accept raw request objects.

```python
# backend/app/services/appointment_service.py
class AppointmentService:
    def __init__(self, db: AsyncSession, identity: CurrentIdentity): ...

    async def book(self, payload: BookAppointmentSchema) -> Appointment:
        # 1. Verify slot is AVAILABLE and belongs to same tenant
        # 2. Create appointment record
        # 3. Update slot status to BOOKED
        # 4. Write audit log entry
        # All in one transaction
        ...

    async def cancel(self, appointment_id: uuid.UUID) -> Appointment:
        # 1. Verify appointment belongs to this patient's tenant
        # 2. Verify patient owns the appointment (or is ADMIN)
        # 3. Set status=CANCELLED, revert slot to AVAILABLE
        # 4. Write audit log
        ...
```

---

### Audit Logging

Every mutation (INSERT, UPDATE, DELETE) must write an `AuditLog` entry:

```python
async def write_audit(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    table_name: str,
    record_id: uuid.UUID,
    action_type: str,          # INSERT | UPDATE | DELETE
    old_data: dict | None,
    new_data: dict | None,
    performed_by: uuid.UUID,
): ...
```

Audit logs are append-only — never soft-deleted.

---

### Deliverables

- `backend/app/api/routes/` — all route files listed above
- `backend/app/services/` — all service files with business logic
- `backend/app/api/schemas.py` (or per-domain schema files) — Pydantic request/response models
- `backend/tests/` — tests for each route group covering happy path + auth errors + validation

### Acceptance Criteria

- Every route has a corresponding test.
- A PATIENT token cannot call any admin or doctor-only endpoint (returns 403).
- All list endpoints filter by `tenant_id` — cross-tenant data is never returned.
- Booking an appointment marks the slot as BOOKED in the same transaction.
- Cancelling an appointment reverts the slot to AVAILABLE.
- Every mutation writes an audit log entry.
