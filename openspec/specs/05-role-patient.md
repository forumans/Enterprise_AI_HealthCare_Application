# 05 — Role: Patient

A patient manages their own appointments, sees their completed visits, diagnoses and prescriptions, and keeps
their profile up to date. A patient can only ever see or change their own data.

## 1. Menu (top menu "Patients")

| Item | Route | Shown when |
|------|-------|-----------|
| Login | `/patients/login` | signed out |
| Register | `/patients/register` | signed out |
| Schedule Appointment | `/patients/appointments` | signed in as PATIENT (landing page) |
| Prescriptions | `/patients/prescriptions` | signed in as PATIENT |
| Billing | `/patients/billing` | signed in as PATIENT (placeholder: "To be implemented") |
| Update Profile | `/patients/profile` | signed in as PATIENT |

Login and registration are specified in doc 04.

## 2. Schedule / Cancel Appointment (`/patients/appointments`)

Page heading: "Schedule / Cancel Appointment". Sections, top to bottom:

### 2.1 Patient Information card
- **PAT-INFO-01** Show the patient's Name, Phone and Insurance (provider and policy) from `GET /patient/me`.

### 2.2 Book New Appointment
- **PAT-BOOK-01 Doctor.** Dropdown "Select Doctor" listing the tenant's active doctors from `GET /doctors`,
  sorted by name, each shown as "<name> - <specialty or 'General Practice'>". Placeholder "Select a doctor".
  If loading fails, show the error under the dropdown.
- **PAT-BOOK-02 Reason.** Required textarea "Appointment Reason *", placeholder "Please describe the reason for
  your appointment..." (VAL-09).
- **PAT-BOOK-03 Week grid.** A 7-column grid starting today, one column per day (day name and date; past
  days greyed), each with the 16 hourly cells "8:00 AM" … "11:00 PM". Navigation "Previous Week" (disabled on
  the first week) / "Week of M/D - M/D" / "Next Week" (disabled after 4 weeks ahead, 5 weeks total).
  The grid loads the selected doctor's slots from `GET /doctor/availability/{doctor_id}/all`.
- **PAT-BOOK-04 Cell states and colors.**

