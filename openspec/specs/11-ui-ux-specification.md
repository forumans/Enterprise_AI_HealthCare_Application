# 11 — UI / UX Specification

A single-page React application with a dark clinical theme, a sticky top bar, role-filtered dropdown menus,
breadcrumbs, and card-based pages. Screen-by-screen content is in the role documents (04–08); this document
defines the shell, shared components, interaction patterns and styling they all use.

## 1. Application shell

- **UI-SHELL-01 Top bar (sticky, `top: 0`, above content).** Left: logo (heart icon) and brand text
  (configurable; reference: "Peteti" / "Software Inc."). Next to it, for signed-in users only: the tenant
  (clinic) name, truncated with ellipsis and full name in a tooltip. Center: main menus. Right: decorative
  search pill, notification and profile icons, and "Sign Out" for signed-in users.
- **UI-SHELL-02 Main menus:** Home, Doctors, Patients, Support Staff, Admin. Home navigates to `/`; the others
  open a floating dropdown. Clicking outside closes it. The menu matching the current path prefix
  (`/doctors`, `/patients`, `/support`, `/admin`) is highlighted.
- **UI-SHELL-03 Submenu filtering.** Items marked "signed out" hide when a token exists; items marked with a role
  show only for that role and only when signed in (doc 05–08 menu tables). A signed-in patient opening "Doctors"
  sees no doctor items, and so on.
- **UI-SHELL-04 Content area.** Centered, max width 1240 px, full width below that. Pages other than Home show a
  breadcrumb line ("Home > Patients > Schedule Appointment", etc.).
- **UI-SHELL-05 Global status line.** Messages from the auth context appear at the top of the content and fade out
  after 5 seconds; for patients it also shows "Insurance: <provider>" and "Ins Id: <policy>".
- **UI-SHELL-06 Unknown routes** redirect to `/`.
- **UI-SHELL-07 Responsive.** Layouts collapse to a single column below 900 px and 760 px; tables scroll
  horizontally inside their card (`overflow-x: auto`) instead of breaking the page.

## 2. Visual design tokens

| Token | Value | Use |
|-------|-------|-----|
| `--bg` | `#0a1a2a` | page background (with blue radial gradients) |
| `--panel` | `rgba(9, 32, 52, 0.82)` | cards, table rows |
| `--text` | `#eaf5ff` | primary text |
| `--muted` | `#b4cce2` | secondary text, help, empty states |
| `--brand` | `#42b5f5` | primary buttons, links, table headers |
| `--brand-dark` | `#2793d3` | hover |
| `--accent` | `#49d7c2` | positive status (SCHEDULED/CONFIRMED/COMPLETED text, success) |
| `--danger` | `#ff90ab` | errors, CANCELLED, required asterisk |
| `--border` | `rgba(136, 194, 227, 0.36)` | card, input and table borders |
| Success green | `#28a745` | Available slot, Book/Activate buttons, newly booked row tint |
| Warning amber | `#f0a020` | Selected slot, Reschedule button, session-ended notice |
| Danger red | `#dc3545` | Booked slot, Cancel/Deactivate buttons |
| Neutral grey | `#6c757d` / `#94a3b8` | Unavailable slot / disabled buttons |

- **UI-STYLE-01** Font: "Plus Jakarta Sans" (Google Fonts) with "Segoe UI", sans-serif fallback.
- **UI-STYLE-02** Inputs: 10 px radius, dark fill `rgba(9,35,55,0.82)`, light text, border token. Cards: 16–20 px
  padding. Action buttons: small (12 px text, 4 px radius); primary actions 14 px text, 6–10 px radius.
- **UI-STYLE-03** Icons are Unicode symbols or text labels only; no icon library dependency.
- **UI-STYLE-04** Colors are never the only signal: slots and statuses also carry text labels; a legend explains
  calendar colors.

## 3. Forms

- **UI-FORM-01 Labeled field.** Label in bold, a required asterisk in `--danger` where required, an info icon
  whose tooltip shows the rule text ("Name must be 3-80 characters.", "Use 10-15 digits. Country code allowed.",
  …), the input, and an inline error message below it.
- **UI-FORM-02** Validate on submit (`VAL-GEN-02`); some fields (date of birth) also re-validate as the user types
  after the first submit attempt.
- **UI-FORM-03** Password fields have a show/hide toggle with an accessible label ("Show password" /
  "Hide password").
- **UI-FORM-04** Submit buttons show a busy label ("Searching...", "Booking...", "Saving...", "Sending...",
  "Rescheduling...") and are disabled while busy.
- **UI-FORM-05** Status messages: success in teal, error in pink. Success messages clear after a few seconds;
  error messages persist until the next action.
- **UI-FORM-06** Country is a dropdown of all countries with "United States" first.

## 4. Feedback and confirmations

- **UI-FB-01** Destructive or state-changing actions (cancel, confirm, deactivate/activate, change email) ask
  for confirmation in a dialog that names the person and the time or value affected.
- **UI-FB-02** Results of quick actions are announced with a brief alert or inline message using the exact texts
  in the role documents. The server's `detail` message SHALL be shown on failure when available; otherwise a
  generic "Failed to … Please try again."
- **UI-FB-03** Loading states: "Loading appointments...", "Loading prescription data...", skeleton cards on the
  home page.
- **UI-FB-04** Empty states use muted centered text ("No upcoming appointments", `No patients match "x"`).

## 5. Scrolling and focus behavior

- **UI-SCROLL-01** When picking a person reveals the next section further down the page, the page SHALL scroll
  smoothly to that section (`scrollIntoView({behavior: 'smooth', block: 'start'})`).
- **UI-SCROLL-02** Scroll targets SHALL have a top scroll margin (about 90 px) so the sticky top bar does not
  cover their heading.
