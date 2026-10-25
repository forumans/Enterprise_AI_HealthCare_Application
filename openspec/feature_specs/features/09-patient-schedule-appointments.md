# Feature 09 — Patient: Schedule / Cancel Appointment

**Roles:** P · **Route:** `/patients/appointments` (patient landing page) ·
**API:** `GET /patient/patient/profile`, `GET /doctors`, `GET /doctor/availability/{id}/all`, `GET /appointments/all?include_cancelled=true`,
`POST /appointments`, `DELETE /appointments/{id}`, `POST /appointments/{id}/reschedule` ·
**Depends on:** 07, 08, F05, F06 (reschedule dialog) · **Traces to:** `PAT-INFO-01`, `PAT-BOOK-*`, `PAT-LIST-*`,
`PAT-CANCEL-01`, `PAT-RESCHED-01`

## 1. Purpose

The patient's home screen: see their details, book a slot with a doctor by clicking a green cell, and manage
their upcoming appointments (reschedule, cancel) and past visits.

## 2. UI — top to bottom

`h2` "Schedule / Cancel Appointment".

### 2.1 Patient Information card (`PAT-INFO-01`)
Shown once `GET /patient/patient/profile` has loaded. `h3` "Patient Information"; three labelled values:
**Name** (`full_name`), **Phone**, **Insurance** = "<provider> - <policy>" when both exist, else whichever exists,
else "Not specified".

While the appointment list is first loading, the rest of the page is replaced by a card "Loading appointments...".

### 2.2 Book New Appointment card

1. **Select Doctor \*** — `<select>` with a disabled placeholder "Select a doctor" and one option per doctor from
   `GET /doctors` (server order, by name), text "<name> - <specialty or 'General Practice'>". Load failure shows
   "Failed to load doctors." in pink under the select.
