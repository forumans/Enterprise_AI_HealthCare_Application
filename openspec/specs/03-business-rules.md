# 03 — Business Rules (cross-cutting)

These rules apply regardless of which role or screen triggers them. Role documents (04–08) refer to them
by ID. The backend SHALL enforce every rule; the frontend SHOULD also enforce rules marked (UI) so users get
immediate feedback.

## 1. Time and the clinic calendar (`BR-TIME`)

- **BR-TIME-01** All instants SHALL be stored and exchanged in UTC (ISO-8601). API responses SHALL include an
  offset (`+00:00`). Clients SHALL treat a timestamp without an offset as UTC.
- **BR-TIME-02** Each clinic (tenant) has its own time zone, the IANA name in `tenants.timezone` (for example
  `America/Chicago`, `Europe/London`, `Asia/Kolkata`). Office hours, "today", "this week", "this month" and
  "this year" are computed in that clinic's time, with daylight-saving transitions handled by IANA rules (8 AM
  stays 8 AM local all year; a DST day is 23 or 25 hours long). Two clinics in different zones never share a
  calendar: each request uses the zone of the signed-in user's clinic. `CLINIC_TIMEZONE` (default
  `America/New_York`) is only the zone given to a clinic created without one.
- **BR-TIME-03** A clinic week runs Monday 00:00 to the next Monday 00:00 (clinic time).
- **BR-TIME-04** The browser displays every time, and lays out every booking and availability grid, in
  **clinic time**, whatever zone the viewer's device is in: a patient travelling or a support agent working
  remotely sees the same 9:00 AM the doctor does. Login returns the clinic's zone (`clinic_timezone`). A grid
  cell is matched to a server slot by converting the server instant to a clinic wall-clock key
  `YYYY-MM-DDTHH:00:00`; when booking, the client converts the chosen cell back to a UTC instant in the clinic's
  zone. Every calendar shows the zone under its heading, e.g. "All times are clinic time: PDT (America/Los Angeles)"
  (`UI-DT-04`).
- **BR-TIME-06** When a clinic's time zone changes, each doctor's future schedule keeps its local hours: open
  and blocked slots move to the same local date and hour in the new zone (a 9 AM slot stays 9 AM), with block
  reasons kept. Booked slots and their appointments keep their exact instant, since a patient holds that time,
  and the local hour a booked slot occupied is reopened in the new zone. A moved slot that would be in the past
  or collide with an existing slot is dropped. The change and the number of slots moved are audited.
- **BR-TIME-05** Office hours SHALL be hourly slots starting at 8:00 AM through the slot starting at 11:00 PM
  clinic time (16 slots per day, 7 days a week). Slot length is 60 minutes. The constants
  `WORKDAY_FIRST_SLOT_HOUR = 8` and `WORKDAY_LAST_SLOT_HOUR = 23` SHALL be defined once on the backend and
  mirrored on the frontend.

## 2. Availability slots (`BR-SLOT`)

### 2.1 Slot states

| Status | Meaning | Who sets it |
|--------|---------|-------------|
| `AVAILABLE` | Open for booking | Default generation; doctor/support staff add or unblock; cancellation frees it |
| `BOOKED` | Held by a live (non-cancelled) appointment | Booking and rescheduling (application code and trigger) |
| `BLOCKED` | Not bookable (doctor away, etc.), with optional reason | Doctor or support staff |

- **BR-SLOT-01 Default generation.** Whenever a doctor's full availability is requested
  (`GET /doctor/availability/{doctor_id}/all`), the system SHALL ensure that each of the next 7 clinic-local
  days (today included) that has **no** slot at all for that doctor (any status) receives the full set of
  default office-hour slots, all `AVAILABLE`, keeping only slots strictly in the future.
- **BR-SLOT-02** A day that already has at least one slot SHALL be left untouched, so a doctor's manual
  changes (deleted or blocked hours) are never overwritten.
- **BR-SLOT-03** Slot generation SHALL be concurrency-safe: inserts skip slots that already exist
  (`ON CONFLICT DO NOTHING` on (`doctor_id`, `slot_time`)). A generation failure SHALL be logged and SHALL
  NOT fail the read request.
- **BR-SLOT-04 Change window.** Blocking, unblocking or adding a slot through `POST /doctor/availability`
  SHALL be refused for slot times in the past ("Cannot update slots earlier than now.") or more than 30 days
  ahead ("Cannot update slots beyond 30 days.").
- **BR-SLOT-05 Booked slots are protected.** A `BOOKED` slot SHALL NOT be blocked, unblocked, re-added or
  deleted: "Cannot modify a patient-booked slot." (HTTP 400). It changes only through booking, cancellation
  or rescheduling.
