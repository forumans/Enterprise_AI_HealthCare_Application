# Feature 16 — Support Staff: Patient Appointments and Doctor Appointments

**Roles:** S · **Routes:** `/support/patient-appointments` (support landing page), `/support/doctor-appointments`
· **API:** `GET /support/appointments`, `GET /support/patients`, `GET /support/doctors`, `POST /appointments`
(with `patient_id`), `PATCH /appointments/{id}`, `POST /appointments/{id}/reschedule`, `DELETE /appointments/{id}`,
`GET /doctor/availability/{id}/all` · **Depends on:** 07, 08, 15, F06 · **Traces to:** `SUP-PA-*`, `SUP-DA-*`

## 1. Purpose

Front-desk staff manage appointments on behalf of a patient (patient mode) or a doctor (doctor mode): see the
person's upcoming appointments, edit reasons, reschedule, cancel, and book new appointments. They never see
clinical data.

## 2. One screen, two modes

| | Patient mode | Doctor mode |
|-|--------------|-------------|
| Route | `/support/patient-appointments` | `/support/doctor-appointments` |
| `h2` | "Patient Appointments" | "Doctor Appointments" |
| Intro (muted) | "Book, update, reschedule or cancel appointments on behalf of a patient." | "… on behalf of a doctor." |
| Subject search | patient (`SupportSearchPanel kind="patient"`) | doctor (`kind="doctor"`) |
| Counterpart (booking) | doctor, via embedded doctor search | patient, via embedded patient search |
| Table counterpart column | "Doctor" | "Patient" |
| Patient conflicts passed to calendars | the patient's other upcoming appointment times | none (server still enforces) |

Mounted with a distinct React `key` per mode, so switching routes resets state.

## 3. UI — top to bottom

1. Heading and intro (§2).
2. **Subject search panel** (F06 §6.2). Picking a person selects them (row highlighted), loads their appointments
   and **smoothly scrolls** to the Upcoming section (scroll margin 90 px). Re-picking scrolls again.
3. **Upcoming Appointments for <name> (<N>)** card (only after a pick):
   - Data: `GET /support/appointments?patient_id=<id>` or `?doctor_id=<id>`, then client-filtered by
     `isAppointmentUpcoming`. "Loading appointments..." while loading; empty "No upcoming appointments"; load error →
     `alert(<message>)`.
   - Columns: Date & Time (`Fri, Oct 23, 2026, 03:00 PM PDT`), Doctor/Patient, Reason ("No notes" if empty),
     Status (teal), Actions. Each row has `data-appointment-id`.
   - Actions (all disabled while that row is busy):
     - **Edit Reason** (blue): `prompt("Update the reason for this appointment:", current)`; Cancel or unchanged
       (trimmed) → nothing; trimmed < 5 → `alert("Reason must be at least 5 characters.")`; else
       `PATCH /appointments/{id} {reason: trimmed}` and reload (no scroll); error → `alert(<message>)`.
     - **Reschedule** (amber): `RescheduleAppointmentModal` with `{id, doctorId, appointmentTime, doctorName,
       patientName, reason, status}` and conflicts (§2, excluding this appointment). Success → reload list and
       calendar.
     - **Cancel** (red; "Working..." while busy): `confirm("Cancel <patient>'s appointment with <doctor> on <date
       time>?")` → `DELETE` → reload list and calendar → `alert("Appointment cancelled successfully")`; error →
       `alert(<message>)`.
   - The appointment just booked is tinted green `rgba(40,167,69,0.22)` until another subject is picked.
