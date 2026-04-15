## ADDED Requirements

### Requirement: React 18 SPA with React Router DOM v6
The frontend SHALL be a single-page application built with React 18, TypeScript, and Vite. Client-side routing SHALL use React Router DOM v6. All routing logic SHALL be defined in `frontend/src/App.tsx`.

#### Scenario: SPA loads on unknown path
- **GIVEN** the CloudFront distribution has 403/404 error rules pointing to `/index.html`
- **WHEN** a user navigates directly to `/patient/appointments`
- **THEN** the browser SHALL load `index.html`, React Router SHALL initialise, and the correct page SHALL render if the user is authenticated

---

### Requirement: Role-based route protection via ProtectedRoute
The system SHALL provide a `ProtectedRoute` component that wraps any route requiring authentication. WHEN no JWT token is present in React Context, `ProtectedRoute` SHALL redirect to `/` using `<Navigate replace>`. WHEN the authenticated role is not in the `allowedRoles` list, `ProtectedRoute` SHALL redirect to `/`.

#### Scenario: Unauthenticated access to protected route
- **GIVEN** the user has no active session (token is null in React Context)
- **WHEN** the user navigates to `/patient/appointments`
- **THEN** the router SHALL redirect to `/` without rendering the appointments page

#### Scenario: Wrong role blocked from route
- **GIVEN** an authenticated PATIENT user
- **WHEN** the user navigates to `/admin/dashboard`
- **THEN** the router SHALL redirect to `/` because PATIENT is not in the ADMIN `allowedRoles` list

#### Scenario: Correct role gains access
- **GIVEN** an authenticated DOCTOR user
- **WHEN** the user navigates to `/doctor/appointments`
- **THEN** the DoctorAppointmentsPage SHALL render normally

---

### Requirement: Complete route table with 15 pages
The application SHALL define routes for all 15 pages: `/` (LoginPage, public), `/register` (PatientRegistrationPage, public), `/doctors/register` (DoctorRegistrationPage, public), `/admin/register` (AdminRegistrationPage, public), `/patient/appointments` (PATIENT), `/patient/medical-history` (PATIENT), `/patient/prescriptions` (PATIENT), `/patient/documents` (PATIENT), `/patient/profile` (PATIENT), `/doctor/appointments` (DOCTOR), `/doctor/availability` (DOCTOR), `/doctor/profile` (DOCTOR), `/admin/dashboard` (ADMIN), `/admin/users` (ADMIN), `/admin/appointments` (ADMIN).

#### Scenario: Public routes accessible without login
- **GIVEN** no authenticated session
- **WHEN** the user navigates to `/register`
- **THEN** the PatientRegistrationPage SHALL render without redirecting

#### Scenario: PATIENT cannot access DOCTOR routes
- **GIVEN** an authenticated PATIENT
- **WHEN** the user attempts to navigate to `/doctor/appointments`
- **THEN** the router SHALL redirect to `/`

---

### Requirement: JWT stored in React Context only
The JWT access token SHALL be stored exclusively in React Context using `useState`. The token SHALL NOT be stored in `localStorage`, `sessionStorage`, cookies, or any other browser storage API. On page refresh, the user SHALL be redirected to the login screen because in-memory state is cleared.

#### Scenario: Page refresh clears session
- **GIVEN** a logged-in user with a token in React Context
- **WHEN** the user refreshes the browser page
- **THEN** React Context state SHALL reset to null and the user SHALL see the login page

#### Scenario: Token not in browser storage
- **GIVEN** a user who has just logged in successfully
- **WHEN** `localStorage` and `sessionStorage` are inspected
- **THEN** no JWT token value SHALL be present in any browser storage

---

### Requirement: Environment variables for local development
The frontend SHALL support `VITE_API_BASE_URL` (empty by default, local dev only), `VITE_APP_NAME`, and `VITE_ENABLE_DEBUG`. In production, `VITE_API_BASE_URL` SHALL NOT be set — all API calls SHALL use relative `/api/...` paths proxied by CloudFront.

#### Scenario: Production build uses relative API paths
- **GIVEN** `VITE_API_BASE_URL` is not set in the production build
- **WHEN** the API client makes a request to `/api/auth/login`
- **THEN** the browser SHALL send the request to the same origin as the frontend, routed by CloudFront to API Gateway

#### Scenario: Local development uses absolute API URL
- **GIVEN** `VITE_API_BASE_URL=http://127.0.0.1:8000` in `.env.local`
- **WHEN** the API client makes a request
- **THEN** the request SHALL target `http://127.0.0.1:8000/api/...`

---

### Requirement: Production build outputs to dist/
`npm run build` SHALL produce a `dist/` directory containing `index.html` and hashed JS/CSS bundles with source maps disabled. The output SHALL be deployable to S3 as-is and serve as the CloudFront origin.

#### Scenario: Build succeeds with no type errors
- **GIVEN** the frontend codebase
- **WHEN** `npm run build` is executed
- **THEN** the build SHALL complete successfully, `dist/index.html` SHALL exist, and `npx tsc --noEmit` SHALL pass with zero errors
