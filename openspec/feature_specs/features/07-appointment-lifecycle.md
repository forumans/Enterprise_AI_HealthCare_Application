# Feature 07 — Appointment Lifecycle (Core Domain and API)

**Roles:** P, D, S, A (per endpoint) · **API:** `/appointments*` · **Used by screens:** 09, 10, 11, 12, 16 ·
**Depends on:** F02, F03, F04, F05, 08 (slots) · **Traces to:** `BR-APT-*`, `DATA-APT-*`, `DATA-TRG-01`

## 1. Purpose

One appointment = one patient booked into one hourly slot of one doctor. This feature owns the state machine,
booking, confirmation, rescheduling, reason edits, status changes, cancellation and the appointment list APIs.
Screens are specified separately and only call these endpoints.

## 2. State machine

```
               book (P own / S for patient)          confirm (D own)
    (none) ──────────────────────────────► SCHEDULED ─────────────────► CONFIRMED
                                              │   ▲  reschedule keeps status  │
                                              │   └───────────────────────────┤
                                              │                               │ consultation saved (D own)
                cancel (P own, D own, S, A)   │                               ▼
                                              ▼                           COMPLETED (terminal)
                                         CANCELLED (terminal; row soft-deleted; slot freed)
```

- **BR-APT-01** New appointments start `SCHEDULED`.
- **BR-APT-02** Only `SCHEDULED` can be confirmed ("Only scheduled appointments can be confirmed.", 400); only the
  appointment's own doctor confirms (403 "Not allowed to change this appointment." otherwise).
- **BR-APT-03** `COMPLETED` is set when the doctor saves a consultation ([12](12-consultation-clinical-records.md))
  through the generic status endpoint.
- **BR-APT-04 Cancel** sets `status=CANCELLED`, `deleted_at=now`, `deleted_by=caller`; the trigger frees the slot
  (`AVAILABLE`). The row is kept; cancelled rows don't count toward the partial unique indexes, so the slot can
  be rebooked by anyone immediately.
- **BR-APT-05** Terminal states are never rescheduled, edited, confirmed or cancelled again. A cancelled
  appointment is soft-deleted, so every later call on it returns 404 "Appointment not found.".
- **BR-APT-VIEW-01 Upcoming vs past.** An appointment is *upcoming* while `appointment_time + 60 min > now` and
  its status is neither `COMPLETED` nor `CANCELLED` (in-progress visits stay upcoming). Everything else is *past*.
- **BR-APT-VIEW-02** Doctor-facing lists exclude appointments of soft-deleted patients.

## 3. Booking (`BR-APT-BOOK`)

- **BOOK-01 Who.** PATIENT books for themselves (profile from token). SUPPORT_STAFF books for a named patient
  (`patient_id` required, else **422 "patient_id is required."**). The patient must exist, not be soft-deleted
  and belong to the caller's tenant, else **404 "Patient profile not found."**. Other roles → 403.
- **BOOK-02** `slot` parses as ISO-8601 (else **422 "Invalid slot timestamp."**) and is strictly in the future
  (else **400 "Cannot book a time in the past."**).
- **BOOK-03** `reason` ≥ 5 characters (Pydantic `min_length=5` → 422 generic message). UI messages: patient screen
  "Please provide a reason for the appointment." (empty); support screens "Please provide a reason of at least 5
  characters.". Stored in `appointments.notes` (patient flow sends it trimmed).
- **BOOK-04 Slot lock.** `SELECT … FROM doctor_availability WHERE tenant_id = :t AND doctor_id = :d AND
  slot_time = :time FOR UPDATE`. Missing or not `AVAILABLE` → **409 "Requested slot is not available."**.
- **BOOK-05** Insert the appointment (`slot_id` = slot id, `notes` = reason, status default), set the slot
  `BOOKED`, flush. A unique-index violation (doctor or patient already busy at that time) →
  **409 "Appointment conflicts with existing booking."**. Audit `appointments` INSERT
  `{doctor_id, patient_id, appointment_time: <slot as sent>}`. Commit. Return **201** `{"id", "status"}`.
