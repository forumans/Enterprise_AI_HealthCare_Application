## ADDED Requirements

### Requirement: Backend unit test coverage gate
The backend test suite SHALL use `pytest` with `pytest-asyncio` and `httpx` as the async test client. The overall coverage gate SHALL be at least 70%. The auth and RBAC modules SHALL achieve at least 90% coverage.

#### Scenario: Coverage gate passes
- **GIVEN** all backend unit tests pass
- **WHEN** `pytest --cov` is run
- **THEN** the overall coverage report SHALL show ≥ 70% and the coverage for `app/core/security.py` and `app/core/dependencies.py` SHALL show ≥ 90%

---

### Requirement: RBAC negative tests — wrong role returns 403
The test suite SHALL include tests that verify each role-protected endpoint returns `403 Forbidden` when called by a user with an insufficient role.

#### Scenario: PATIENT cannot access admin endpoint
- **GIVEN** a test client authenticated as a PATIENT
- **WHEN** `GET /api/admin/users` is called
- **THEN** the response status SHALL be 403

#### Scenario: DOCTOR cannot book appointments
- **GIVEN** a test client authenticated as a DOCTOR
- **WHEN** `POST /api/appointments` is called
- **THEN** the response status SHALL be 403

---

### Requirement: Cross-tenant isolation tests
The test suite SHALL include integration tests that verify cross-tenant access returns 403 or empty results and never returns foreign-tenant data.

#### Scenario: Tenant A token blocked from Tenant B resource
- **GIVEN** a token for a user in Tenant A and the ID of a resource belonging to Tenant B
- **WHEN** the Tenant A token is used to request the Tenant B resource
- **THEN** the response status SHALL be 403 or 404 and the response body SHALL NOT contain any Tenant B data

---

### Requirement: Auth security tests
The test suite SHALL include tests for: wrong password returning 401 with "Invalid credentials", expired token returning 401, and identical error messages for both "user not found" and "wrong password" (anti-enumeration).

#### Scenario: Wrong password returns 401
- **GIVEN** a real user account in the system
- **WHEN** `POST /auth/login` is called with the correct email and wrong password
- **THEN** the response SHALL be `401 {"detail": "Invalid credentials"}`

#### Scenario: Non-existent user returns same 401 message
- **GIVEN** an email that does not exist in the system
- **WHEN** `POST /auth/login` is called with that email
- **THEN** the response SHALL be `401 {"detail": "Invalid credentials"}` — identical to the wrong-password response

#### Scenario: Expired token returns 401
- **GIVEN** a JWT whose `exp` claim is in the past
- **WHEN** a protected endpoint is called with that token
- **THEN** the response SHALL be `401 Unauthorized`

---

### Requirement: Frontend unit tests with Vitest
Frontend unit tests SHALL use Vitest with `@testing-library/react` and `msw` for API mocking. The test suite SHALL cover: `useAuth` hook (login, logout, token storage), `ProtectedRoute` component (redirect on no token, redirect on wrong role), and utility functions in `utils/index.ts`.

#### Scenario: ProtectedRoute redirects when no token
- **GIVEN** no authenticated session (token is null)
- **WHEN** `ProtectedRoute` with `allowedRoles={["PATIENT"]}` renders
- **THEN** `mockNavigate` SHALL have been called with `"/"` and `{ replace: true }`

#### Scenario: Token never stored in browser storage
- **GIVEN** a successful login response
- **WHEN** `login(mockLoginResponse)` is called
- **THEN** `localStorage.getItem("token")` SHALL be null and `sessionStorage.getItem("token")` SHALL be null

---

### Requirement: Integration test for full appointment booking flow
The test suite SHALL include an integration test that exercises the complete booking flow against a real (test) PostgreSQL database: patient books appointment → slot becomes BOOKED → doctor confirms → patient cancels → slot reverts to AVAILABLE.

#### Scenario: Full appointment lifecycle
- **GIVEN** a test database with a doctor, patient, and an AVAILABLE slot
- **WHEN** the patient books, the doctor confirms, and the patient cancels the appointment
- **THEN** the appointment status SHALL follow SCHEDULED → CONFIRMED → CANCELLED and the slot status SHALL end at AVAILABLE

---

### Requirement: Playwright E2E tests for critical user journeys
The project SHALL include Playwright E2E tests for: patient books and cancels an appointment, doctor sets availability and views appointments, admin deletes and restores a user. These tests SHALL run against live local backend (port 8000) and frontend (port 5173).

#### Scenario: Patient booking journey passes
- **GIVEN** the backend and frontend are running locally
- **WHEN** the Playwright test navigates to `/`, logs in as a patient, and completes the booking flow
- **THEN** the new appointment SHALL appear in the appointments list and the test SHALL pass without assertion failures

---

### Requirement: Security tests for injection and rate limiting
The test suite SHALL include: SQL injection attempt in the login email field (must return 401 or 422, never 200), rate limit test for the login endpoint (16th request within 1 minute must return 429).

#### Scenario: SQL injection rejected
- **GIVEN** a login request with `email: "' OR 1=1 --"` and any password
- **WHEN** `POST /auth/login` is called
- **THEN** the response status SHALL be 401 or 422 and SHALL NOT be 200

#### Scenario: Rate limit triggered on login
- **GIVEN** 15 consecutive login attempts with invalid credentials from the same IP
- **WHEN** the 16th attempt is made
- **THEN** the response status SHALL be 429

---

### Requirement: CI gates must pass before merge
The following checks SHALL all pass before any code is merged to `main`: `ruff check` (backend lint), `mypy app/` (backend type check), `pytest` with ≥ 70% coverage, `npx tsc --noEmit` (frontend type check), `npm run test` (frontend unit tests), `npm run build` (frontend build), Playwright critical paths, and a secrets scan.

#### Scenario: Linting failure blocks merge
- **GIVEN** a pull request with a Python style violation detected by `ruff`
- **WHEN** the CI pipeline runs
- **THEN** the lint check SHALL fail and the PR SHALL NOT be mergeable until the violation is fixed

#### Scenario: Type error blocks merge
- **GIVEN** a pull request introducing a TypeScript type error
- **WHEN** `npx tsc --noEmit` runs in CI
- **THEN** the type check SHALL fail and the PR SHALL NOT be mergeable
