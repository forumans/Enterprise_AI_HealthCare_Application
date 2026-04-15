## ADDED Requirements

### Requirement: No external icon libraries
The frontend SHALL NOT import from `lucide-react`, `react-icons`, or any other icon package. Visual indicators SHALL use Unicode symbols (✓, ✕, +, →), short text labels, or CSS-styled indicators. This keeps the bundle small and avoids build dependency errors.

#### Scenario: Build has no icon library imports
- **GIVEN** the frontend codebase
- **WHEN** all import statements are inspected
- **THEN** no import from `lucide-react`, `react-icons`, `heroicons`, or any icon package SHALL exist

---

### Requirement: Loading and error states on every data-fetching page
Every page component that fetches data SHALL render three distinct states: a loading indicator WHILE the query is in-flight, a `StatusMessage` error banner IF the query fails, and the normal data view WHEN data is available.

#### Scenario: Page shows loading state
- **GIVEN** a patient navigates to `/patient/appointments`
- **WHEN** the React Query hook is fetching
- **THEN** the component SHALL render a loading indicator instead of the appointments list

#### Scenario: Page shows error state
- **GIVEN** the API call for appointments fails
- **WHEN** React Query reports an error
- **THEN** the component SHALL render a `StatusMessage` with `type="error"` and a user-facing message

---

### Requirement: Controlled form inputs with inline validation
All form components SHALL use controlled inputs. Validation SHALL run in the submit handler, not on `required` alone. Errors SHALL display inline next to the relevant field via `LabeledField`. The form SHALL NOT submit if validation fails.

#### Scenario: Login form with empty email
- **GIVEN** the LoginPage form
- **WHEN** the user submits without an email
- **THEN** an inline error SHALL appear under the email field and the API SHALL NOT be called

#### Scenario: Invalid email format
- **GIVEN** the PatientRegistrationPage form
- **WHEN** the user submits with `"not-an-email"` in the email field
- **THEN** an inline validation error SHALL appear and the form SHALL NOT submit

---

### Requirement: Accessibility baseline
All form inputs SHALL have an associated `<label>` linked via `htmlFor`/`id`. All buttons SHALL have descriptive text or `aria-label`. Status badges SHALL convey state via both colour and text. All interactive elements SHALL be keyboard-navigable.

#### Scenario: Screen reader identifies form fields
- **GIVEN** the LoginPage form
- **WHEN** a screen reader focuses the email input
- **THEN** the associated label text SHALL be announced

#### Scenario: Status badge readable without colour
- **GIVEN** an AppointmentStatusBadge showing "CONFIRMED"
- **WHEN** the badge is inspected
- **THEN** it SHALL display both the status text and a colour indicator

---

### Requirement: AppLayout wraps all authenticated pages
All authenticated routes SHALL render inside `AppLayout`. `AppLayout` SHALL render `AppHeader` (user name, role badge, logout button) and a breadcrumb trail above the page content.

#### Scenario: Authenticated page has header and breadcrumbs
- **GIVEN** an authenticated PATIENT at `/patient/appointments`
- **WHEN** the page renders
- **THEN** `AppHeader` SHALL be visible with the user's name, role badge, and a logout button

#### Scenario: Logout clears session
- **GIVEN** an authenticated user inside AppLayout
- **WHEN** the user clicks Logout
- **THEN** auth state SHALL be cleared from React Context and the user SHALL be redirected to `/`

---

### Requirement: AppointmentStatusBadge uses text and colour
`AppointmentStatusBadge` SHALL render a visually distinct badge for SCHEDULED, CONFIRMED, COMPLETED, and CANCELLED statuses. Each badge SHALL display both the status name as text and a distinct colour.

#### Scenario: Distinct badge for each status
- **GIVEN** appointments with four different statuses
- **WHEN** each badge renders
- **THEN** each SHALL be visually distinguishable by both colour AND displayed text label
