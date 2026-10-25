# 10 — API Specification

REST over HTTPS, JSON bodies (multipart for uploads). Every path below is served both as `/api<path>` and
`<path>` (`GEN-ARCH-01`). Roles use the codes P, D, S, A (doc 09 §5.1); "public" means no token.

## 1. Conventions

- **API-GEN-01** Authenticated requests send `Authorization: Bearer <access_token>`.
- **API-GEN-02** Errors are JSON `{"detail": "<human-readable message>"}`. Status codes:
  400 business-rule violation, 401 not authenticated or session ended, 403 wrong role or not the owner,
  404 not found (including other tenants' records), 409 conflict (duplicate email, slot taken, double booking),
  422 invalid input, 500 unexpected error (generic message), 503 dependency not ready.
- **API-GEN-03** Timestamps are ISO-8601 with offset (UTC). Inputs without an offset are treated as UTC.
  Date-only query parameters use `YYYY-MM-DD`.
- **API-GEN-04** Ids are UUID strings.
- **API-GEN-05** Successful creates return 201. Other successes return 200.
- **API-GEN-06** Lists are unpaged unless `page`/`page_size` are documented; searches are capped at 50 except
  for `*` (`BR-SRCH-03`).
- **API-GEN-07** The OpenAPI document (`/docs`, `/openapi.json`) SHOULD be disabled or protected in production.

## 2. Health

| Method & path | Auth | Response |
|---------------|------|----------|
| GET `/health` | public | 200 `{status:"healthy", service:"healthcare-backend", database:"connected", version}`; 503 `{status:"unhealthy", database:"disconnected"\|"unknown", error}` |
| GET `/api/health/ready` | public | 200 `{status:"ready", checks:{database, api}}` or 503 `not_ready` |
| GET `/api/health/live` | public | 200 `{status:"alive", timestamp}` |

## 3. Authentication

| Method & path | Auth | Body | Success | Errors |
|---------------|------|------|---------|--------|
| POST `/auth/register` | public | `{full_name (3–255), email, phone?, password, insurance_provider?, insurance_policy_number?, date_of_birth? (YYYY-MM-DD), gender?, address_line1?, address_line2?, city?, state?, postal_code?, country?}` | 201 `{message:"Registration successful"}` | 409 duplicate email; 422 |
| POST `/auth/login` | public | `{email, password, remember_me?}` | 200 `{access_token, refresh_token:"", role, tenant_id, user_name?, insurance_provider?, insurance_policy_id?}` | 401 "Authentication failed" |
| POST `/auth/forgot-password` | public | `{email}` | 200 fixed message (`AUTH-FP-02`) | — |
| POST `/auth/reset-password` | public | `{token, new_password (≥8)}` | 200 `{message}` | 400 invalid/expired link; 422 |
| POST `/doctors/register` | public | `{full_name, email, password, specialty?, license_number?, phone?, date_of_birth?}` | 201 `{message}` | 409; 422 |
| POST `/admin/register` | public (bootstrap only) | `{full_name, email, password}` | 201 `{message}` | 403 once an admin exists; 409; 422 |

## 4. Tenants

| Method & path | Roles | Response |
|---------------|-------|----------|
| GET `/tenants/current` | any signed-in | `{id, name, domain}` |
| POST `/tenants` | platform admin | body `{name (2–255), domain?}` → 201 `{id, name, domain}`; 409 duplicate domain |
| GET `/tenants/{id}` | platform admin | `{id, name, domain}` / 404 |

## 5. Doctors and availability

| Method & path | Roles | Input | Response |
|---------------|-------|-------|----------|
| GET `/doctors` | any signed-in | — | `[{id, name, specialty, license_number}]` active doctors of the tenant, by name |
| GET `/doctors/me` | D | — | `{id, name, specialty, license_number}` / 404 |
| GET `/doctor/profile` | D | — | `{id, full_name, email, phone, specialty, license_number, …}` |
| PUT `/doctor/profile` | D | `{fullName?, phone?, specialty?, licenseNumber?}` | `{message:"Profile updated successfully"}` |
| GET `/availability/{doctor_id}?date=YYYY-MM-DD` | any signed-in | — | `[{slot}]` AVAILABLE slots on that clinic day |
| GET `/doctor/availability/{doctor_id}/ndays` | any signed-in | — | `[{slot_time}]` AVAILABLE slots in the next 30 days (read-only, no generation) |
| GET `/doctor/availability/{doctor_id}/all?days=30` | any signed-in | — | `[{slot_time, status}]` from now to now+days, effective status (`BR-SLOT-08`); tops up defaults (`BR-SLOT-01`); unknown doctor → `[]` |
| POST `/doctor/availability` | D (own), S (doctor_id) | `{slot, is_available, block_reason?, doctor_id?}` | `{message}` (`BR-SLOT-06`); 400 window/booked; 403; 404; 422 |
| POST `/doctor/availability/{doctor_id}` | D (own), S | `{slot_time, is_available}` | add/update; 400 booked |
| DELETE `/doctor/availability/{doctor_id}` | D (own), S | `{slot_time}` | `{message}`; 404 missing; 400 booked |
| POST `/doctors` | A | `{user_id, full_name, specialty?, license_number?, phone?}` | 201 `{id}`; 404 user; 409 exists |

## 6. Doctor appointment views

| Method & path | Roles | Response |
|---------------|-------|----------|
| GET `/doctor/appointments/today` | D | `[{id, doctor_id, time, patient_name, reason, status, urgent}]` today (clinic) |
| GET `/doctor/appointments/all?from_date=` | D | `[{id, doctor_id, time, patient_name, symptoms, status}]` clinic week containing `from_date` (default today) |
| GET `/doctor/appointments?from_date=` | D | week view limited to today … today+30 (400 outside) |
| GET `/doctor/appointments/upcoming` | D | `[{id, time, patient_name, status}]` from now |
| GET `/doctor/appointments/{id}` | D (own) | `{id, time, patient_id, patient_name, status, notes}`; 400 non-UUID; 404 |

## 7. Appointments

| Method & path | Roles | Input | Response / errors |
|---------------|-------|-------|-------------------|
| POST `/appointments` | P, S | `{doctor_id, slot, reason (≥5), patient_id? (S: required)}` | 201 `{id, status}`; 400 past; 404 patient; 409 slot/conflict; 422 |
| GET `/appointments` | any (scoped) | — | `[{id, doctor_id, patient_id, appointment_time, status}]` |
| GET `/appointments/all` | any (scoped) | — | `[{id, doctor_id, patient_id, slot_id, appointment_time, status, notes, doctor_name}]` by time |
| GET `/appointments/week?from_date=` | any (scoped) | — | same fields, clinic week |
| POST `/appointments/{id}/confirm` | D (own) | — | `{message:"Appointment confirmed successfully."}`; 400 not SCHEDULED; 403; 404 |
| POST `/appointments/{id}/reschedule` | P (own), D (own), S | `{slot}` | `{id, appointment_time, status}`; 400 past/same/status; 403; 404; 409 |
| PATCH `/appointments/{id}` | S | `{reason (≥5)}` | `{id, reason, status}`; 400 status; 404 |
| PATCH `/appointments/{id}/status` | D (own), A | `{status: SCHEDULED\|CONFIRMED\|COMPLETED}` | `{message}`; 400 CANCELLED; 403; 404; 422 |
| DELETE `/appointments/{id}` | P (own), D (own), S, A | — | `{message:"Appointment cancelled."}`; 403; 404 |

Scoping for list endpoints: patients and doctors see their own; support staff and admins see the tenant's;
a patient/doctor without a profile gets `[]`.

## 8. Patient self-service

| Method & path | Roles | Response |
|---------------|-------|----------|
| GET `/patient/me` | P | `{id, name, email, phone, date_of_birth, insurance_provider, insurance_policy_number, address}` |
| GET `/patient/patient/profile` | P | `{id, full_name, phone, date_of_birth, gender, address_line1, address_line2, city, state, postal_code, country, insurance_provider, insurance_policy_number}` |
| PUT `/patient/patient/profile` | P | body camelCase `{fullName?, phone?, dateOfBirth?, gender?, addressLine1?, addressLine2?, city?, state?, postalCode?, country?, insuranceProvider?, insurancePolicyNumber?}` → `{message}` |
| PATCH `/patient/profile` | P | `{full_name, phone}` → `{message:"Profile updated"}` (email not editable, doc 13) |
| GET `/patient/appointments/upcoming` | P | `[{id, date, doctor, status}]` |
| GET `/patient/medical-history` | P | `[{date, doctor, diagnosis, notes}]` |
| GET `/patient/prescriptions-full?patient_id=` | P (own; parameter ignored), D (patient_id required, same tenant) | `[{appointment_time, doctor_name, appointment_status, appointment_note, symptoms, diagnosis, lab_results, medication_details, pharmacy_name, appointment_created_at}]` COMPLETED only, newest first |
| POST `/patient/documents` | P | multipart `file` → 201 `{message:"Document uploaded"}` |

## 9. Patients (staff views)

| Method & path | Roles | Response |
|---------------|-------|----------|
| GET `/patients` | D, S, A | `[{id, user_id, name, phone}]` active patients (avoid on large tenants; use search) |
| GET `/patients/search?q=` | D, A | `[{id, name, phone, dob, gender, address, symptoms, diagnosis, lab_results, medication, prescription_date}]` (name match; `[]` for short terms) |
| GET `/patients/{id}/prescriptions` | D | `[{id, name, symptoms, diagnosis, lab_results, medication, prescription_date, doctor_name}]` |
| POST `/patients` | A | `{user_id, full_name, phone?, insurance_provider?, insurance_policy_number?}` → 201 `{id}` |

## 10. Clinical records

| Method & path | Roles | Input | Response |
|---------------|-------|-------|----------|
| POST `/medical-records` | D (own appointment) | `{appointment_id, patient_id, diagnosis (≥3), notes (≥5), lab_results?}` | 201 `{id, message:"Medical record saved."}`; 404 "No appointment found for selected patient."; 409 exists |
| GET `/medical-records/{appointment_id}` | P (own), D (own), A | — | `{id, appointment_id, symptoms, diagnosis, lab_results}`; 404 |
| POST `/prescriptions` | D (own record), A | `{medical_record_id, medication_details (≥1), pharmacy_id?}` | 201 `{id}`; 404 record; 409 exists |
| GET `/prescriptions/pharmacies` | P, D, A | — | `[{id, name, address, phone}]` |
| GET `/prescriptions/{id}` | P (own), D, A | — | `{id, medical_record_id, pharmacy_id, medication_details}` |

## 11. Documents

| Method & path | Roles | Input | Response |
|---------------|-------|-------|----------|
| POST `/documents?patient_id=` | P (own), D, A | multipart `file` | 201 `{id}`; 404 patient; 413 too large; 415 type |
| GET `/documents/{patient_id}` | P (own), D, A | — | `[{id, document_name, document_type, download_url (1 h, null if storage unavailable), signed_at}]` |

## 12. Support staff

| Method & path | Roles | Input | Response |
|---------------|-------|-------|----------|
| GET `/support/profile` | S | — | `{id, full_name, phone, email}` |
| PUT `/support/profile` | S | `{full_name (3–255), phone (^\+?[0-9\-\s]{10,15}$)}` | `{message:"Profile updated successfully", full_name, phone, email}` |
| GET `/support/patients?q=` | S | `BR-SRCH` | `[{id, name, phone, email, date_of_birth, gender, insurance_provider, city, state}]` |
| GET `/support/doctors?q=` | S | `BR-SRCH` | `[{id, name, phone, email, specialty, license_number}]` |
| GET `/support/appointments?patient_id=\|doctor_id=` | S | exactly one | `[{id, appointment_time, status, reason, patient_id, patient_name, doctor_id, doctor_name}]` from start of today (clinic), by time |

## 13. Admin

| Method & path | Input | Response |
|---------------|-------|----------|
| GET `/admin/users?page=1&page_size=25` | page ≥1, size 1–500 | `[{id, name, email, role, is_deleted}]` newest first |
| POST `/admin/users` | `ADM-REG-01` fields | 201 `{id}`; 409; 422; 503 |
| GET `/admin/users/search?role=&q=` | role ∈ roles; `BR-SRCH` | `[{user_id, role, name, email, phone, address, date_of_birth, specialty, is_active, is_self}]` |
| POST `/admin/users/{id}/reset-password` | `{new_password}` | `{message, user_id, user_email, user_role}`; 400 short; 404 |
| POST `/admin/users/{id}/change-email` | `{new_email}` | `{message, user_id, old_email, new_email, user_role}`; 400 same/invalid; 404; 409 |
| POST `/admin/users/{id}/deactivate` | — | `{message, user_id, user_email, user_role, is_active:false}`; 400 self/already; 403 caller deactivated; 409 last admin |
| POST `/admin/users/{id}/activate` | — | same with `is_active:true` |
| PATCH `/admin/users/{id}/soft-delete` | — | `{message}`; 404 |
| PATCH `/admin/users/{id}/restore` | — | `{message:"User restored."}`; 400 not deleted; 404; 409 email reused |
| POST `/admin/reset-password` | `{email, role, new_password}` | legacy, by email+role |
| POST `/admin/change-email` | `{email, role, new_email}` | legacy, by email+role |
| GET `/admin/roles` | — | `[{value, label}]` Patients, Doctors, Support Staff, Admin |
| GET `/admin/appointments?page=&page_size=` | | `[{id, date, doctor, patient, status}]` |
| GET `/admin/reports` | | `{monthly_patient_count, diagnosis_frequency, doctor_utilization_rate}` |
| GET `/admin/appointment-metrics` | | `{total_appointments_to_date, …_year_to_date, …_this_month, …_this_week, …_today}` |
| GET `/audit-logs?table=&date_from=&date_to=` | | `[{action, timestamp, performed_by, table, old, new}]` newest 200 |
| `/users` (POST, GET, GET `/{id}`, PATCH `/{id}/soft-delete`, PATCH `/{id}/restore`) | | legacy user CRUD, same rules as `/admin/users*` |

## 14. Endpoints that SHALL NOT exist in production

- `GET /tenants/debug` (echoes the token identity) and `GET /test/auth-check` are development aids. They SHALL be
  removed or disabled outside development.
