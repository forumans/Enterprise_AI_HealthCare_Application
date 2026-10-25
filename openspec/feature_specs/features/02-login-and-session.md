# Feature 02 — Login, Sign-Out and Session

**Roles:** all four, from the guest state · **Routes:** `/patients/login`, `/doctors/login`, `/support/login`,
`/admin/login` · **API:** `POST /auth/login`, `GET /admin/setup-status`, `GET /tenants/current` ·
**Depends on:** F03, F04 (rate limits), F06 · **Traces to:** `AUTH-LOGIN-*`, `AUTH-SESS-*`, `SEC-AUTHN-*`

## 1. Purpose

One login page per role. Signs the user in, keeps the session in memory, routes them to their landing page,
signs them out on request or when the server ends the session.

## 2. UI — login page

Login pages are **not** wrapped in `AppLayout` (no breadcrumb, no global status line).

| Route | Role | Title (`h2`) | Subtitle (muted) | Below the form |
|-------|------|--------------|------------------|----------------|
| `/patients/login` | PATIENT | "Patient Login" | "Access your medical records and appointments" | link "Don't have an account? Register" → `/patients/register` |
| `/doctors/login` | DOCTOR | "Doctor Login" | "Manage your appointments and patient consultations" | link "New doctor? Register here" → `/doctors/register` |
| `/support/login` | SUPPORT_STAFF | "Support Staff Login" | "Manage appointments and availability on behalf of patients and doctors" | text "Support staff accounts are created by an administrator" |
| `/admin/login` | ADMIN | "Admin Login" | "System administration and management" | while `GET /admin/setup-status` says `setup_required: true`: link "First time setup? Create the first administrator" → `/admin/setup`; otherwise (or on error) text "Administrator accounts are created by an existing administrator" |

Every login page also shows a centered link "Forgot password?" → `/forgot-password` between the form and the
register line.

### 2.1 Form

| Field | id | Type / autocomplete | Placeholder | Help tooltip | Validation (on submit) |
|-------|----|----------------------|-------------|--------------|-----------------------|
| Email | `email` | `email` / `email` | "your.email@example.com" | "Enter your registered email address" | `^[^\s@]+@[^\s@]+\.[^\s@]+$`; error under field "Please enter a valid email address" (shown only after a submit attempt and while the email is non-empty and invalid) |
| Password | `password` | `password` with show/hide toggle / `current-password` | "Enter your password" | "Enter your password" | length ≥ 8, else page message "Password must be at least 8 characters." (no request sent) |

Submit button (class `button-primary`): "Login as Patient", "Login as Doctor", "Login as Admin",
"Login as Support Staff". Disabled while either field is empty or the email error is showing.

### 2.2 Messages on the login page

- **Session-ended notice** — when the page was reached through a forced sign-out (`location.state.notice`) and no
  other status is showing: amber box (`role="status"`, left border 4 px `#f0a020`, background
  `rgba(240,160,32,0.12)`, text `#ffd28a`) with "Your session has ended. Please sign in again."
- **Status** — the auth context status rendered as `StatusMessage`; success style when it contains (case-insensitive)
  "success", "successfully", "completed", "registered", "confirmed", "updated" or "created", else error style.
- Opening a login page clears the status. Errors stay until the next attempt.

## 3. Behavior

### 3.1 Login flow

1. Client validates (§2.1), then `POST /auth/login {email, password, remember_me: false}`.
2. **Role-page check (AUTH-LOGIN-05):** if the returned `role` differs from the page's role, discard the token and
   show "Invalid credentials" (generic — never reveal which role the email belongs to).
3. On success, store the session in memory:
   `{accessToken: access_token, role, tenantId: tenant_id, userName: user_name, insuranceProvider:
   insurance_provider, insurancePolicyId: insurance_policy_id, clinicTimezone: clinic_timezone}`; clear status;
   navigate to the landing page: PATIENT `/patients/appointments`, DOCTOR `/doctors/appointments`,
   SUPPORT_STAFF `/support/patient-appointments`, ADMIN `/admin/system-dashboard`.
4. On error show the server's `detail` (e.g. "Authentication failed", or the 429 message).
5. After sign-in the shell loads `GET /tenants/current` for the header's clinic name ([21](21-clinic-settings-and-tenants.md)).