| State | Color | Clickable |
|-------|-------|:-:|
| Past (earlier day, or today at or before the current hour) | dark grey, 50% opacity | no |
| Available (doctor slot `AVAILABLE`) | green `#28a745` | yes |
| Booked (patient's own live appointment, or booked this session) | red `#dc3545` | no |
| Unavailable (no doctor selected, `BOOKED`, `BLOCKED` or no slot) | grey `#6c757d` | no |

  A legend shows Available / Booked / Unavailable.
- **PAT-BOOK-05 Booking action.** Clicking an available cell books it immediately (no extra confirmation):
  - missing reason → "Please provide a reason for the appointment."; no doctor → "Please select a doctor.";
  - calls `POST /appointments {doctor_id, slot (UTC ISO), reason}` (rules `BR-APT-BOOK-*`);
  - on success: clear the reason, reload slots and appointments, show "Appointment booked successfully!";
  - on failure: "Failed to book appointment. Please try again." (the server's 409 message SHOULD be shown).
- **PAT-BOOK-06** A patient SHALL NOT be able to book a time where they already have a live appointment with
  any doctor (`BR-APT-BOOK-07`; enforced by `DATA-APT-02`).

### 2.3 My Appointments
- **PAT-LIST-01** Load all the patient's appointments with doctor names from `GET /appointments/all` and split
  them with `BR-APT-VIEW-01`.
- **PAT-LIST-02 Upcoming (N).** Table columns: Date & Time, Doctor, Notes (reason), Status, Action, sorted
  soonest first. Empty: "No upcoming appointments scheduled". For `SCHEDULED`/`CONFIRMED` rows show
  "Reschedule" and "Cancel" ("Cancelling..." while busy).
- **PAT-LIST-03 Past (N).** Same columns without Action, newest first, read-only, dimmed text. Show the latest
  5; a toggle "Show More (K more)" / "Show Less (K hidden)" reveals the rest. Status `CANCELLED` is shown in
  pink, others in teal.
- **PAT-CANCEL-01** Cancel asks "Are you sure you want to cancel this appointment?". On confirm call
  `DELETE /appointments/{id}`, reload appointments and slots, and show "Appointment cancelled successfully";
  on failure "Failed to cancel appointment. Please try again."
- **PAT-RESCHED-01** Reschedule opens the shared reschedule dialog (doc 11 `UI-CMP-RESCHED`) for that
  appointment, with the patient's other live appointment times passed as conflicts. On success, reload the
  lists and slots (rules `BR-APT-RESCHED-*`).

## 3. Prescriptions & Medical Records (`/patients/prescriptions`)

- **PAT-RX-01** Heading "My Prescriptions & Medical Records". Load `GET /patient/me` and
  `GET /patient/prescriptions-full` (no `patient_id`; the server uses the caller's own profile).
- **PAT-RX-02** Table columns: Appointment Time, Doctor, Status, Notes, Symptoms, Diagnosis, Lab Results,
  Medication, Pharmacy. Rows: completed visits only, newest first (`BR-CLIN-07`). Empty fields show blank.
- **PAT-RX-03** Show an empty-state message when there are no completed visits, and an error panel if loading
  fails.

## 4. Update Profile (`/patients/profile`)

- **PAT-PROF-01** Load `GET /patient/patient/profile` and prefill: Full Name (VAL-01), Phone (VAL-03), Date of
  Birth (VAL-06), Gender (VAL-08), Address Line 1/2, City, State/Province, Postal Code, Country (VAL-15),
  Insurance Provider, Policy Number.
- **PAT-PROF-02** Save with `PUT /patient/patient/profile`. Only provided fields change; full name and phone are
  never set to empty. Show success, or "Failed to update profile. Please try again." on error.
- **PAT-PROF-03** A patient SHALL NOT change their login email from this screen. Email changes go through an
  admin (`ADM-ACCT`), which enforces `BR-ACC-01`.
- **PAT-PROF-04** Profile updates SHALL write an audit entry with old and new values of changed fields.

## 5. Documents (API only in the reference build)

- **PAT-DOC-01** A patient MAY upload a document for themselves via `POST /patient/documents` (multipart field
  `file`). The file is stored in the private bucket under `documents/<tenant>/<patient>/…`
  (`DATA` §4.11) with its MIME type, and an audit entry is written.
- **PAT-DOC-02** A patient MAY list their own documents with short-lived (1 hour) download URLs via
  `GET /documents/{patient_id}`, and SHALL NOT list another patient's documents (`SEC-OWN-02`).
- **PAT-DOC-03** Uploads SHALL be limited to `MAX_UPLOAD_SIZE` (default 10 MB) and an allow-list of types
  (PDF, JPEG, PNG). There is no upload screen yet.

## 6. Data the patient may access (summary)

| Data | Access |
|------|--------|
| Own profile and insurance | read, update (not email) |
| Own appointments | read, book, reschedule, cancel |
| Doctors of the clinic (name, specialty, license number) | read |
| A doctor's slot states (available / booked / blocked, no patient names) | read |
| Own completed visits with symptoms, diagnosis, lab results, prescriptions, pharmacy | read |
| Pharmacies list | read |
| Own documents | upload, list |
| Any other patient's data, staff accounts, audit logs | none |

## 7. Acceptance criteria

- **PAT-AC-01** A patient books an available slot with a 5+ character reason; the appointment appears under
  Upcoming as `SCHEDULED` and the slot shows Booked.
- **PAT-AC-02** Booking with a 4-character reason is rejected by the server (422) even if the UI is bypassed.
- **PAT-AC-03** Booking a slot another patient took a moment earlier returns 409 "Requested slot is not
  available." and the grid refreshes.
- **PAT-AC-04** A patient cannot book two doctors at the same hour (409).
- **PAT-AC-05** Cancelling frees the slot, which is immediately bookable by another patient.
- **PAT-AC-06** Rescheduling keeps the reason and status, frees the old slot, books the new one.
- **PAT-AC-07** A patient calling `DELETE /appointments/{id}` or `/reschedule` for another patient's
  appointment gets 403; for another tenant's appointment, 404.
- **PAT-AC-08** The prescriptions page lists only `COMPLETED` visits.
- **PAT-AC-09** A patient token calling any `/admin/*`, `/support/*` or `/doctor/appointments*` endpoint gets 403.