- **BOOK-06** The doctor SHALL be a non-deleted doctor of the tenant whose login is active and not deleted. Checked
  before the slot lock: unknown, deleted or other-tenant doctor → **404 "Doctor not found."**; deactivated login
  (e.g. self-registered and awaiting approval) → **409 "This doctor isn't accepting appointments."**.
- **BOOK-07 (UI)** Grids never offer past cells, non-`AVAILABLE` cells, or cells where the patient already has a
  live (`SCHEDULED`/`CONFIRMED`) appointment with any doctor.

## 4. Rescheduling (`BR-APT-RESCHED`)

- **RESCHED-01** PATIENT (own), DOCTOR (own) and SUPPORT_STAFF (any in tenant). Others → 403 "Forbidden for this
  role."; a patient/doctor who doesn't own it → **403 "Not allowed to reschedule this appointment."**.
- **RESCHED-02** `slot` parses (422 "Invalid slot timestamp.") and is strictly in the future
  (**400 "Cannot reschedule to a time in the past."**).
- **RESCHED-03** The appointment is loaded `FOR UPDATE` (tenant, not deleted; else 404 "Appointment not found.").
  Only `SCHEDULED`/`CONFIRMED` → else **400 "Only scheduled or confirmed appointments can be rescheduled."**.
- **RESCHED-04** New time ≠ current → else **400 "Appointment is already at that time."**.
- **RESCHED-05** Lock the **same doctor's** slot at the new time; missing or not `AVAILABLE` →
  **409 "Requested slot is not available."**. Lock the old slot.
- **RESCHED-06** In the same transaction: `appointment_time = new`, `slot_id = new slot`, new slot `BOOKED`, old
  slot `AVAILABLE` (only if it was `BOOKED`). Patient, doctor, reason and status are unchanged. A unique-index
  violation (patient busy at the new time) → **409 "Appointment conflicts with existing booking."**.
- **RESCHED-07** Audit `appointments` UPDATE `{appointment_time: old}` → `{appointment_time: new}`. Response 200
  `{"id", "appointment_time": <new ISO>, "status"}`.
- The DB trigger does not react to time changes, so the slot updates above are mandatory in code.

## 5. Other transitions

| Action | Endpoint | Who | Rules | Success |
|--------|----------|-----|-------|---------|
| Confirm | `POST /appointments/{id}/confirm` | D (own) | 404 if missing/deleted/other tenant; 403 "Not allowed to change this appointment." if not own; 400 unless `SCHEDULED` | `{"message": "Appointment confirmed successfully."}`; audit `{status:"SCHEDULED"}`→`{status:"CONFIRMED"}` |
| Edit reason | `PATCH /appointments/{id}` `{reason ≥5}` | S | 404; only `SCHEDULED`/`CONFIRMED` else 400 "Only scheduled or confirmed appointments can be updated."; stored trimmed | `{"id", "reason", "status"}`; audit `{notes}` old→new |
| Set status | `PATCH /appointments/{id}/status` `{status}` | D (own), A | value upper-cased/trimmed; `CANCELLED` → 400 "Use DELETE /appointments/{id} to cancel an appointment."; not in `SCHEDULED/CONFIRMED/COMPLETED` → 422 "Invalid appointment status."; 404; doctor not own → 403 "Not allowed to change this appointment."; same as the current status → no-op success (no audit); only `SCHEDULED→CONFIRMED`, `SCHEDULED→COMPLETED`, `CONFIRMED→COMPLETED` are allowed, anything else → 400 "Can't change an appointment from <old> to <new>." | `{"message": "Appointment status updated."}`; audit `{status}` old→new |
| Cancel | `DELETE /appointments/{id}` | P (own), D (own), S, A | 404; patient/doctor not own → 403 "Not allowed to cancel this appointment." | `{"message": "Appointment cancelled."}`; audit DELETE `{status: old}`→`{status:"CANCELLED"}` |

Time changes go only through reschedule. A `COMPLETED` visit can't be reopened, not even by an admin.

## 6. List endpoints (scoped to the caller)