### 3.2 Sign-out (AUTH-SESS-04)

"Sign Out" in the header clears the session, all loaded data (appointments, search rows, user data) and both
forms, sets status "Logged out successfully.", and navigates to `/`.

Opening any `/login` route while signed in signs the current user out first and clears the form.

### 3.3 Forced sign-out (AUTH-SESS-03)

When any request that carried a token gets 401, `api.ts` dispatches `hc:session-ended`. The auth context (only
the first time, via a ref) resets the session to guest, clears the login form and status, and navigates
**replace** to the role's login page with `state: {notice: "Your session has ended. Please sign in again."}`.
The app also clears loaded data on that event. Several simultaneous 401s cause one sign-out and one redirect.

### 3.4 Session lifetime

`ACCESS_TOKEN_MINUTES` (default 30). No refresh: the user signs in again after expiry. Reloading the page or
opening a new tab starts as a guest (token is memory-only).

## 4. API

### `POST /auth/login` (public)

Request `{"email": str, "password": str, "remember_me": bool = false}` (`remember_me` accepted and ignored).

Processing:
1. `email = email.strip().lower()`; `ip` = client address (F04 §5).
2. Check `login-email` and `login-ip` limits (429 if exhausted).
3. `cross_tenant.login_lookup(email)` → active, non-deleted account in any tenant.
4. If none or the password doesn't verify: record both limits; **401 "Authentication failed"**.
5. Clear the `login-email` counter; `set_db_tenant(account.tenant_id, account.id)`.
6. Issue the token (F03 §2); read `tenants.timezone`; for PATIENT load the non-deleted patient profile.

Response 200:
```json
{
  "access_token": "<jwt>",
  "refresh_token": "",
  "role": "PATIENT",
  "tenant_id": "<uuid>",
  "user_name": "Jane Doe",              // patients only, else null
  "insurance_provider": "Acme Health",  // patients only, else null
  "insurance_policy_id": "P-123",       // patients only, else null
  "clinic_timezone": "America/New_York" // valid IANA key (fallback to CLINIC_TIMEZONE)
}
```

Errors: 401 "Authentication failed" (unknown, wrong password, deactivated, deleted — identical); 429 rate limit;
422 generic validation message.

No audit entry is written for login.

## 5. Edge cases

- A self-registered doctor awaiting approval gets the generic 401 until an admin activates them ([05](05-doctor-self-registration.md)).
- A patient signing in on the Doctor page with valid credentials sees "Invalid credentials" and stays signed out.
- A user whose clinic zone is not a valid IANA name receives `CLINIC_TIMEZONE`.

## 6. Acceptance criteria

- **F02-AC-01** Given valid patient credentials on `/patients/login`, When submitted, Then the user lands on
  `/patients/appointments`, the header shows the clinic name and "Sign Out".
- **F02-AC-02** Given valid doctor credentials on `/patients/login`, When submitted, Then "Invalid credentials"
  is shown and no session exists.
- **F02-AC-03** Given a wrong password and an unknown email, When submitted to the API, Then both get the same
  401 body "Authentication failed".
- **F02-AC-04** Given "abc" as email, When the user submits, Then "Please enter a valid email address" appears
  and no request is sent; given a 7-character password, Then "Password must be at least 8 characters.".
- **F02-AC-05** Given a signed-in user whose account an admin deactivates, When they click anything that calls
  the API, Then they are on their login page with "Your session has ended. Please sign in again.".
- **F02-AC-06** Given 3 requests failing with 401 at once, Then exactly one navigation to the login page occurs.
- **F02-AC-07** Given a signed-in user, When they open `/doctors/login`, Then they are signed out and the form is
  empty.
- **F02-AC-08** Given `setup_required: true`, Then the Admin Login page shows the first-time setup link.
- **F02-AC-09** Given a reload while signed in, Then the app starts as a guest.

## 7. Reference implementation

`frontend/src/components/pages/LoginPage.tsx`, `contexts/AuthContext.tsx`, `api.ts` (`request`, `SESSION_ENDED_EVENT`),
`backend/app/api/routes/auth.py` (`login`), tests `LoginPage.test.tsx`, `AppHeader.test.tsx`,
`backend/tests/test_auth_login.py`.