- **UI-SCROLL-03** After a successful booking on the support staff screens, the page SHALL scroll back up to the
  new appointment's row (`SUP-PA-05`).
- **UI-SCROLL-04** Re-picking the same person scrolls again. Later list reloads (for example after editing a
  reason) SHALL NOT move the page.

## 6. Shared components

### 6.1 `UI-CMP-SEARCH` — Support search panel
Defined in `SUP-SRCH-01` … `SUP-SRCH-05`. Props: kind (patient | doctor), access token, selected id
(highlighted row), `onPick`, `embedded` (no card frame). Remounting it (changing its key) clears text and results.

### 6.2 `UI-CMP-ADMINSEARCH` — Admin account search
Defined in `ADM-SRCH-01` … `ADM-SRCH-03`. Accepts extra columns supplied by the page (Status, Action).

### 6.3 `UI-CMP-SLOTS` — Slot picker calendar
- 7 day columns starting today, 16 hourly cells per day (8 AM … 11 PM, local labels), week navigation with
  Previous (disabled at week 0) and Next (disabled at week 4); 5 weeks total.
- Loads `GET /doctor/availability/{doctor_id}/all`; reloads when the doctor or a refresh counter changes. Error:
  "Failed to load the doctor's availability."
- Cell state (see `rescheduleSlotState`): **past** (start ≤ now) → not clickable; **current** (the appointment's
  existing time, when rescheduling) → blue, tooltip "Current appointment time"; **available** (slot
  `AVAILABLE` and not a conflict) → green, clickable; **unavailable** otherwise → grey. The selected cell is
  amber with a white outline.
- Legend: Current (only when rescheduling), Selected, Available, Unavailable.
- Selection is reported as a local wall-clock key; callers convert it to UTC with `new Date(key).toISOString()`.

### 6.4 `UI-CMP-RESCHED` — Reschedule dialog
- Modal (`role="dialog"`, `aria-modal`, labelled by its title). Closes on "✕ Close" or a backdrop click, except
  while saving.
- Shows the unchanged details: patient, doctor, status, reason. Embeds `UI-CMP-SLOTS` for the same doctor with
  the current time and conflicts.
- Footer: "New time: <date time>" / "Select an available slot" and "Confirm Reschedule" (disabled until a slot is
  picked; "Rescheduling..." while saving). Calls `POST /appointments/{id}/reschedule`; on success runs the
  caller's refresh, announces "Appointment rescheduled to <date time>" and closes; on failure shows the server
  message inside the dialog.

### 6.5 `UI-CMP-BOOKGRID` — Patient booking grid
Defined in `PAT-BOOK-03` … `PAT-BOOK-05` (one-click booking variant used by patients).

### 6.6 `UI-CMP-AVAILGRID` — Availability management grid
Defined in `DOC-AVAIL-02/03`; reused by support staff with a chosen doctor.

### 6.7 Protected route
Renders its children only when the session role is in the allowed list; otherwise redirects to `/`.

## 7. Date and time display

- **UI-DT-01** Appointment date/time: weekday, month, day, year and time with AM/PM in **clinic time**
  (`BR-TIME-04`, `en-US` reference) with the zone, for example "Fri, Oct 23, 2026, 03:00 PM PDT". Booking and
  availability grids, week headings and "today" are clinic-calendar days.
- **UI-DT-02** Dates of birth from the API (`YYYY-MM-DD`) SHALL be shown as `MM/DD/YYYY` by string reformatting,
  never through a `Date` round-trip, which can shift the day across time zones.
- **UI-DT-03** Server timestamps without an offset SHALL be parsed as UTC (`parseServerDate`).
- **UI-DT-04** Every calendar SHALL show "All times are clinic time: <abbr> (<zone>)" directly under its week
  heading (component `ClinicTimeNote`), e.g. "All times are clinic time: EDT (America/New York)": the patient
  booking calendar, the support staff booking calendars, every Reschedule dialog, Manage Availability (doctor
  and support staff), the doctor's Weekly and Today's Appointments.

## 8. Accessibility

- **UI-A11Y-01** Every input has a `<label for>`; icon-only buttons have `aria-label`s.
- **UI-A11Y-02** Dialogs trap attention visually (backdrop) and are announced as modal.
- **UI-A11Y-03** Status notices use `role="status"`.
- **UI-A11Y-04** Interactive table names are real `<button>` elements (keyboard focusable), not clickable text.
- **UI-A11Y-05** Text contrast SHALL meet WCAG AA against the dark background.

## 9. Route catalog

| Route | Guard | Screen (spec) |
|-------|-------|---------------|
| `/` | none | Home (`AUTH-HOME`) |
| `/patients/login`, `/doctors/login`, `/support/login`, `/admin/login` | none | Login (`AUTH-LOGIN`) |
| `/forgot-password`, `/reset-password` | none | `AUTH-FP`, `AUTH-RP` |
| `/admin/setup` | none | First-Time Setup (`AUTH-BOOT-05`) |
| `/patients/register` | none | `AUTH-REGP` |
| `/doctors/register` | none | `AUTH-REGD` |
| `/patients/appointments` · `/prescriptions` · `/billing` · `/profile` | PATIENT | doc 05 |
| `/doctors/appointments` · `/today-appointments` · `/search-patients` · `/manage-availability` · `/profile` · `/consultation/:id` | DOCTOR | doc 06 |
| `/support/patient-appointments` · `/doctor-appointments` · `/doctor-availability` · `/profile` | SUPPORT_STAFF | doc 07 |
| `/admin/system-dashboard` · `/register-doctor` · `/register-patient` · `/register-admin` · `/register-support-staff` · `/reset-password` · `/deactivate` | ADMIN | doc 08 |
| `*` | none | redirect to `/` |
