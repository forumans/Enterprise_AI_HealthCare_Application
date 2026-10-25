# F06 — UI Shell, Design System, Routing and Shared Components

A single-page React app with a dark clinical theme, a sticky top bar with role-filtered dropdown menus,
breadcrumbs, and card-based pages. Screen content is in the feature files; this file defines what they share.

## 1. Application shell

### 1.1 Top bar (`AppHeader`, class `topbar`)

- Sticky (`position: sticky; top: 0; z-index: 2`), horizontal gradient `#1e3a5f → #2c5282 → #1e3a5f`,
  2 px bottom border `#4a90e2`, padding 14 px 24 px, shadow.
- **Left:** logo (animated "💖" heart emoji, 40 px) and brand text: "Peteti" (name) over "Software Inc." (tagline).
  Brand text is configurable per deployment.
- **Tenant name** (signed-in users only, from `GET /tenants/current`): positioned right of the brand, max 280 px,
  single line with ellipsis, full name in a `title` tooltip.
- **Center:** main menu buttons "Home", "Doctors", "Patients", "Support Staff", "Admin" (class
  `top-menu-button`; the one matching the current path prefix gets `active-main`: blue `#4a90e2` fill).
  "Home" navigates to `/` and closes menus; the others toggle a floating dropdown under the button. A
  `mousedown` outside any `.menu-item-container` closes it. Clicking a submenu link navigates and closes it.
- **Right:** decorative search pill "🔍 Search", "🔔", "👤", and a "Sign Out" button for signed-in users.

Active main menu by path prefix: `/doctors*` → Doctors, `/patients*` → Patients, `/support*` → Support Staff,
`/admin*` → Admin, otherwise Home.

### 1.2 Submenus (`config/menu.ts`)

An item marked **signed out** is hidden when a token exists. An item marked with a role shows only when signed
in with that role. Items appear in this order:

| Main menu | Item label → route | Visibility |
|-----------|--------------------|-----------|
| Doctors | Login → `/doctors/login`; Register → `/doctors/register` | signed out |
| | Weekly Appointments → `/doctors/appointments`; Today's Appointments → `/doctors/today-appointments`; Search Patients → `/doctors/search-patients`; Manage Availability → `/doctors/manage-availability`; Update Profile → `/doctors/profile` | DOCTOR |
| Patients | Login → `/patients/login`; Register → `/patients/register` | signed out |
| | Schedule Appointment → `/patients/appointments`; Prescriptions → `/patients/prescriptions`; Billing → `/patients/billing`; Update Profile → `/patients/profile` | PATIENT |
| Support Staff | Login → `/support/login` | signed out |
| | Patient Appointments → `/support/patient-appointments`; Doctor Appointments → `/support/doctor-appointments`; Doctor Availability → `/support/doctor-availability`; Update Profile → `/support/profile` | SUPPORT_STAFF |
| Admin | Login Admin → `/admin/login` | signed out |
| | System Dashboard → `/admin/system-dashboard`; Register Doctor → `/admin/register-doctor`; Register Patient → `/admin/register-patient`; Register Admin → `/admin/register-admin`; Register Support Staff → `/admin/register-support-staff`; Reset Password / Email → `/admin/reset-password`; Deactivate → `/admin/deactivate`; Clinic Settings → `/admin/clinic-settings` | ADMIN |

A signed-in user opening another role's menu sees an empty dropdown. The current route's submenu link is
highlighted (`active-submenu`).

### 1.3 Page layout (`AppLayout`)

- Content area centered, `max-width: 1240px`, padding 20 px; full width below that.
- Every page except `/` shows a breadcrumb bar (bordered panel) with the label from §3.
- **Global status line:** when the auth context's `status` string is non-empty it is shown at the top of the
  content (class `status fade-out`, 5 s fade-in/out animation). For patients it also shows
  "Insurance: <provider>" and "Ins Id: <policy>" lines when present. The initial "Ready." status clears after
  1 s. Non-error statuses clear after 10 s; statuses containing "failed", "Error" or "Authentication failed" stay.
- Login pages are rendered **without** `AppLayout` (no breadcrumb / status line); they show their own messages.

### 1.4 Routing (`App.tsx`)

