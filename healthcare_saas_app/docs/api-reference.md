# API Reference

All endpoints are available under both `/api/<path>` (production, proxied through CloudFront) and `/<path>` (direct, for backward compatibility). Examples use the `/api` prefix.

Authentication is via `Authorization: Bearer <token>` header unless marked **Public**.

---

## Authentication

### POST `/api/auth/register`
**Public** — Register a new patient account.

**Request body:**
```json
{
  "email": "patient@example.com",
  "password": "securepassword",
  "full_name": "Jane Smith",
  "phone": "+1-555-0100",
  "date_of_birth": "1990-05-15",
  "gender": "Female",
  "insurance_provider": "BlueCross",
  "insurance_policy_number": "BC-12345"
}
```

**Response `201`:**
```json
{ "id": "uuid", "email": "patient@example.com", "role": "PATIENT" }
```

---

### POST `/api/auth/login`
**Public** — Authenticate and receive a JWT token.

**Request body:**
```json
{ "email": "user@example.com", "password": "securepassword" }
```

**Response `200`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiJ9...",
  "role": "PATIENT | DOCTOR | ADMIN",
  "tenant_id": "uuid",
  "user_name": "Jane Smith",
  "insurance_provider": "BlueCross",
  "insurance_policy_id": "BC-12345"
}
```

---

### POST `/api/auth/forgot-password`
**Public** — Request a password reset link.

```json
{ "email": "user@example.com" }
```

---

### POST `/api/auth/reset-password`
**Public** — Reset password using a reset token.

```json
{ "token": "reset-token", "new_password": "newpassword" }
```

---

## Doctors

### GET `/api/doctors`
**Public** — List all active doctors.

**Response `200`:** Array of doctor objects with `id`, `full_name`, `specialty`, `license_number`.

---

### POST `/api/doctors/register`
**Public** — Doctor self-registration.

**Request body:**
```json
{
  "email": "doctor@example.com",
  "password": "securepassword",
  "full_name": "Dr. John Carter",
  "specialty": "Cardiology",
  "license_number": "LIC-98765",
  "phone": "+1-555-0200"
}
```

---

### GET `/api/doctors/me`
**DOCTOR** — Get the authenticated doctor's profile.

---

### PUT `/api/doctor/profile`
**DOCTOR** — Update the authenticated doctor's profile.

---

### GET `/api/doctor/appointments/today`
**DOCTOR** — Get all appointments scheduled for today.

---

### GET `/api/doctor/appointments/all`
**DOCTOR** — Get all appointments (all time).

---

### GET `/api/doctor/appointments/upcoming`
**DOCTOR** — Get upcoming (future) appointments.

---

### GET `/api/doctor/appointments/weekly`
**DOCTOR** — Get appointments for the current week.

---

### GET `/api/doctor/appointments/{appointment_id}`
**DOCTOR** — Get details of a specific appointment.

---

## Availability

### GET `/api/doctor/availability/{doctor_id}/ndays`
**Public** — Get the next 30 days of availability slots for a doctor. Auto-creates slots if none exist.

**Query params:** `?days=30` (optional, default 30)

**Response `200`:** Array of availability slots:
```json
[
  {
    "id": "uuid",
    "slot_time": "2026-04-15T09:00:00",
    "status": "AVAILABLE | BOOKED | BLOCKED"
  }
]
```

---

### GET `/api/doctor/availability/{doctor_id}/all`
**DOCTOR / ADMIN** — Get all availability slots (available and booked).

---

### POST `/api/doctor/availability`
**DOCTOR** — Create or update an availability slot.

```json
{
  "slot_time": "2026-04-15T09:00:00",
  "status": "AVAILABLE"
}
```

---

### DELETE `/api/doctor/availability/{availability_id}`
**DOCTOR** — Delete an availability slot.

---

## Appointments

### POST `/api/appointments`
**PATIENT** — Book an appointment.

```json
{
  "doctor_id": "uuid",
  "slot_id": "uuid",
  "appointment_time": "2026-04-15T09:00:00",
  "notes": "Follow-up for blood pressure"
}
```

**Response `201`:** `{ "id": "uuid" }`

---

### GET `/api/appointments`
**PATIENT / DOCTOR / ADMIN** — List appointments for the authenticated user.

---

### GET `/api/appointments/all`
**ADMIN** — List all appointments across all patients and doctors.

---

### PUT `/api/appointments/{appointment_id}/status`
**DOCTOR** — Update appointment status.

```json
{ "status": "CONFIRMED | COMPLETED | CANCELLED" }
```

---

### POST `/api/appointments/{appointment_id}/confirm`
**DOCTOR** — Confirm a scheduled appointment.

---

### DELETE `/api/appointments/{appointment_id}`
**PATIENT** — Cancel an appointment (soft delete).

---

## Patients

### POST `/api/patients`
**ADMIN** — Create a patient record.

---

### GET `/api/patients`
**ADMIN / DOCTOR** — List all patients in the tenant.

---

### GET `/api/patients/search`
**DOCTOR / ADMIN** — Search patients by name.

**Query params:** `?q=Jane`

---

### GET `/api/patient/me`
**PATIENT** — Get the authenticated patient's profile.

---

### GET `/api/patient/appointments/upcoming`
**PATIENT** — Get the authenticated patient's upcoming appointments.

---

### GET `/api/patient/medical-history`
**PATIENT** — Get all medical records for the authenticated patient.

---

### GET `/api/patient/prescriptions`
**PATIENT** — Get all prescriptions for the authenticated patient.

---

### GET `/api/patient/documents`
**PATIENT** — List uploaded documents for the authenticated patient.

---

### POST `/api/patient/documents`
**PATIENT** — Upload a document (multipart/form-data).

**Form fields:** `file` (binary)

**Response `201`:** `{ "message": "Document uploaded" }`

---

## Medical Records

### POST `/api/medical-records`
**DOCTOR** — Create a medical record for an appointment.

```json
{
  "appointment_id": "uuid",
  "patient_id": "uuid",
  "diagnosis": "Hypertension stage 1",
  "notes": "Patient reports occasional headaches. Prescribed lisinopril.",
  "lab_results": "Blood pressure: 145/90"
}
```

**Response `201`:** `{ "id": "uuid" }`

---

### GET `/api/medical-records/{appointment_id}`
**ADMIN / DOCTOR / PATIENT** — Get the medical record for a specific appointment.

---

## Prescriptions

### POST `/api/prescriptions`
**DOCTOR / ADMIN** — Create a prescription linked to a medical record.

```json
{
  "medical_record_id": "uuid",
  "pharmacy_id": "uuid",
  "medication_details": "Lisinopril 10mg — take once daily with water"
}
```

---

### GET `/api/prescriptions/pharmacies`
**DOCTOR / ADMIN / PATIENT** — List available pharmacies.

---

## Documents

### POST `/api/documents`
**ADMIN / DOCTOR / PATIENT** — Upload a document for a specific patient.

**Query params:** `?patient_id=<uuid>`

**Form fields:** `file` (binary)

**Response `201`:** `{ "id": "uuid" }`

---

### GET `/api/documents/{patient_id}`
**ADMIN / DOCTOR / PATIENT** — List documents for a patient. Returns presigned S3 download URLs (1-hour expiry).

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "document_name": "bloodwork_results.pdf",
    "document_type": "application/pdf",
    "download_url": "https://s3.amazonaws.com/...?X-Amz-Signature=...",
    "signed_at": "2026-04-13T10:00:00"
  }
]
```