Scoping (`_scope_to_caller`): ADMIN and SUPPORT_STAFF see the whole tenant; PATIENT sees `patient_id = own`;
DOCTOR sees `doctor_id = own`; a patient/doctor without a profile gets `[]`. All exclude soft-deleted rows.

| Endpoint | Roles | Response item | Order |
|----------|-------|---------------|-------|
| `GET /appointments` | any signed-in | `{id, doctor_id, patient_id, appointment_time, status}` | unspecified |
| `GET /appointments/all?include_cancelled=` | any signed-in | `{id, doctor_id, patient_id, slot_id, appointment_time, status, notes, doctor_name}` (`doctor_name` from a tenant-filtered, non-deleted doctor join; "Unknown Doctor" when missing). `include_cancelled=true` also returns cancelled appointments (soft-deleted on cancel) | `appointment_time` asc |
| `GET /appointments/week?from_date=YYYY-MM-DD` | any signed-in | same as `/all` (`doctor_name` null when missing) | asc, limited to the clinic week (Mon–Mon) containing `from_date` (default clinic today) |

Doctor-specific views are in [10](10-doctor-weekly-appointments.md)/[11](11-doctor-today-appointments.md);
support views in [16](16-support-appointments.md).

## 7. Request schemas

```text
CreateAppointmentRequest   { doctor_id: str, slot: str (ISO), reason: str (min 5), patient_id?: str }
RescheduleAppointmentRequest { slot: str (ISO) }
UpdateAppointmentRequest   { reason: str (min 5) }
UpdateAppointmentStatusRequest { status: str }
```

## 8. Concurrency guarantees (`NFR-REL-01`)

- Two concurrent bookings of one slot → exactly one 201 and one 409 (row lock + unique index).
- A patient booking two doctors at the same hour concurrently → one 201, one 409 (`unique_patient_time`).
- A booking racing a reschedule into the same slot → one succeeds, the other 409.

## 9. Acceptance criteria

- **F07-AC-01** Given an available slot and a 5-character reason, When a patient books, Then 201, status
  `SCHEDULED`, slot `BOOKED`, audit row present.
- **F07-AC-02** Given a 4-character reason sent directly, Then 422.
- **F07-AC-03** Given a slot another patient took a moment earlier, Then 409 "Requested slot is not available.".
- **F07-AC-04** Given a patient with a 10 AM appointment with doctor A, When they book 10 AM with doctor B, Then
  409 "Appointment conflicts with existing booking.".
- **F07-AC-05** Given a cancelled appointment, Then its slot is `AVAILABLE`, another patient can book it, and the
  cancelled row still exists with `deleted_at` set.
- **F07-AC-06** Given a reschedule, Then reason and status are unchanged, old slot `AVAILABLE`, new slot
  `BOOKED`; rescheduling to the same time → 400 "Appointment is already at that time.".
- **F07-AC-07** Given a `COMPLETED` appointment, When rescheduled, Then 400 "Only scheduled or confirmed
  appointments can be rescheduled.".
- **F07-AC-08** Given support staff booking without `patient_id`, Then 422 "patient_id is required.".
- **F07-AC-09** Given a patient calling DELETE or reschedule on another patient's appointment, Then 403; on
  another tenant's, Then 404.
- **F07-AC-10** Given doctor B, When B confirms doctor A's appointment, Then 403 "Not allowed to change this
  appointment." and the status stays `SCHEDULED`.
- **F07-AC-13** Given a doctor whose login is deactivated, When a patient or support staff books one of their slots,
  Then 409 "This doctor isn't accepting appointments." and nothing is created; given a doctor of another clinic,
  Then 404 "Doctor not found.".
- **F07-AC-11** Given `PATCH /status {status:"cancelled"}`, Then 400 "Use DELETE /appointments/{id} to cancel an
  appointment.".
- **F07-AC-12** Given a confirmed appointment, When confirmed again, Then 400 "Only scheduled appointments can be
  confirmed.".

## 10. Reference implementation

`backend/app/api/routes/appointments.py`, `services/appointment_service.py`, `migrations/002_fix_sync_function.sql`,
tests `tests/integration/test_core_flows.py`, `test_http_flows.py`.
