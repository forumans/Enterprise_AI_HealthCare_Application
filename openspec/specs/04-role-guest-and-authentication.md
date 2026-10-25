# 04 — Guest and Authentication

Covers everything a visitor can do before signing in, plus the sign-in, sign-out and session rules shared by
all roles.

## 1. Home page (`/`)

- **AUTH-HOME-01** Show the heading "Smart Healthcare Management Platform" and the lead text "Manage doctors,
  patients, appointments, prescriptions, and billing from a single unified platform."
- **AUTH-HOME-02** Show "Patient Login" (hidden when the signed-in user is a patient) and "Doctor Login"
  buttons that open the matching login pages.
- **AUTH-HOME-03** Show a "Latest Medical Breakthroughs" grid of 5 news cards (headline, source, summary,
  "Read more →" opening a web search for the headline and source in a new tab with `noopener,noreferrer`).
  Show 5 skeleton cards while loading. The news source is pluggable; the reference build uses static content.
- **AUTH-HOME-04** The home page is reachable by every role. No breadcrumb is shown on it.

## 2. Login (one page per role)

| Route | Role | Title | Subtitle | Link below the form |
|-------|------|-------|----------|---------------------|
| `/patients/login` | PATIENT | Patient Login | Access your medical records and appointments | "Don't have an account? Register" → `/patients/register` |
| `/doctors/login` | DOCTOR | Doctor Login | Manage your appointments and patient consultations | "New doctor? Register here" → `/doctors/register` |
| `/support/login` | SUPPORT_STAFF | Support Staff Login | Manage appointments and availability on behalf of patients and doctors | Text only: "Support staff accounts are created by an administrator" |
| `/admin/login` | ADMIN | Admin Login | System administration and management | "First time setup? Register admin" (see `AUTH-BOOT`) |

- **AUTH-LOGIN-01** Fields: Email (type email, autocomplete `email`) and Password (autocomplete
  `current-password`). Submit button label: "Login as Patient", "Login as Doctor", "Login as Admin" or
  "Login as Support Staff". Below: "Forgot password?" → `/forgot-password`.
- **AUTH-LOGIN-02** The submit button is disabled until both fields have a value and the email is valid.
  On submit: invalid email → "Please enter a valid email address" under the field; password shorter than 8
  characters → "Password must be at least 8 characters." (no request sent).
- **AUTH-LOGIN-03** The server looks the user up by lower-cased email among non-deleted, active accounts and
  verifies the password in constant time. Unknown email, wrong password, deactivated and deleted accounts all
  return the same 401 "Authentication failed".
- **AUTH-LOGIN-04** On success the server returns `access_token`, `role`, `tenant_id` and, for patients,
  `user_name`, `insurance_provider`, `insurance_policy_id`. `refresh_token` is an empty string.
- **AUTH-LOGIN-05 Role-page check.** If the returned role differs from the login page's role, the client
  SHALL discard the token and show "Invalid credentials" (generic, so the page does not reveal which role
  the email belongs to).
- **AUTH-LOGIN-06** On success the client stores the session in memory and navigates to the role's landing
  page (doc 01 §3).
- **AUTH-LOGIN-07** Opening any `/login` page while signed in SHALL sign the current user out first and clear
  the form.
- **AUTH-LOGIN-08** If the user arrived because their session ended, the login page shows an amber notice
  "Your session has ended. Please sign in again." until a new status message replaces it.
- **AUTH-LOGIN-09** Login errors stay on screen until the next attempt. Success messages clear after
  10 seconds.

## 3. Patient self-registration (`/patients/register`)

- **AUTH-REGP-01** Fields and rules:

| Field | Required | Rule / help text |
|-------|:-:|------------------|
| Full Name | yes | VAL-01, "Name must be 3-80 characters." |
| Email | yes | VAL-02, "Use a valid email format, e.g., name@example.com." |
| Phone | yes | VAL-03, "Use 10-15 digits. Country code allowed." |
| Password (show/hide toggle) | yes | VAL-04 |
| Date of Birth | no | VAL-06, "Format: MM/DD/YYYY (optional, max age 120 years)." |
| Gender | no | VAL-08; "Select Gender (Optional)", Male, Female, Other, Prefer not to say |
| Address Line 1, Address Line 2, City, State/Province, Postal Code | no | VAL-14 |
| Country | no | VAL-15, default "United States" |
| Insurance Provider, Policy Number | no | VAL-14 |

- **AUTH-REGP-02** Each field has an info icon whose tooltip shows the rule text.
- **AUTH-REGP-03** `POST /auth/register` creates the user (role `PATIENT`, active) and the patient profile in
  the default tenant (see `DATA-SEED-01`), enforces `BR-ACC-01`, writes an audit entry and returns 201
  "Registration successful".
- **AUTH-REGP-04** On success show "Registration successful! Please log in." and go to `/patients/login`.
  On failure show the server's message (for example the duplicate-email message), keeping the input.