| Route | Guard | Screen | Spec |
|-------|-------|--------|------|
| `/` | none | Home | [01](../features/01-home-page.md) |
| `/patients/login`, `/doctors/login`, `/support/login`, `/admin/login` | none (no layout) | Login | [02](../features/02-login-and-session.md) |
| `/forgot-password`, `/reset-password` | none | Password reset | [03](../features/03-password-reset.md) |
| `/patients/register` | none | Patient Registration | [04](../features/04-patient-self-registration.md) |
| `/doctors/register` | none | Doctor Registration | [05](../features/05-doctor-self-registration.md) |
| `/admin/setup` | none | First-Time Setup | [06](../features/06-first-admin-setup.md) |
| `/patients/appointments` | PATIENT | Schedule / Cancel Appointment | [09](../features/09-patient-schedule-appointments.md) |
| `/patients/prescriptions` | PATIENT | My Prescriptions & Medical Records | [13](../features/13-patient-prescriptions.md) |
| `/patients/billing` | PATIENT | Billing placeholder | [23](../features/23-placeholders.md) |
| `/patients/profile` | PATIENT | Update Profile | [17](../features/17-profiles.md) |
| `/doctors/appointments` | DOCTOR | Weekly Appointments | [10](../features/10-doctor-weekly-appointments.md) |
| `/doctors/today-appointments` | DOCTOR | Today's Appointments | [11](../features/11-doctor-today-appointments.md) |
| `/doctors/consultation/:appointmentId` | DOCTOR | Patient Consultation | [12](../features/12-consultation-clinical-records.md) |
| `/doctors/search-patients` | DOCTOR | Search Patients | [14](../features/14-doctor-search-patients.md) |
| `/doctors/manage-availability` | DOCTOR | Manage Availability | [08](../features/08-doctor-availability.md) |
| `/doctors/profile` | DOCTOR | Update Profile | [17](../features/17-profiles.md) |
| `/support/patient-appointments`, `/support/doctor-appointments` | SUPPORT_STAFF | Patient / Doctor Appointments | [16](../features/16-support-appointments.md) |
| `/support/doctor-availability` | SUPPORT_STAFF | Doctor Availability | [08](../features/08-doctor-availability.md) |
| `/support/profile` | SUPPORT_STAFF | Update Profile | [17](../features/17-profiles.md) |
| `/admin/system-dashboard` | ADMIN | System Dashboard | [18](../features/18-admin-dashboard.md) |
| `/admin/register-doctor`, `/register-patient`, `/register-admin`, `/register-support-staff` | ADMIN | Registration forms | [19](../features/19-admin-user-registration.md) |
| `/admin/reset-password`, `/admin/deactivate` | ADMIN | Account management | [20](../features/20-admin-account-management.md) |
| `/admin/clinic-settings` | ADMIN | Clinic Settings | [21](../features/21-clinic-settings-and-tenants.md) |
| `*` | none | redirect (replace) to `/` | |

**ProtectedRoute** renders its children only when `session.role` is in the allowed list; otherwise
`<Navigate to="/" replace />`. Guests have role `GUEST`.

Route-entry side effects: entering any path containing `/login` while signed in signs the user out and clears the
login form; entering any path containing `/register` clears the login and patient registration forms.

## 2. Design tokens and styling

| Token | Value | Use |
|-------|-------|-----|
| `--bg` | `#0a1a2a` | page background, under blue gradients (§2.1) |
| `--panel` | `rgba(9, 32, 52, 0.82)` | cards, table rows, dropdowns |
| `--text` | `#eaf5ff` | primary text |
| `--muted` | `#b4cce2` | secondary text, help, empty states |
| `--brand` | `#42b5f5` | primary buttons, links, table headers |
| `--brand-dark` | `#2793d3` | hover |
| `--accent` | `#49d7c2` | positive status text (SCHEDULED/CONFIRMED/COMPLETED), success |
| `--accent-soft` | `#133846` | |
| `--danger` | `#ff90ab` | errors, CANCELLED, required asterisk |
| `--danger-soft` | `rgba(86, 27, 41, 0.86)` | |
| `--border` | `rgba(136, 194, 227, 0.36)` | card, input and table borders |
| Success green | `#28a745` | available slot, Book / Activate / Confirm Reschedule |
| Warning amber | `#f0a020` | selected slot, Reschedule button, session-ended notice border |
| Danger red | `#dc3545` | booked slot (patient grid), Cancel / Deactivate / Close |
| Neutral grey | `#6c757d` unavailable slot; `#94a3b8` disabled/busy buttons; `#2a2a2a` past slot (50% opacity) | |

