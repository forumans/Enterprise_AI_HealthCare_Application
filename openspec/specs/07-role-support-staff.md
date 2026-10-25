# 07 — Role: Support Staff

Support staff (front desk, call center) manage appointments and doctor availability on behalf of patients and
doctors of their own clinic. They see patients' contact details but never clinical data. Accounts are created
only by an admin (`ADM-REG`); there is no self-registration.

## 1. Menu (top menu "Support Staff")

| Item | Route | Shown when |
|------|-------|-----------|
| Login | `/support/login` | signed out |
| Patient Appointments | `/support/patient-appointments` | SUPPORT_STAFF (landing page) |
| Doctor Appointments | `/support/doctor-appointments` | SUPPORT_STAFF |
| Doctor Availability | `/support/doctor-availability` | SUPPORT_STAFF |
| Update Profile | `/support/profile` | SUPPORT_STAFF |

## 2. Shared search panel (`UI-CMP-SEARCH`, used on every support screen)

- **SUP-SRCH-01** A card with label "Find Patient" or "Find Doctor", a search box (placeholder "Enter a name,
  email or phone number, or * for everyone") and a "Search" button ("Searching..." while busy). Pressing Enter
  submits.
- **SUP-SRCH-02** Validation per `BR-SRCH-01` with what = "a name, email or phone number". Matching per
  `BR-SRCH-02` (name, email, phone digits). Endpoints: `GET /support/patients?q=`, `GET /support/doctors?q=`.
- **SUP-SRCH-03** Results: "N patient(s)/doctor(s) found. Click a name to continue." then a numbered table:
  - patients: #, Full Name (link button), Phone, Email, Date of Birth (MM/DD/YYYY, no time-zone shift), Gender,
    Insurance, City / State;
  - doctors: #, Full Name (link button), Phone, Email, Specialty ("General Practice" if empty), License Number.
  Empty values show "—". No results: `No patients match "<q>"` or, for `*`, "No patients found".
- **SUP-SRCH-04** The picked person's row is highlighted. The panel can be embedded inside another card
  (no card frame).
- **SUP-SRCH-05** Patient search results SHALL NOT include clinical fields (diagnoses, records, prescriptions).

## 3. Patient Appointments (`/support/patient-appointments`)

Heading "Patient Appointments", text "Book, update, reschedule or cancel appointments on behalf of a patient."

- **SUP-PA-01 Pick the patient.** Search panel (patients). Clicking a name selects the patient, loads their
  appointments, and **scrolls the page smoothly** to the Upcoming Appointments section, leaving room for the
  sticky header.
- **SUP-PA-02 Upcoming Appointments for <name> (N).** Data: `GET /support/appointments?patient_id=` — the
  patient's non-deleted appointments from the start of today (clinic time), with patient and doctor names, then
  filtered client-side by `BR-APT-VIEW-01`. Table: Date & Time, Doctor, Reason ("No notes" if empty), Status,
  Actions. "Loading appointments..." while loading; "No upcoming appointments" when empty.
- **SUP-PA-03 Row actions:**
  - "Edit Reason" — prompt "Update the reason for this appointment:" prefilled; cancelled or unchanged → no-op;
    under 5 characters → "Reason must be at least 5 characters." (no request); else `PATCH /appointments/{id}
    {reason}` (`BR-APT-EDIT-01`) and reload.
  - "Reschedule" — opens the reschedule dialog; the patient's other upcoming appointment times are conflicts.
  - "Cancel" — confirm "Cancel <patient>'s appointment with <doctor> on <date time>?", then
    `DELETE /appointments/{id}`, reload, "Appointment cancelled successfully". Label "Working..." while busy.
  Buttons on a row are disabled while that row is busy.
- **SUP-PA-04 Book New Appointment for <name>.**
  1. A doctor search panel (embedded) — the doctor is chosen by search, not a dropdown. Picking a doctor
     highlights the row, shows "Booking with doctor: <name> (<specialty>)", and scrolls to the reason box.
  2. "Appointment Reason *" textarea (VAL-09).
  3. Slot picker calendar (`UI-CMP-SLOTS`) for the chosen doctor, with the patient's upcoming appointment times
     as conflicts; before a doctor is picked: "Select a doctor to see available slots."
  4. "Selected: <date time>" / "Select an available slot" and a "Book Appointment" button (disabled until a slot
     is chosen; "Booking..." while busy).
- **SUP-PA-05 Book.** `POST /appointments {doctor_id, patient_id, slot, reason}` (`BR-APT-BOOK-*`). On success:
  1. show "Appointment booked for <date time>";
  2. clear the reason and selected slot;
  3. reload the upcoming list and the calendar;
  4. **close both search result lists and the calendar**: the patient search panel and the doctor search panel
     reset (results and search text cleared), the chosen doctor is cleared;
  5. **scroll up to the new appointment's row**, which is highlighted green until another patient is picked.
  The selected patient stays selected so their upcoming list stays visible. On failure show the server message
  and keep the form.
- **SUP-PA-06** Picking a different patient resets the booking form (doctor, reason, slot, highlight) and starts a
  fresh doctor search.

## 4. Doctor Appointments (`/support/doctor-appointments`)

Same layout and behavior as §3 with the roles swapped. Heading "Doctor Appointments".

- **SUP-DA-01 Pick the doctor** with the doctor search panel; selecting scrolls to the doctor's upcoming
  appointments (`GET /support/appointments?doctor_id=`). Table counterpart column is Patient.
- **SUP-DA-02** Row actions as `SUP-PA-03`. No patient conflicts are passed to the reschedule calendar (the
  server still enforces `DATA-APT-02`).
- **SUP-DA-03 Book.** The patient is chosen with an embedded **patient search panel** (name, email, phone or `*`)
  — never a full dropdown of all patients, and the screen SHALL NOT download the full patient list. Picking a
  patient shows "Booking with patient: <name> (<phone>)" and scrolls to the reason box. Then reason, slot picker
  for the selected doctor, and Book — with the same post-booking behavior as `SUP-PA-05` (close search results
  and calendar, scroll to and highlight the new appointment).
- **SUP-DA-04** `GET /support/appointments` SHALL require exactly one of `patient_id` or `doctor_id`
  ("Provide exactly one of patient_id or doctor_id.", 422).

## 5. Doctor Availability (`/support/doctor-availability`)

- **SUP-AV-01** Heading "Doctor Availability", text "Block or unblock a doctor's slots on their behalf.
  Patient-booked slots can't be changed here."
- **SUP-AV-02** Doctor search panel; picking a doctor shows the Manage Availability grid (`DOC-AVAIL-02/03`) for
  that doctor, with every change sent as `POST /doctor/availability {slot, is_available, block_reason,
  doctor_id}` (`BR-SLOT-07`).

## 6. Update Profile (`/support/profile`)

- **SUP-PROF-01** Load `GET /support/profile` (full name, phone, email). Email is shown read-only (it is the
  login; only an admin changes it).
- **SUP-PROF-02** Fields Full Name (VAL-01) and Phone (VAL-03; the server enforces the same pattern). Save with
  `PUT /support/profile`; show "Profile updated successfully!" or the error. Writes an audit entry.

## 7. Data support staff may access (summary)

| Data | Access |
|------|--------|
| Own profile | read, update name and phone |
| Patients of the clinic | search; contact and insurance details only |
| Doctors of the clinic | search; contact, specialty, license |
| Appointments of the clinic (from today) with patient and doctor names and reasons | read, book, edit reason, reschedule, cancel |
| Slots of any doctor in the clinic | read, add, block, unblock |
| Medical records, prescriptions, diagnoses, documents, audit logs | none |
| Confirming or completing appointments | none (doctor only) |

## 8. Acceptance criteria

- **SUP-AC-01** Support staff book for a patient found by email; the appointment appears for the patient and
  the doctor; the audit entry names the staff member as `performed_by`.
- **SUP-AC-02** Booking without `patient_id` returns 422 "patient_id is required."
- **SUP-AC-03** Changing a doctor's slot without `doctor_id` returns 422 "doctor_id is required."
- **SUP-AC-04** A support staff token cannot read `/patients/search`, `/patient/prescriptions-full`,
  `/medical-records/*` or `/admin/*` (403).
- **SUP-AC-05** After a successful booking on either screen, no search results and no calendar are visible; the
  page is scrolled to the new appointment, which is highlighted.
- **SUP-AC-06** The Doctor Appointments screen never calls `GET /patients` (full patient list).
- **SUP-AC-07** A patient or doctor from another tenant never appears in search results and cannot be booked
  (404).