## 4. Doctor self-registration (`/doctors/register`)

- **AUTH-REGD-01** Fields: Full Name (VAL-01), Email (VAL-02), Phone (VAL-03), Password (VAL-04), Specialty
  (optional, "Medical specialty (optional)."), License Number (optional), Date of Birth (required, VAL-07,
  "Doctor must be at least 18 years old").
- **AUTH-REGD-02** `POST /doctors/register` creates the user (role `DOCTOR`) and doctor profile in the default
  tenant, enforces `BR-ACC-01`, returns 201 "Doctor registration successful for <name>".
- **AUTH-REGD-03** On success show the server message and navigate to `/doctors/login` after 2 seconds.
  A "Back to login" style button also goes to `/doctors/login`.
- **AUTH-REGD-04** Self-registered doctors are immediately bookable once they have slots (no approval step).
  Production deployments SHOULD add an approval step or disable self-registration (doc 13).

## 5. First administrator bootstrap (`AUTH-BOOT`)

- **AUTH-BOOT-01** `POST /admin/register` (public) creates an `ADMIN` user in the default tenant. It exists so
  a new deployment can get its first administrator.
- **AUTH-BOOT-02** It SHALL create the `admins` profile row as well (`BR-ACC-02`).
- **AUTH-BOOT-03** It SHALL be refused once the tenant has any active admin (403), so it cannot be used to
  take over a running clinic. All further admins are created by an admin (doc 08).

## 6. Forgot and reset password

### 6.1 Forgot password (`/forgot-password`)
- **AUTH-FP-01** Heading "Forgot Password", text "Enter the email you sign in with and we'll send you a link
  to choose a new password." One field, Email (VAL-02: "Please enter a valid email address."). Button
  "Send Reset Link" ("Sending..." while in flight; disabled while empty). Submit calls
  `POST /auth/forgot-password`; on success the form is replaced by the server's reply. A "Back to Home" link
  is always shown.
- **AUTH-FP-02** The server SHALL always reply 200 "If an account exists for that email, a password reset link
  has been sent." — identical whether or not the account exists, is active, or the email could be sent — so the
  endpoint cannot be used to discover registered emails.
- **AUTH-FP-03** For an active, non-deleted account the server emails a link
  `<FRONTEND_URL>/reset-password?token=<token>` valid for `PASSWORD_RESET_MINUTES` (default 30), with the text:
  "We received a request to reset your password. Open this link within N minutes to choose a new password: …
  The link works once. If you didn't ask for this, you can ignore this email; your password stays the same."
  Subject: "Reset your password". It writes an audit entry `{"password_reset_requested": true}`.
- **AUTH-FP-04** If SMTP is not configured or sending fails, the server logs a warning without the recipient or
  body and still returns the same reply.

### 6.2 Reset password (`/reset-password?token=…`)
- **AUTH-RP-01** Heading "Choose a New Password". Without a token the page shows the error "This page needs the
  link from your password reset email." and a "Request a new reset link" link to `/forgot-password`. With a
  token: New Password and Confirm fields (VAL-04, VAL-05). After success the form is replaced by the server's
  reply and a "Go to sign in" link.
- **AUTH-RP-02** `POST /auth/reset-password` SHALL accept the token only if it is correctly signed, unexpired,
  has purpose `password_reset`, the account is still active and not deleted, and the account's password has
  not changed since the token was issued (single use; see `SEC-PWD-04`). Otherwise 400 "This password reset
  link is invalid or has expired. Please request a new one."
- **AUTH-RP-03** On success the password hash is replaced, an audit entry `{"password_reset": true,
  "via": "email_link"}` is written, and the reply is "Your password has been reset. You can now sign in with
  your new password."

## 7. Session behavior (all roles)

- **AUTH-SESS-01** The session (`accessToken`, `role`, `tenantId`, plus patient display fields) lives only in
  memory. Reloading the page or opening a new tab starts as a guest.
- **AUTH-SESS-02** Token lifetime is `ACCESS_TOKEN_MINUTES` (default 30). There is no refresh; the user signs
  in again after expiry.
- **AUTH-SESS-03 Forced sign-out.** When any request that carried a token gets 401, the client SHALL clear the
  session and any loaded data, and navigate (replace) to that role's login page with the session-ended notice.
  Several simultaneous 401s SHALL trigger only one sign-out and redirect.
- **AUTH-SESS-04 Sign out.** "Sign Out" in the header clears the session and loaded data, shows "Logged out
  successfully.", and navigates to `/`.
- **AUTH-SESS-05 Route guard.** Every role page is wrapped in a guard; a user whose role is not allowed (including
  guests) is redirected to `/`. The guard is a convenience only; the server enforces access (doc 09).
- **AUTH-SESS-06** Signed-in users see their tenant (clinic) name in the header, loaded from
  `GET /tenants/current`.