### 2.1 Global styles

- Font "Plus Jakarta Sans" (Google Fonts, weights 400–800) with "Segoe UI", sans-serif fallback.
- `body` background: `linear-gradient(180deg, rgba(8,25,40,.86), rgba(7,31,50,.9) 50%, rgba(10,44,67,.92))`
  over radial gradients `rgba(88,179,231,.42)` at 18% 14% and `rgba(35,124,171,.4)` at 78% 0%.
- Cards: 16 px radius, 20 px padding, gradient `var(--panel) → rgba(15,45,70,.9)`, shadow
  `0 10px 28px rgba(0,0,0,.28)`, 3 px top accent bar visible on hover, hover lift `translateY(-4px)`.
- Inputs/selects/textareas: 10 px radius, fill `rgba(9,35,55,0.82)`, text `#eef8ff`, border token, padding
  11 px 12 px, 14 px text. Labels bold 14 px `#d6ebfb`.
- Buttons: action buttons 12 px text / 4 px radius / padding 6 px 12 px; primary 14–16 px text, 6–10 px radius.
  Busy or disabled buttons turn `#94a3b8` with `not-allowed` cursor.
- Tables: collapsed borders with the border token; header text `--brand`; rows `--panel`; wrap in
  `overflow-x: auto`.
- **Responsive:** layouts collapse to one column below 900 px and 760 px; tables scroll horizontally inside their
  card; usable at 360 px wide.
- **UI-STYLE-01** Icons are Unicode symbols or text only; no icon library.
- **UI-STYLE-02** Color is never the only signal: every slot and status also has a text label; calendars have a
  legend.

## 3. Breadcrumb labels

| Path | Label |
|------|-------|
| `/` | (none shown) |
| `/patients/login` · `/patients/register` | "Home > Patients > Login" · "Home > Patients > Register" |
| `/patients/appointments` · `/prescriptions` · `/billing` · `/profile` | "Home > Patients > Schedule Appointment" · "… > Prescriptions" · "… > Billing" · "… > Update Profile" |
| `/doctors/login` · `/register` | "Home > Doctors > Login" · "Home > Doctors > Register" |
| `/doctors/appointments` · `/today-appointments` · `/search-patients` · `/manage-availability` · `/profile` · `/consultation/:id` | "Home > Doctors > Appointments" · "… > Today's Appointments" · "… > Search Patients" · "… > Manage Availability" · "… > Update Profile" · "… > Consultation" |
| `/support/login` · `/patient-appointments` · `/doctor-appointments` · `/doctor-availability` · `/profile` | "Home > Support Staff > Login" · "… > Patient Appointments" · "… > Doctor Appointments" · "… > Doctor Availability" · "… > Update Profile" |
| `/admin/setup` · `/system-dashboard` · `/register-doctor` · `/register-patient` · `/register-admin` · `/register-support-staff` · `/reset-password` · `/deactivate` · `/clinic-settings` | "Home > Admin > First-Time Setup" · "… > System Dashboard" · "… > Register Doctor" · "… > Register Patient" · "… > Register Admin" · "… > Register Support Staff" · "… > Reset Password / Email" · "… > Deactivate" · "… > Clinic Settings" |
| `/forgot-password` · `/reset-password` | "Home > Forgot Password" · "Home > Reset Password" |
| anything else | "Home" |

(The current code misses some of these; see GAP-11.)

## 4. Forms and feedback

- **UI-FORM-01 `LabeledField`** props: `id, label, helpText, value, onChange, type?, placeholder?, error?,
  autoComplete? (default "off"), required?, children?`. Renders: a label row (`<label for=id>` with a
  `--danger` "*" when required, and an info button `aria-label="<label> input rules"` whose CSS tooltip
  (`data-tip`) shows `helpText` on hover/focus); the error paragraph (class `field-error`, pink) **above** the
  input; then the input (or `children`). Password inputs get a show/hide toggle button
  (`aria-label` "Show password" / "Hide password", "👁️" / "🙈").
- **UI-FORM-02** Validate on submit; show each message under its field; keep the user's input. Some fields
  (dates of birth on admin forms) re-validate as the user types.