- **BR-SLOT-06 Transitions** through `POST /doctor/availability`:
  - `is_available=true`, slot missing → create `AVAILABLE` ("Availability added successfully");
  - `is_available=true`, slot `BLOCKED` → `AVAILABLE`, clear `block_reason` ("Slot unblocked successfully");
  - `is_available=false`, slot missing → create `BLOCKED` with reason ("Slot blocked successfully");
  - `is_available=false`, slot `AVAILABLE` or `BLOCKED` → `BLOCKED` with the new reason ("Slot blocked successfully").
- **BR-SLOT-07 Who may change slots.** A doctor may change only their own slots. Support staff may change any
  doctor's slots in their tenant and SHALL name the doctor (`doctor_id`, else 422 "doctor_id is required.").
  A doctor naming another doctor gets 403 "Not allowed to change another doctor's availability." Other roles
  get 403.
- **BR-SLOT-08 Effective status.** When listing a doctor's slots, a slot that has a live (non-cancelled,
  non-deleted) appointment at its time SHALL be reported as `BOOKED`, whatever its stored status.
- **BR-SLOT-09** The bookable horizon shown to users SHALL be 5 weeks (current week plus 4 more). The
  availability listing SHALL default to the next 30 days.

## 3. Appointment lifecycle (`BR-APT`)

### 3.1 State machine

```
              book                     confirm (doctor)
   (none) ───────────► SCHEDULED ─────────────────────► CONFIRMED
                          │  ▲                              │
                          │  └──── reschedule keeps status ─┤
                          │                                 │ consultation completed (doctor)
           cancel (any    │                                 ▼
           permitted role)│                             COMPLETED   (terminal)
                          ▼
                      CANCELLED (terminal; record soft-deleted; slot freed)
```

- **BR-APT-01** New appointments start as `SCHEDULED`.
- **BR-APT-02 Confirm.** Only `SCHEDULED` appointments can be confirmed: "Only scheduled appointments can be
  confirmed." Only doctors confirm.
- **BR-APT-03 Complete.** Setting `COMPLETED` happens when the doctor saves a consultation. A generic status
  endpoint accepts only `SCHEDULED`, `CONFIRMED` or `COMPLETED` ("Invalid appointment status.", 422); setting
  `CANCELLED` through it is refused ("Use DELETE /appointments/{id} to cancel an appointment.", 400). Doctors
  may change only their own appointments; admins any in the tenant.
- **BR-APT-04 Cancel.** Cancelling SHALL set `status = CANCELLED`, `deleted_at = now`,
  `deleted_by = caller` and free the slot (`AVAILABLE`). The row is kept for audit. Cancelled appointments
  no longer count toward the uniqueness indexes, so the slot can be rebooked by anyone.
- **BR-APT-05 Who may cancel.** A patient only their own appointments, a doctor only their own; support staff
  and admins any appointment in the tenant. Otherwise 403 "Not allowed to cancel this appointment."
- **BR-APT-06** Terminal states (`COMPLETED`, `CANCELLED`) SHALL NOT be rescheduled, edited, confirmed or
  cancelled again (a cancelled appointment is soft-deleted and returns 404).

### 3.2 Booking (`BR-APT-BOOK`)

- **BR-APT-BOOK-01** Only patients (for themselves) and support staff (for a named patient, `patient_id`
  required, else 422 "patient_id is required.") may book. The patient SHALL exist, be active and belong to
  the caller's tenant, else 404 "Patient profile not found."