2. **Appointment Reason \*** — textarea (3 rows), placeholder "Please describe the reason for your appointment...".
3. **Week calendar** (`UI-CMP-BOOKGRID`):
   - Navigation: "Previous Week" (disabled, grey, at week 0) · "Week of M/D - M/D" + `ClinicTimeNote` ·
     "Next Week" (disabled at week 4). Week 0 starts **today** (clinic time); 5 weeks total.
   - Table: 7 columns, header = weekday short ("Mon") over `MM/DD` (past days' header grey `#94a3b8`, else blue);
     one cell per office hour, labelled "8:00 AM" … "11:00 PM". Past day columns have a faint grey background.
   - Availability = `GET /doctor/availability/{selected}/all?days=30`, reloaded when the doctor changes and after
     each booking / cancellation / reschedule; load failure → treat as no slots.
   - Cell state (first match wins):

| State | Rule | Color | Clickable |
|-------|------|-------|:-:|
| Past | earlier day, or today with cell hour ≤ current clinic hour | `#2a2a2a`, 50% opacity | no |
| Booked | the patient has a `SCHEDULED`/`CONFIRMED` appointment at that instant (±1 min), or booked it in this page session | red `#dc3545` | no |
| Available | a doctor is selected and the doctor's slot at that cell is `AVAILABLE` | green `#28a745` | yes |
| Unavailable | otherwise (no doctor, `BOOKED`, `BLOCKED`, no slot) | grey `#6c757d` | no |

   - Legend: Available (green), Booked (red), Unavailable (grey).
4. **Booking** (`PAT-BOOK-05`): clicking an available cell books immediately, no extra confirmation:
   - empty reason (after trim) → `alert("Please provide a reason for the appointment.")`; no doctor →
     `alert("Please select a doctor.")`;
   - `POST /appointments {doctor_id, slot: slotKeyToDate(cellKey, tz).toISOString(), reason: trimmed}`;
   - success: mark the cell booked for this session, clear the reason, reload availability and appointments,
     `alert("Appointment booked successfully!")`;
   - failure: `alert(<server detail> or "Failed to book appointment. Please try again.")` and reload availability
     (the slot may have been taken). A reason shorter than 5 characters is rejected by the server (422 generic
     message).

### 2.3 My Appointments card

`h3` "My Appointments". Data: `GET /appointments/all` (own appointments, non-deleted, with `doctor_name`), split by
`isAppointmentUpcoming` (F05).

**Upcoming (N)** (`h4`, blue): soonest first. Empty → "No upcoming appointments scheduled". Table columns:
Date & Time (format "weekday long, month long day, year at hh:mm AM ZONE" in clinic time), Doctor
(`doctor_name` or "Doctor"), Notes (reason or "No notes"), Status (teal; pink when `CANCELLED`), Action. For
`SCHEDULED`/`CONFIRMED` rows the Action cell has **"Reschedule"** (amber) and **"Cancel"** (red; "Cancelling..."
and grey while in flight, disabled).

**Past (N)** — heading "Past (<shown>)" or "Past (5 of <total>)" when collapsed with more than 5. Newest first,
same columns without Action, dimmed text (opacity 0.8). Empty → "No past appointments". Shows the latest 5; when
more than 5 exist a button toggles "Show More (<k> more)" / "Show Less (<k> hidden)".

### 2.4 Cancel (`PAT-CANCEL-01`)
`confirm("Are you sure you want to cancel this appointment?")` → `DELETE /appointments/{id}` → reload the list,
free the cell booked in this session (compare instants, F05), reload availability →
`alert("Appointment cancelled successfully")`; failure → `alert(<server detail> or "Failed to cancel appointment.
Please try again.")`.

### 2.5 Reschedule (`PAT-RESCHED-01`)
Opens `RescheduleAppointmentModal` (F06 §6.5) with `{id, doctorId, doctorName, appointmentTime, reason: notes,
status}` and `conflictingTimes` = times of the patient's other `SCHEDULED`/`CONFIRMED` appointments. On success:
reload appointments, clear session-booked cells, refresh the calendar.

## 3. Rules

All rules come from [07](07-appointment-lifecycle.md) (booking, reschedule, cancel) and
[08](08-doctor-availability.md) (slot states). Patient-specific:

- **PAT-BOOK-06** A patient SHALL NOT book a time where they already have a live appointment with any doctor (UI
  greys it; DB index `unique_patient_time` enforces it).
- The page loads `GET /appointments/all?include_cancelled=true`, so cancelled appointments stay visible under
  **Past** with status `CANCELLED` (pink) and no actions. Their times don't count as the patient's bookings in the
  calendar or as reschedule conflicts.

## 4. Acceptance criteria

- **F09-AC-01** Given a selected doctor with an available 2 PM slot tomorrow and the reason "Annual checkup", When
  the patient clicks 2:00 PM, Then "Appointment booked successfully!", the cell turns red, and the appointment is
  listed under Upcoming as `SCHEDULED`.
- **F09-AC-02** Given no reason, When an available cell is clicked, Then "Please provide a reason for the
  appointment." and no request.
- **F09-AC-03** Given another patient booked the slot first, When clicked, Then the alert shows "Requested slot is
  not available." and the grid refreshes to grey.
- **F09-AC-04** Given the patient has 10 AM with doctor A, When viewing doctor B's grid, Then B's 10 AM cell is red
  (not clickable).
- **F09-AC-05** Given an upcoming appointment, When cancelled, Then it disappears and its cell is green again.
- **F09-AC-06** Given 8 past appointments, Then 5 are shown with "Show More (3 more)".
- **F09-AC-07** Given week 4, Then "Next Week" is disabled; at week 0 "Previous Week" is disabled.
- **F09-AC-08** Given a browser in `Asia/Tokyo` and a clinic in `America/New_York`, Then the grid rows and all
  times are New York times and the note reads "All times are clinic time: EDT (America/New York)" (or EST).

## 5. Reference implementation

`frontend/src/components/pages/PatientAppointmentsPage.tsx`, `hooks/useAppointments.ts`, `hooks/useUserData.ts`,
`utils/index.ts` (`removeCancelledBooking`, `isAppointmentUpcoming`).
