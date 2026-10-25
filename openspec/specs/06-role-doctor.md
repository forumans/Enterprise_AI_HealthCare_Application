# 06 — Role: Doctor

A doctor manages their own schedule and availability, confirms and reschedules their own appointments, runs
consultations, and looks up patients' clinical history within their clinic.

## 1. Menu (top menu "Doctors")

| Item | Route | Shown when |
|------|-------|-----------|
| Login | `/doctors/login` | signed out |
| Register | `/doctors/register` | signed out |
| Weekly Appointments | `/doctors/appointments` | DOCTOR (landing page) |
| Today's Appointments | `/doctors/today-appointments` | DOCTOR |
| Search Patients | `/doctors/search-patients` | DOCTOR |
| Manage Availability | `/doctors/manage-availability` | DOCTOR |
| Update Profile | `/doctors/profile` | DOCTOR |
| (Consultation) | `/doctors/consultation/:appointmentId` | DOCTOR; opened from Today's Appointments |

- **DOC-GEN-01** Every doctor screen identifies the doctor by their own profile (`user_id` from the token).
  A doctor user without a doctor profile in the tenant gets empty lists or 404 "Doctor not found" — never
  another doctor's data.
- **DOC-GEN-02** Doctor screens show a doctor details card: Name, Phone, Specialization (or "N/A"), License
  Number.

## 2. Weekly Appointments (`/doctors/appointments`)

- **DOC-WEEK-01** Heading "Weekly Appointments" and a Doctor Information card (Name, Specialty, License Number)
  from `GET /doctors/me`.
- **DOC-WEEK-02** The view shows one clinic week, Monday to Sunday, starting with the current week. "← Previous
  Week" and "Next Week →" move by 7 days without limit (past weeks are viewable for reference).
- **DOC-WEEK-03** Data: `GET /doctor/appointments/all?from_date=YYYY-MM-DD` returns the doctor's non-deleted
  appointments in the clinic week containing `from_date` (id, time, patient name, symptoms/reason, status),
  sorted by time. Appointments of soft-deleted patients are excluded.