---

## Admin

### GET `/api/admin/users`
**ADMIN** — List all users (paginated).

**Query params:** `?page=1&page_size=20`

---

### POST `/api/admin/users`
**ADMIN** — Create a user account.

---

### DELETE `/api/admin/users/{user_id}`
**ADMIN** — Soft-delete a user.

---

### POST `/api/admin/users/{user_id}/restore`
**ADMIN** — Restore a soft-deleted user.

---

### POST `/api/admin/reset-password`
**ADMIN** — Reset any user's password.

```json
{ "user_id": "uuid", "new_password": "newpassword" }
```

---

### GET `/api/admin/appointments`
**ADMIN** — List all appointments across all tenants (paginated).

---

### GET `/api/admin/reports`
**ADMIN** — Get system-wide metrics and reports.

---

### GET `/api/admin/appointments/metrics`
**ADMIN** — Get appointment-specific metrics.

---

### GET `/api/admin/roles`
**ADMIN** — List available roles (`ADMIN`, `DOCTOR`, `PATIENT`).

---

### POST `/api/admin/register`
**Public** — Register a new admin account.

---

## Audit Logs

### GET `/api/audit-logs`
**ADMIN** — List audit log entries.

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "table_name": "appointments",
    "record_id": "uuid",
    "action_type": "INSERT | UPDATE | DELETE",
    "old_data": null,
    "new_data": { "patient_id": "uuid", "status": "SCHEDULED" },
    "performed_by": "uuid",
    "performed_at": "2026-04-13T10:00:00"
  }
]
```

---

## Tenants

### GET `/api/tenants`
**ADMIN** — List all tenants.

---

## Health

### GET `/api/health`
**Public** — Basic health check. Returns database connectivity status.

```json
{
  "status": "healthy",
  "service": "healthcare-backend",
  "database": "connected",
  "version": "1.0.0"
}
```

---

### GET `/api/health/ready`
**Public** — Readiness probe. Returns `200` when database is reachable.

---

### GET `/api/health/live`
**Public** — Liveness probe. Returns `200` if the process is running.

---

## Error Responses

All error responses follow this shape:

```json
{ "detail": "Human-readable error message" }
```

| HTTP Status | Meaning |
|---|---|
| `400` | Bad request — invalid input |
| `401` | Unauthorised — missing or invalid token |
| `403` | Forbidden — authenticated but insufficient role |
| `404` | Not found |
| `422` | Validation error — request body does not match expected schema |
| `500` | Internal server error |
| `503` | Service unavailable — database unreachable |