4. **Book New Appointment for <name>** card:
   1. Embedded counterpart search panel (no card frame), keyed by subject + a reset counter so it starts fresh
      for each subject and after each booking. **The counterpart is always chosen by search — never a dropdown of
      all patients (the API has no full patient list; `*` in the search lists everyone).**
   2. Picking a counterpart shows "Booking with doctor: <b>name</b> (<specialty or 'General Practice'>)" or
      "Booking with patient: <b>name</b> (<phone>)" and scrolls smoothly to this block; resets the selected slot.
   3. "Appointment Reason \*" textarea (id `support-reason`, 3 rows, placeholder "Describe the reason for the
      appointment...").
   4. Without a counterpart: muted "Select a doctor to see available slots." / "Select a patient to see available
      slots.". With one: `SlotPickerCalendar` for the booking doctor (patient mode: the counterpart; doctor mode:
      the subject), with patient conflicts in patient mode, disabled while booking, refreshed after changes.
   5. Footer: "Selected: <date time>" or "Select an available slot", and **"Book Appointment"** (green; disabled
      until a slot is chosen; "Booking..." while busy).
5. **Book:** trimmed reason < 5 → `alert("Please provide a reason of at least 5 characters.")`. Else
   `POST /appointments {doctor_id, patient_id, slot: <UTC ISO>, reason: trimmed}`. On success, in order:
   1. `alert("Appointment booked for <date time>")`;
   2. clear the selected slot and reason;
   3. reload the upcoming list and the calendar;
   4. close both search result lists and the calendar: clear the counterpart and remount **both** search panels
      (results and text cleared);
   5. scroll up to the new appointment's row (by `data-appointment-id`, falling back to the Upcoming card) and
      highlight it green.
   The subject stays selected so their list stays visible. On failure `alert(<server message>)` and keep the form.
6. Picking a different subject resets the booking form (counterpart, reason, slot, highlight).

## 4. API — `GET /support/appointments` (S)

- Exactly one of `patient_id` or `doctor_id`, else **422 "Provide exactly one of patient_id or doctor_id."**.
- Appointments of the tenant, not soft-deleted, `appointment_time >= start of clinic today`, joined to
  non-deleted patients and non-deleted doctors, filtered by the id, ordered by time.
- Item `{id, appointment_time, status, reason (notes or ""), patient_id, patient_name, doctor_id, doctor_name}`.

Booking, reschedule, reason edit and cancel are the shared endpoints of [07](07-appointment-lifecycle.md); the
audit rows name the staff member as `performed_by`.

## 5. Data support staff may access

| Data | Access |
|------|--------|
| Patients of the clinic | search; contact and insurance details only |
| Doctors of the clinic | search; contact, specialty, license |
| Appointments from today, with names and reasons | read, book, edit reason, reschedule, cancel |
| Any doctor's slots | read, add, block, unblock ([08](08-doctor-availability.md)) |
| Medical records, prescriptions, diagnoses, documents, audit logs | none (403) |
| Confirming or completing appointments | none |

## 6. Acceptance criteria

- **F16-AC-01** Given a patient found by email, When staff book with a doctor found by name, Then the appointment
  appears for the patient and doctor, and the audit row's `performed_by` is the staff member.
- **F16-AC-02** Given a successful booking on either screen, Then no search results and no calendar are visible,
  the page is scrolled to the new row, and it is highlighted.
- **F16-AC-03** Given the Doctor Appointments screen, Then the patient for a booking is picked from a search, never a dropdown.
- **F16-AC-04** Given a reason "abc", When editing, Then "Reason must be at least 5 characters." and no request.
- **F16-AC-05** Given a patient or doctor from another clinic, Then they never appear and booking them returns 404.
- **F16-AC-06** Given `GET /support/appointments` with both ids or neither, Then 422.
- **F16-AC-07** Given a support token, When calling `/patients/search`, `/patient/prescriptions-full`,
  `/medical-records/*` or `/admin/*`, Then 403.
- **F16-AC-08** Given patient mode, Then the slot picker greys the patient's other upcoming appointment times.

## 7. Reference implementation

`frontend/src/components/pages/SupportAppointmentsPage.tsx` (+ test), `backend/app/api/routes/support.py`.
