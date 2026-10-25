# Feature 10 — Doctor: Weekly Appointments

**Roles:** D · **Route:** `/doctors/appointments` (doctor landing page) ·
**API:** `GET /doctors/me`, `GET /doctor/appointments/all?from_date=`, `POST /appointments/{id}/confirm`,
`DELETE /appointments/{id}`, `POST /appointments/{id}/reschedule` · **Depends on:** 07, F05, F06 ·
**Traces to:** `DOC-WEEK-01…07`

## 1. Purpose

A Monday-to-Sunday overview of the doctor's own appointments, with quick confirm / reschedule / cancel actions
and a patient details panel.

## 2. UI

`h2` "Weekly Appointments".

1. **Doctor Information** card (`h3`): Name, Specialty, License Number from `GET /doctors/me`.
2. **Patient Details** panel (only while an appointment is selected), shown above the week header: `h3`
   "Patient Details", red "✕ Close" button; fields (blue uppercase labels): "Patient Name:", "Date/Time:"
   (`MM/DD/YYYY, h:mm AM ZONE` clinic time), "Status:", and "Symptoms:" (the visit reason) when non-empty.
3. **Week navigation** card: "← Previous Week" · heading "<Mon D, YYYY> - <Mon D, YYYY>" (Monday–Sunday) with
   `ClinicTimeNote` · "Next Week →". Both buttons always enabled (past and future weeks viewable). Changing week
   closes the Patient Details panel.
4. **Week grid** card: "Loading appointments..." while loading; else 7 equal columns (Mon … Sun, clinic week).
   Today's column has a blue border and tint and a blue heading. Column heading: "Mon, Oct 26" style. Each
   appointment (sorted by time) shows:
   - time `hh:mm AM` (clinic time, muted);
   - patient name as a link-style button → opens Patient Details;
   - status text (teal; pink for `CANCELLED`);
   - actions: **"Confirm"** (blue, `SCHEDULED` only; "Confirming..."), **"Reschedule"** (amber,
     `SCHEDULED`/`CONFIRMED`), **"Cancel"** (red, `SCHEDULED`/`CONFIRMED`; "Cancelling...").
   - Empty day: muted "No appointments".

## 3. Behavior

- Week start = Monday of the clinic's current week; load with `GET /doctor/appointments/all?from_date=<Monday
  YYYY-MM-DD>` on mount and on week change.
- Appointments are grouped by the clinic-calendar day of `time` (F05), not the browser's day.
- **Confirm:** `confirm("Are you sure you want to confirm this appointment?")` → `POST /appointments/{id}/confirm`
  → reload → `alert("Appointment confirmed successfully")`; failure `alert("Failed to confirm appointment. Please
  try again.")`.
- **Cancel:** `confirm("Are you sure you want to cancel this appointment?")` → `DELETE` → close the panel if it
  showed that appointment → reload → `alert("Appointment cancelled successfully")`; failure
  `alert("Failed to cancel appointment. Please try again.")`.
- **Reschedule:** `RescheduleAppointmentModal` with `{id, doctorId, appointmentTime: time, patientName, reason:
  symptoms, status}`, no conflict list (the server still enforces the patient's other bookings). On success close
  the panel and reload.

## 4. API — `GET /doctor/appointments/all?from_date=YYYY-MM-DD` (D)

- Anchor = `from_date` or clinic today; range = clinic week (Monday 00:00 → next Monday 00:00) containing it.
- Caller's doctor profile (no profile → `[]`); appointments of that doctor in the tenant and range, not
  soft-deleted, joined to patients that are not soft-deleted, ordered by time.
- Item `{id, doctor_id, time: <ISO>, patient_name, symptoms: <notes or "">, status}`.

Related (not used by this screen): `GET /doctor/appointments?from_date=` — same week query restricted to
anchors between clinic today and today+30 (400 "Cannot request appointments earlier than today." /
"Cannot request appointments beyond 30 days."), items `{id, time, patient_name, symptoms}`;
`GET /doctor/appointments/upcoming` — appointments from now, `{id, time, patient_name, status, urgent: ""}`.

## 5. Acceptance criteria

- **F10-AC-01** Given appointments Mon 9 AM and Wed 3 PM this week, Then they appear in the Mon and Wed columns
  with their times; other days say "No appointments".
- **F10-AC-02** Given a `SCHEDULED` appointment, When confirmed, Then its status shows `CONFIRMED` and the Confirm
  button disappears.
- **F10-AC-03** Given a week spanning the autumn DST change, Then each appointment appears on its correct
  clinic-local day.
- **F10-AC-04** Given a click on a patient name, Then the Patient Details panel shows name, date/time, status and
  symptoms; "✕ Close" hides it; changing week hides it.
- **F10-AC-05** Given another doctor's appointment id, When this doctor calls confirm/cancel/reschedule, Then 403.

## 6. Reference implementation

`frontend/src/components/pages/DoctorAppointmentsPage.tsx`, `hooks/useAppointments.ts` (`loadDoctorData`),
`backend/app/api/routes/doctor.py` (`doctor_all_appointments`).