- **UI-FORM-03** Submit buttons show a busy label ("Searching...", "Booking...", "Saving...", "Sending...",
  "Updating...", "Creating...", "Rescheduling...", "Confirming...", "Cancelling...") and are disabled while busy.
- **UI-FORM-04 `StatusMessage`** `{message, type: 'success'|'error' (default error)}`: block with 12 px padding,
  6 px radius, 1 px border; success = text/border `#49d7c2` on `#49d7c220`; error = `#ff90ab` on `#ff90ab20`.
  Renders nothing for an empty message.
- **UI-FORM-05** Country fields are a `<select>` of the full country list with "United States" first.
- **UI-FB-01** State-changing actions (cancel, confirm, deactivate/activate, change email, clinic time zone)
  ask `window.confirm` with a question naming the person/time/value; quick results are announced with
  `window.alert` or inline messages using the exact strings in each feature file.
- **UI-FB-02** On failure show the server's `detail` when present; otherwise "Failed to … Please try again.".
- **UI-FB-03** Empty states use muted centered text.

## 5. Scrolling

- **UI-SCROLL-01** When picking a person reveals the next section lower on the page, scroll smoothly to it:
  `el.scrollIntoView({behavior: 'smooth', block: 'start'})`.
- **UI-SCROLL-02** Scroll targets have `scroll-margin-top: 90px` so the sticky bar doesn't cover them.
- **UI-SCROLL-03** Re-picking the same person scrolls again; later list reloads SHALL NOT move the page.

## 6. Shared components

### 6.1 `ClinicTimeNote`
Small (12 px, `#b4cce2`) line "All times are clinic time: <abbr> (<zone>)" (F05), `data-testid="clinic-time-note"`.
Shown under the heading of every calendar and on the doctor's appointment pages.

### 6.2 `SupportSearchPanel` (`UI-CMP-SEARCH`)
Props: `kind: "patient" | "doctor"`, `accessToken`, `onPick(row)`, `selectedId?`, `embedded?` (no card frame).
Remounting (changing its `key`) clears text and results.

- Label "Find Patient" / "Find Doctor"; `type="search"` input, placeholder
  "Enter a name, email or phone number, or * for everyone"; button "Search" ("Searching..." while busy). Enter
  submits.
- Validation ([15](../features/15-people-search.md)): trimmed term ≥ 2 characters or exactly `*`, else the
  error "Enter at least 2 characters of a name, email or phone number, or * to list everyone." (pink, 12 px).
- Calls `GET /support/patients?q=` or `GET /support/doctors?q=`; server errors show the server message.
- Results: "<N> patient(s)/doctor(s) found. Click a name to continue." (singular for 1), then a numbered table:
  - patients: `#`, Full Name (link-style `<button>`), Phone, Email, Date of Birth (`MM/DD/YYYY` by string
    reformat, "—" if empty), Gender, Insurance, City / State (`"City, State"`);
  - doctors: `#`, Full Name, Phone, Email, Specialty ("General Practice" if empty), License Number.
  Empty values show "—". The picked row is tinted `rgba(66,181,245,0.18)`.
- No results: `No patients match "<q>"` (or doctors), or for `*`: "No patients found" / "No doctors found".

### 6.3 `AdminUserSearch` (`UI-CMP-ADMINSEARCH`)
Props: `accessToken, results, onResults(rows|null), roleOrder?, onPick?, selectedId?, extraColumns?, resultsHint?`.

- "Role *" select ("Select a role" + options from `GET /admin/roles`, optionally filtered/ordered by `roleOrder`);
  "Search" input (placeholder "Name, email or phone number, or * for everyone"); button "Search"
  ("Searching..."). Changing the role clears results and errors.
- Validation: no role → "Please select a role"; term rule as §6.2 → same message text.
- Calls `GET /admin/users/search?role=&q=`.
- Results: "<N> found." + optional hint, numbered table `#`, Full Name (link button when `onPick`), Email, Phone,
  Address, Details (specialty and/or "DOB MM/DD/YYYY", joined by " · ", "—" if none), then extra columns.
- No results: `No <role label lower-case> match "<q>"` or `No <role label lower-case> found` for `*`.
- Role-load failure: "Failed to load roles".