- **DOC-WEEK-04** Appointments are grouped under their day (in the viewer's local time) with time
  (`hh:mm AM/PM`), patient name and status (`CANCELLED` pink, others teal).
- **DOC-WEEK-05 Patient details.** Clicking a patient name opens a "Patient Details" panel above the week
  header: Patient Name, Date/Time, Status, Symptoms. A close button hides it. Changing week closes it.
- **DOC-WEEK-06 Actions per appointment:**
  - "Confirm" for `SCHEDULED` — asks "Are you sure you want to confirm this appointment?", calls
    `POST /appointments/{id}/confirm` (`BR-APT-02`), shows "Appointment confirmed successfully" or
    "Failed to confirm appointment. Please try again.", then reloads the week. Label "Confirming..." while busy.
  - "Reschedule" for `SCHEDULED`/`CONFIRMED` — opens the reschedule dialog (`UI-CMP-RESCHED`); reload on success.
  - "Cancel" for `SCHEDULED`/`CONFIRMED` — asks "Are you sure you want to cancel this appointment?", calls
    `DELETE /appointments/{id}`, shows "Appointment cancelled successfully" or "Failed to cancel appointment.
    Please try again."
- **DOC-WEEK-07** The server SHALL verify the appointment belongs to the calling doctor for confirm,
  reschedule, cancel and status change (403 otherwise).

## 3. Today's Appointments (`/doctors/today-appointments`)

- **DOC-TODAY-01** Heading "Today's Appointments" and the doctor details card (`GET /doctor/profile`).
- **DOC-TODAY-02** Data: `GET /doctor/appointments/today` — the doctor's non-deleted appointments within today's
  clinic-day bounds, sorted by time. The page shows only `SCHEDULED` and `CONFIRMED` ones.
- **DOC-TODAY-03** Each appointment is a card: time, patient name, reason, a status badge (`CONFIRMED` teal,
  `SCHEDULED` blue) and actions: Confirm (`SCHEDULED`), Reschedule, Cancel (both `SCHEDULED`/`CONFIRMED`) with
  the same confirmations and messages as `DOC-WEEK-06`, and "Consultation".
- **DOC-TODAY-04** "Consultation" is enabled only for `CONFIRMED` appointments (greyed, 50% opacity,
  not-allowed cursor otherwise; clicking does nothing) and opens `/doctors/consultation/{id}`. Saving the
  medical record SHALL also be refused by the server for appointments that aren't `CONFIRMED` ("Only confirmed
  appointments can be consulted.").
- **DOC-TODAY-05** Show an empty state when there are no appointments today.

## 4. Consultation (`/doctors/consultation/:appointmentId`)

- **DOC-CONS-01** Load `GET /doctor/appointments/{id}` (own, non-deleted appointment with non-deleted patient:
  id, time, patient id and name, status, notes) and `GET /prescriptions/pharmacies` in parallel.
  An id that is not a UUID returns 400 "Invalid appointment ID".
- **DOC-CONS-02** Heading "Patient Consultation". "Appointment Details" card: patient name, date/time, status,
  reason.
- **DOC-CONS-03** "Consultation Details" form:
  - Symptoms * (textarea, "Enter patient symptoms...") — VAL-11
  - Lab Results (optional, "Enter lab results (if any)...")
  - Diagnosis * ("Enter diagnosis...") — VAL-10
  - "Prescription (Optional)": Medication ("Enter medication name..."), Dosage ("e.g., 500mg, 1 tablet,
    5ml..."), Instructions ("e.g., Take twice daily with food..."), Pharmacy (dropdown "Select a pharmacy
    (optional)", each "<name> - <address>"; when the tenant has none, a disabled "No pharmacies available"
    option and the note "No pharmacies are currently available in the system.").
- **DOC-CONS-04** Save follows `BR-CLIN-02` … `BR-CLIN-05`:
  1. `POST /medical-records {patient_id, appointment_id, diagnosis, notes: symptoms, lab_results}` — the record
     SHALL be linked to **this** appointment, which must belong to the calling doctor;
  2. if medication and dosage are given, `POST /prescriptions {medical_record_id, medication_details,
     pharmacy_id}`;
  3. `PATCH /appointments/{id}/status {status: "COMPLETED"}`;
  4. show "Consultation completed successfully!" and go to Today's Appointments after 2 seconds.
  Any failure shows "Failed to save consultation details" and keeps the form.
- **DOC-CONS-05** Cancelled or missing appointment → `BR-CLIN-06` message, no form.
- **DOC-CONS-06** Medical record and prescription creation SHALL write audit entries (diagnosis is recorded in
  the audit log only as part of the clinical record, never in application logs).

## 5. Search Patients (`/doctors/search-patients`)

- **DOC-SRCH-01** Heading "Search Patients". Field "Search Patient by Name", help "Use at least first 2 letters
  of patient name, or * to list every patient." (VAL-12 with what = "a patient name"). Button "Search"
  ("Searching..." while busy).
- **DOC-SRCH-02** `GET /patients/search?q=` (DOCTOR, ADMIN) matches the patient name (`BR-SRCH`) within the
  tenant and returns one row per patient × appointment × record (demographics plus symptoms, diagnosis, lab
  results, medication, prescription date).
- **DOC-SRCH-03** "PATIENT DETAILS": one line per distinct patient — name (clickable), Age (from date of
  birth), Gender, Phone (formatted), Address. The first patient is selected automatically.
- **DOC-SRCH-04** Selecting a patient loads `GET /patient/prescriptions-full?patient_id=` and shows a table:
  PRESCRIPTION DATE, DOCTOR, NOTES, SYMPTOMS, DIAGNOSIS, LAB RESULTS, MEDICATION, PHARMACY — completed visits,
  newest first. "Loading prescription data..." while loading.
- **DOC-SRCH-05 Access.** A doctor may view the clinical history of any non-deleted patient in their own tenant
  (clinic-wide care team model). This SHALL be recorded as a read of PHI in the audit trail
  (`SEC-AUD-04`). Tenants requiring a stricter model MAY limit it to patients who have or had an appointment
  with the doctor.

## 6. Manage Availability (`/doctors/manage-availability`)

- **DOC-AVAIL-01** Heading "Manage Availability" and the doctor details card. Load the doctor's own id from
  `GET /doctors/me`, then slots from `GET /doctor/availability/{id}/all` (which tops up default slots,
  `BR-SLOT-01`).
- **DOC-AVAIL-02** Week grid starting today with "Previous Week" (disabled on the first week), "Week of M/D -
  M/D" and "Next Week". Each day column lists the 16 hourly cells.
- **DOC-AVAIL-03 Cell labels and actions.**

| Slot state | Label | Click action |
|-----------|-------|-------------|
| Past | (greyed, not clickable) | none |
| `BOOKED` | "Patient Booked" | disabled (`BR-SLOT-05`) |
| `BLOCKED` | "Blocked" | prompt "Enter reason for unblocking this slot:"; Cancel aborts; OK → unblock |
| `AVAILABLE` | "Available" | prompt "Enter reason for blocking this slot:"; Cancel aborts; OK → block with that reason |
| no slot | "Click to Add" | add as available |

  Each action calls `POST /doctor/availability {slot (UTC ISO), is_available, block_reason}` and shows the
  server message ("Slot blocked successfully", "Slot unblocked successfully", "Slot added successfully") or
  the error (`BR-SLOT-04`, `BR-SLOT-05`), then reloads the grid.
- **DOC-AVAIL-04** The same screen component is reused by support staff for any doctor (doc 07).

## 7. Update Profile (`/doctors/profile`)

- **DOC-PROF-01** Load `GET /doctor/profile`; fields Full Name (VAL-01), Phone (VAL-03), Specialty, License
  Number. Save with `PUT /doctor/profile`; show "Profile updated successfully!" (clears after a few seconds) or
  the error.
- **DOC-PROF-02** Empty full name or phone SHALL NOT overwrite stored values. Email is not editable here.
- **DOC-PROF-03** Profile updates SHALL write an audit entry.

## 8. Data the doctor may access (summary)

| Data | Access |
|------|--------|
| Own profile | read, update (not email) |
| Own appointments (with patient names and reasons) | read, confirm, reschedule, cancel, complete |
| Own slots | read, add, block, unblock |
| Other doctors | list (name, specialty, license) only |
| Patients of the clinic | search; read demographics and clinical history |
| Medical records / prescriptions | create for own appointments; read |
| Pharmacies | read |
| Patient documents | list/upload for patients of the clinic |
| Staff accounts, audit logs, other tenants | none |

## 9. Acceptance criteria

- **DOC-AC-01** Confirming a `SCHEDULED` appointment makes it `CONFIRMED`; confirming it again returns 400.
- **DOC-AC-02** A doctor cannot confirm, reschedule, cancel or complete another doctor's appointment (403).
- **DOC-AC-03** Blocking an available slot makes it `BLOCKED` and unbookable; unblocking restores `AVAILABLE`
  and clears the reason.
- **DOC-AC-04** Blocking a `BOOKED` slot returns 400 "Cannot modify a patient-booked slot."
- **DOC-AC-05** Blocking a slot 31 days ahead returns 400 "Cannot update slots beyond 30 days."
- **DOC-AC-06** A doctor with no slots who opens Manage Availability gets 16 slots per remaining day for the
  next 7 days; a day the doctor edited is not regenerated.
- **DOC-AC-07** Saving a consultation creates exactly one medical record for that appointment, an optional
  prescription, and sets the appointment `COMPLETED`; it then appears in the patient's prescriptions page.
- **DOC-AC-08** Weekly view for a week spanning a DST change shows appointments on the correct local days.
