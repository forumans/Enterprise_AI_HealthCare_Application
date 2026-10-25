# Feature 11 — Doctor: Today's Appointments

**Roles:** D · **Route:** `/doctors/today-appointments` · **API:** `GET /doctor/profile`,
`GET /doctor/appointments/today`, confirm / cancel / reschedule (07) · **Depends on:** 07, 12, F06 ·
**Traces to:** `DOC-TODAY-01…05`

## 1. Purpose

The doctor's work list for the current clinic day, with the entry point to the consultation.

## 2. UI

1. `h2` "Today's Appointments" with `ClinicTimeNote` directly under it.
2. **Doctor Details** card (`h3`): "Name:", "Phone:" (formatted: 10 digits → `(555) 123-4567`; more digits →
   `+<cc> (555) 123-4567`; otherwise as stored; empty → "N/A"), "Specialization:" ("N/A"), "License Number:"
   ("N/A"). Source `GET /doctor/profile`; "Loading doctor information..." while loading.
3. List card:
   - "Loading today's appointments..." · error "Failed to load today's appointments" (pink) · empty
     "No appointments for today".
   - Only `SCHEDULED` and `CONFIRMED` appointments are shown, sorted by time. Each is a bordered card (border teal
     for `CONFIRMED`, blue for `SCHEDULED`) with a 3-column layout:
     - time badge `hh:mm AM` (teal background for `CONFIRMED`, blue for `SCHEDULED`);
     - patient name (`h4`), "Reason: <reason>" when present, status pill (teal/blue tint);
     - actions: "Confirm" (`SCHEDULED`; "Confirming..."), "Reschedule" (amber), "Cancel" (red; "Cancelling..."),
       and **"Consultation"**.
   - **Consultation** link → `/doctors/consultation/{id}`; enabled only for `CONFIRMED` (teal). For other statuses
     it is greyed (`#94a3b8`, opacity 0.5, `not-allowed` cursor, `aria-disabled="true"`, tooltip "Confirm the
     appointment to start the consultation") and clicking does nothing.
- Confirm / Cancel / Reschedule behave exactly as [10](10-doctor-weekly-appointments.md) §3 (same prompts and
  alerts), refreshing this list afterwards.

## 3. API — `GET /doctor/appointments/today` (D)

Range = clinic-day bounds of clinic today (23/25 h on DST days). Caller's doctor profile (none → `[]`); that
doctor's tenant appointments in range, not soft-deleted, with non-deleted patients, ordered by time. Item
`{id, doctor_id, time, patient_name, reason: <notes or "">, status, urgent: ""}`. The server returns all statuses;
the page filters.

## 4. Acceptance criteria

- **F11-AC-01** Given a `SCHEDULED` and a `CONFIRMED` appointment today and one `COMPLETED`, Then only the first
  two are listed; Consultation is enabled only on the confirmed one.
- **F11-AC-02** Given a clinic in `America/Los_Angeles` at 11:30 PM PT, Then "today" is the PT date.
- **F11-AC-03** Given a `SCHEDULED` appointment, When the greyed Consultation link is clicked, Then nothing
  happens.
- **F11-AC-04** Given no appointments today, Then "No appointments for today".

## 5. Reference implementation

`frontend/src/components/pages/TodayAppointmentsPage.tsx` (+ test), `backend/app/api/routes/doctor.py`
(`doctor_appointments_today`, `get_doctor_profile`).
