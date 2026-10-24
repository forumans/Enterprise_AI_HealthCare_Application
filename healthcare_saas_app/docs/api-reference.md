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
**DOCTOR** (own slots) / **SUPPORT_STAFF** (any doctor, `doctor_id` required) — Add, block or unblock an availability slot. Patient-booked slots can't be changed (`400`).

```json
{
  "slot": "2026-04-15T13:00:00.000Z",
  "is_available": false,
  "block_reason": "Staff training",
  "doctor_id": "uuid"
}
```

---

### DELETE `/api/doctor/availability/{availability_id}`
**DOCTOR** — Delete an availability slot.

---

## Appointments

### POST `/api/appointments`
**PATIENT** (for themselves) / **SUPPORT_STAFF** (on behalf of a patient, `patient_id` required) — Book an available future slot.

```json
{
  "doctor_id": "uuid",
  "slot": "2026-04-15T13:00:00.000Z",
  "reason": "Follow-up for blood pressure",
  "patient_id": "uuid"
}
```

**Response `201`:** `{ "id": "uuid", "status": "SCHEDULED" }`

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

### PATCH `/api/appointments/{appointment_id}`
**SUPPORT_STAFF** — Update the reason of a `SCHEDULED` or `CONFIRMED` appointment on behalf of the patient.

```json
{ "reason": "Follow-up on blood work" }
```

---

### POST `/api/appointments/{appointment_id}/reschedule`
**PATIENT** (own appointments) / **DOCTOR** (their appointments) / **SUPPORT_STAFF** (any appointment) — Move a `SCHEDULED` or `CONFIRMED` appointment to another available slot of the same doctor. Reason, patient, doctor and status are kept; the old slot is freed and the new one booked.

```json
{ "slot": "2026-10-25T18:00:00.000Z" }
```

Errors: `400` past time / same time / not reschedulable status, `403` not your appointment, `409` slot unavailable or the patient already has an appointment then.

---

### DELETE `/api/appointments/{appointment_id}`
**PATIENT** (own appointments) / **DOCTOR** (their appointments) / **SUPPORT_STAFF** (any appointment) — Cancel a scheduled or confirmed appointment (soft delete); the slot becomes available again. `403` if it isn't yours.

---

## Patients

### POST `/api/patients`
**ADMIN** — Create a patient record.

---

### GET `/api/patients`
**ADMIN / DOCTOR / SUPPORT_STAFF** — List all patients in the tenant.

---

### GET `/api/patients/search`
**DOCTOR / ADMIN** — Search patients by name; `?q=*` lists every patient.

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

## Support Staff

### GET `/api/support/profile`
**SUPPORT_STAFF** — The logged-in support staff member's profile: `{ "id", "full_name", "phone", "email" }`.

---

### PUT `/api/support/profile`
**SUPPORT_STAFF** — Update your own name and phone. Email is the login and can't be changed here. `422` if the name is shorter than 3 characters or the phone isn't 10–15 digits.

```json
{ "full_name": "Sam Support", "phone": "+1 555-123-4567" }
```

---

### GET `/api/support/doctors`
**SUPPORT_STAFF** — Find doctors by part of their name or phone number, matched the same way as the patient search below. Returns name, phone, email, specialty and license number. Up to 50 results.

**Query params:** `?q=<at least 2 characters, or * for everyone>` (`422` otherwise). `*` returns everyone with no 50-result cap.

---

### GET `/api/support/patients`
**SUPPORT_STAFF** — Find patients by part of their name (case-insensitive) or phone number (formatting ignored, 3+ digits). Returns contact details only — name, phone, email, date of birth, gender, insurance provider, city, state — no medical data. Up to 50 results.

**Query params:** `?q=<at least 2 characters, or * for everyone>` (`422` otherwise). `*` returns everyone with no 50-result cap.

---

### GET `/api/support/appointments`
**SUPPORT_STAFF** — Active appointments from the start of today (clinic time) for one patient or one doctor, with patient and doctor names.

**Query params:** exactly one of `?patient_id=uuid` or `?doctor_id=uuid` (`422` otherwise).

Booking, reason updates, rescheduling, cancelling and slot blocking use the appointment and availability endpoints above, which accept the `SUPPORT_STAFF` role.

---

## Admin

### GET `/api/admin/users`
**ADMIN** — List all users (paginated).

**Query params:** `?page=1&page_size=20`

---

### POST `/api/admin/users`
**ADMIN** — Create a user account. `role` is one of `PATIENT`, `DOCTOR`, `ADMIN`, `SUPPORT_STAFF`.

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

### GET `/api/admin/users/search`
**ADMIN** — Find active users of one role in this clinic by part of their name, email or phone number (used by the Reset Password / Email screen). Returns `user_id`, `role`, `name`, `email`, `phone`, `address` (patients), `date_of_birth`, `specialty` (doctors). Up to 50 results.

**Query params:** `?role=PATIENT|DOCTOR|SUPPORT_STAFF|ADMIN&q=<at least 2 characters, or * for everyone of that role>` (`400` bad role, `422` short query). `*` returns all matches with no 50-result cap.

---

### POST `/api/admin/users/{user_id}/deactivate`
**ADMIN** — Deactivate an account (sets `users.is_active = false`); it can't log in until activated again. Records and appointments are kept. Errors: `400` your own account or already deactivated, `403` your own admin account is deactivated, `404` not in this clinic, `409` it would leave no active admin.

---

### POST `/api/admin/users/{user_id}/activate`
**ADMIN** — Re-activate a deactivated account so it can log in again. `400` if it's already active.

Search results (`GET /api/admin/users/search`) include `is_active` and `is_self` for the Deactivate screen.

---

### POST `/api/admin/users/{user_id}/reset-password`
**ADMIN** — Reset the picked user's password: `{ "new_password": "at least 8 characters" }`. Audited without the password. `404` if the user isn't in this clinic.

---

### POST `/api/admin/users/{user_id}/change-email`
**ADMIN** — Change the picked user's login email: `{ "new_email": "new@example.com" }`. Same rules and errors as `/api/admin/change-email` below.

---

### POST `/api/admin/change-email`
**ADMIN** — Change a user's login email, found by current email and role. Emails are trimmed and lowercased; the password is unchanged.

```json
{ "email": "old@example.com", "role": "PATIENT", "new_email": "new@example.com" }
```

Errors: `400` same email or invalid role, `404` no such user, `409` the new email is used by an active account in any clinic (login looks emails up across clinics) or by any account in this clinic.

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