### 6.4 `SlotPickerCalendar` (`UI-CMP-SLOTS`)
Props: `doctorId, accessToken, selectedKey|null, onSelect(key), currentTime?, conflictingTimes?: string[],
disabled?, refreshKey?`.

- Loads `GET /doctor/availability/{doctorId}/all?days=30` on mount and when `doctorId`, token or `refreshKey`
  change. Loading: "Loading availability..."; error: "Failed to load the doctor's availability." (pink, below).
- Week navigation: "Previous Week" (disabled at week 0) · heading "Week of M/D - M/D" + `ClinicTimeNote` ·
  "Next Week" (disabled at week 4). 5 weeks total; week 0 starts **today** (clinic time), not Monday.
- Grid: 7 columns (header weekday short + `MM/DD`), one cell per office hour (labels from `OFFICE_HOUR_SLOTS`).
- Cell state (`rescheduleSlotState`):
  1. **past** — cell start ≤ now → `#2a2a2a`, 50% opacity, not clickable;
  2. **current** — cell key = the appointment's current time → blue `#42b5f5`, tooltip "Current appointment time";
  3. **available** — server status `AVAILABLE` and not in `conflictingTimes` → green `#28a745`, clickable;
  4. **unavailable** — anything else → grey `#6c757d`.
  The selected cell is amber `#f0a020` with a 2 px white outline.
- Legend: "Current" (only when `currentTime` given), "Selected", "Available", "Unavailable".
- Reports selection as a clinic cell key; callers convert with `slotKeyToDate(key, tz).toISOString()`.

### 6.5 `RescheduleAppointmentModal` (`UI-CMP-RESCHED`)
Props: `target {id, doctorId, appointmentTime, doctorName?, patientName?, reason?, status?}`, `accessToken`,
`onClose`, `onRescheduled` (async), `conflictingTimes?`.

- Full-screen backdrop `rgba(2,12,22,0.75)`; `role="dialog"`, `aria-modal="true"`, labelled by the title
  "Reschedule Appointment". Closes on "✕ Close" or a backdrop click — except while saving.
- Read-only details (shown when provided): Patient, Doctor, "Current Date/Time" (format F05 §3.2), Status, Reason.
- Embeds `SlotPickerCalendar` for `target.doctorId` with `currentTime = target.appointmentTime` and the conflicts.
- Footer: "New time: <date time>" or "Select an available slot"; button "Confirm Reschedule" (green; disabled
  until a slot is picked; "Rescheduling..." while saving).
- Confirm → `POST /appointments/{id}/reschedule {slot: <UTC ISO>}` → `await onRescheduled()` →
  `alert("Appointment rescheduled to <date time>")` → close. Failure: server message (pink) inside the dialog,
  dialog stays open.

## 7. Accessibility

- **UI-A11Y-01** Every input has a `<label for>`; icon-only buttons have `aria-label`s.
- **UI-A11Y-02** Dialogs are announced as modal and visually trap attention (backdrop).
- **UI-A11Y-03** Status notices use `role="status"` where they announce changes (session-ended notice).
- **UI-A11Y-04** Clickable names in tables are real `<button>` elements.
- **UI-A11Y-05** Text contrast meets WCAG AA on the dark background.

## 8. Acceptance criteria

- **F06-AC-01** Given a signed-in patient, When opening the Doctors menu, Then no items are listed; Patients
  shows exactly Schedule Appointment, Prescriptions, Billing, Update Profile.
- **F06-AC-02** Given a guest, When navigating to `/admin/system-dashboard`, Then they land on `/`.
- **F06-AC-03** Given any page but Home, Then a breadcrumb with the §3 label is shown.
- **F06-AC-04** Given the slot picker at week 0 at 10:20 clinic time, Then cells 8:00–10:00 today are past and
  "Previous Week" is disabled; at week 4 "Next Week" is disabled.
- **F06-AC-05** Given a reschedule that fails with 409, Then the dialog stays open and shows
  "Requested slot is not available.".
- **F06-AC-06** The access token is never written to `localStorage` or `sessionStorage`.

## 9. Reference implementation

`frontend/src/App.tsx`, `components/layout/*`, `components/common/*`, `config/menu.ts`,
`app/routeBreadcrumbs.ts`, `hooks/useNavigation.ts`, `styles.css`.