- **BR-APT-BOOK-02** The slot time SHALL be strictly in the future: "Cannot book a time in the past." (400).
- **BR-APT-BOOK-03** The reason SHALL be at least 5 characters after trimming (UI shows "Please provide a
  reason of at least 5 characters." / patient screen "Please provide a reason for the appointment.").
- **BR-APT-BOOK-04** The doctor's slot at exactly that time SHALL exist and be `AVAILABLE`, else 409
  "Requested slot is not available." The slot row SHALL be locked (`SELECT … FOR UPDATE`) for the duration of
  the transaction.
- **BR-APT-BOOK-05** On success: insert the appointment (`slot_id` = slot id, `notes` = reason), set the slot
  `BOOKED`, write an audit entry, commit, return `{id, status}` with 201.
- **BR-APT-BOOK-06** If the uniqueness indexes reject the insert (same doctor/time or same patient/time), return
  409 "Appointment conflicts with existing booking."
- **BR-APT-BOOK-07** (UI) The booking grid SHALL NOT offer: past cells (including earlier hours today), cells
  that are not `AVAILABLE`, and cells where the patient already has a `SCHEDULED`/`CONFIRMED` appointment
  with any doctor.

### 3.3 Rescheduling (`BR-APT-RESCHED`)

- **BR-APT-RESCHED-01** Patients (own), doctors (own) and support staff (any in tenant) may reschedule.
  Others get 403; non-owners get 403 "Not allowed to reschedule this appointment."
- **BR-APT-RESCHED-02** Only `SCHEDULED` or `CONFIRMED` appointments: "Only scheduled or confirmed
  appointments can be rescheduled." (400).
- **BR-APT-RESCHED-03** The new time SHALL be in the future ("Cannot reschedule to a time in the past."),
  differ from the current time ("Appointment is already at that time."), and be an `AVAILABLE` slot of the
  **same doctor** ("Requested slot is not available.", 409).
- **BR-APT-RESCHED-04** In one transaction with row locks on the appointment, the new slot and the old slot:
  set the new slot `BOOKED`, set the old slot back to `AVAILABLE` (only if it was `BOOKED`), update
  `appointment_time` and `slot_id`. Patient, doctor, reason and status are unchanged.
- **BR-APT-RESCHED-05** If the patient already has another live appointment at the new time, return 409
  "Appointment conflicts with existing booking."
- **BR-APT-RESCHED-06** (UI) The reschedule calendar marks the current time "Current" and does not offer it,
  past cells, unavailable cells, or the patient's other live appointment times.

### 3.4 Editing the reason (`BR-APT-EDIT`)

- **BR-APT-EDIT-01** Only support staff may change an appointment's reason, for `SCHEDULED`/`CONFIRMED`
  appointments only ("Only scheduled or confirmed appointments can be updated."). Minimum 5 characters
  ("Reason must be at least 5 characters."). Time changes go through rescheduling.

### 3.5 Upcoming versus past (`BR-APT-VIEW`)

- **BR-APT-VIEW-01** An appointment is *upcoming* while its slot has not ended
  (`appointment_time + 60 min > now`) and its status is neither `COMPLETED` nor `CANCELLED`. In-progress
  visits stay upcoming. Everything else is *past*.
- **BR-APT-VIEW-02** Lists of a doctor's appointments SHALL exclude appointments of soft-deleted patients.

## 4. Consultation and clinical records (`BR-CLIN`)

- **BR-CLIN-01** Only the appointment's doctor may open and save its consultation. The consultation SHALL be
  available for `CONFIRMED` appointments (the UI greys the Consultation button for other statuses).
- **BR-CLIN-02** Symptoms (minimum 5 characters) and diagnosis (minimum 3 characters) are required; lab results
  are optional. Error when missing: "Please fill in at least symptoms and diagnosis fields".
- **BR-CLIN-03** Saving creates the appointment's medical record (one per appointment). If one already exists
  (409 "Medical record already exists for appointment."), the existing record is reused.
- **BR-CLIN-04** A prescription is created only when both medication and dosage are given. It is stored as
  `"<medication> - <dosage>. <instructions or 'Take as prescribed'>"`, optionally linked to a pharmacy of the
  same tenant. One prescription per medical record (409 "Prescription already exists." on a second one).
- **BR-CLIN-05** After the record (and optional prescription) is saved, the appointment SHALL be set to
  `COMPLETED`. On success show "Consultation completed successfully!" and return to Today's Appointments after
  2 seconds.
- **BR-CLIN-06** If the appointment was cancelled or no longer exists, the consultation screen SHALL show
  "Appointment was cancelled by the patient. Cannot start consultation." and no form.
- **BR-CLIN-07** A patient's clinical history (prescriptions view) lists only `COMPLETED`, non-deleted
  appointments, newest first, joined with medical record, prescription and pharmacy where present.

## 5. Accounts and identity (`BR-ACC`)

- **BR-ACC-01 Email uniqueness.** Emails are stored lower-cased and trimmed. Because login looks a user up by
  email across all tenants, an email SHALL NOT be given to a new or existing account if it belongs to any
  **active (non-deleted)** account in any tenant, or to **any** account (even deleted) in the same tenant.
  Message: "That email is already used by another account." (409).
- **BR-ACC-02 One profile per user.** Creating a user SHALL create the matching profile row in the same
  transaction: `PATIENT` → `patients`, `DOCTOR` → `doctors`, `SUPPORT_STAFF` → `support_staff`,
  `ADMIN` → `admins`.
- **BR-ACC-03 Deactivate.** Sets `is_active = false`. The person cannot sign in, and any session they already
  have ends on its next request (see `SEC-SESS-03`). Their records stay visible to staff.
- **BR-ACC-04** An admin SHALL NOT deactivate their own account ("You can't deactivate your own account.").
  At least one admin per tenant SHALL stay active ("At least one admin must stay active.", 409). Active-admin
  rows SHALL be locked while (de)activating so two admins deactivating each other at once cannot leave none.
  A deactivated admin acting with a still-valid token gets 403 "Your admin account is deactivated."
- **BR-ACC-05** (De)activating an account already in that state returns 400 "This account is already
  active." / "This account is already deactivated."
- **BR-ACC-06 Soft delete.** Sets `deleted_at`/`deleted_by` on the user and the profile and `is_active = false`.
  The person disappears from lists, searches and booking; their appointments and records stay in the
  database.
- **BR-ACC-07 Restore.** Clears `deleted_at`/`deleted_by` on the user and profile and sets `is_active = true`.
  Refused if the user is not deleted ("This account is not deleted.", 400) or another active account now uses
  the email ("Another active account uses this email. Change one of the emails before restoring.", 409).
- **BR-ACC-08 Change login email (admin).** New email SHALL be valid, differ from the current one ("The new
  email (…) is the same as the current one."), and satisfy `BR-ACC-01`. The password is kept.
- **BR-ACC-09 Reset password (admin).** Minimum 8 characters ("Password must be at least 8 characters long").
  The email is kept.
- **BR-ACC-10** Every account change SHALL write an audit entry naming the acting user (see `SEC-AUD`).

## 6. People search (`BR-SRCH`)

- **BR-SRCH-01** A search term SHALL be at least 2 characters after trimming, or exactly `*`.
  UI message: "Enter at least 2 characters of <what>, or * to list everyone." API returns 422 "Enter at least
  2 characters to search, or * for everyone." (Doctor patient search returns an empty list instead.)
- **BR-SRCH-02** A term matches when it is a case-insensitive substring of the full name, OR of the login email
  (where the search supports email), OR — when the term contains at least 3 digits — the term's digits appear
  in the phone number's digits (formatting ignored, so "555-123" finds "(555) 123-4567").
- **BR-SRCH-03** `*` returns every active match with no cap; any other term is capped at 50 results.
  Results are sorted by full name ascending.
- **BR-SRCH-04** Searches return only non-deleted people in the caller's tenant.

| Search | Who | Fields matched | Returns |
|--------|-----|----------------|---------|
| Support patient search | Support staff | name, email, phone | contact details only (no clinical data) |
| Support doctor search | Support staff | name, email, phone | contact, specialty, license |
| Admin user search | Admin | name, email, phone, within one chosen role | account details, active flag, "is self" |
| Doctor patient search | Doctor, admin | name only | demographics plus clinical history rows |

## 7. Field validation catalog (`VAL`)

Apply the same rule wherever the field appears. "UI" is the client check; "API" is the server check. Both
SHALL enforce the rule; where only one is listed, the other SHALL match it.

| ID | Field | Rule | Message |
|----|-------|------|---------|
| VAL-01 | Full name | Required; 3–80 characters after trimming (API accepts up to 255) | "Name must be at least 3 characters." |
| VAL-02 | Email | Matches `^[^\s@]+@[^\s@]+\.[^\s@]+$`; stored lower-case | "Please provide a valid email address." (login: "Please enter a valid email address") |
| VAL-03 | Phone | Matches `^\+?[0-9\-\s]{10,15}$` (10–15 digits, spaces or dashes; optional leading +) | "Phone should be 10-15 digits." |
| VAL-04 | Password (any new password) | Minimum 8 characters | "Password must be at least 8 characters long" |
| VAL-05 | Password confirmation | Equal to the password | "The two passwords do not match." |
| VAL-06 | Patient date of birth | Optional on self-registration, required when an admin registers a patient; not in the future; not more than 120 years ago | "Date of birth cannot be in the future." / "Date of birth cannot be more than 120 years ago." |
| VAL-07 | Doctor date of birth | Required; doctor at least 18 years old today | "Doctor must be at least 18 years old. Current age: N" |
| VAL-08 | Gender | One of `MALE`, `FEMALE`, `OTHER`, `PREFER_NOT_TO_SAY`; optional on self-registration, required when an admin registers a patient | "Gender is required." |
| VAL-09 | Appointment reason | Required; at least 5 characters after trimming | "Please provide a reason of at least 5 characters." |
| VAL-10 | Diagnosis | Required; at least 3 characters | see `BR-CLIN-02` |
| VAL-11 | Symptoms | Required; at least 5 characters | see `BR-CLIN-02` |
| VAL-12 | Search term | `BR-SRCH-01` | |
| VAL-13 | Slot / appointment time | ISO-8601 instant; parse errors → 422 "Invalid slot timestamp." / "Invalid datetime format." | |
| VAL-14 | Optional text fields (address, insurance, specialty, license) | Trimmed; empty string stored as NULL; max lengths per doc 02 | |
| VAL-15 | Country | Chosen from a fixed list of countries; "United States" first and default | |

- **VAL-GEN-01** Request validation failures SHALL return 422 with the generic message "Invalid request format.
  Please check your input and try again." and SHALL NOT echo submitted values (which may contain PHI or
  passwords).
- **VAL-GEN-02** Each form SHALL validate on submit, show the message under the field, and keep the user's
  input. The submit button SHALL be disabled while the request is in flight.
