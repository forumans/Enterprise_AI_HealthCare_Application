# Feature 03 — Forgot Password and Reset Password (email link)

**Roles:** guest · **Routes:** `/forgot-password`, `/reset-password?token=…` ·
**API:** `POST /auth/forgot-password`, `POST /auth/reset-password` · **Depends on:** F03, F04 ·
**Traces to:** `AUTH-FP-*`, `AUTH-RP-*`, `SEC-PWD-03…05`

## 1. Purpose

Let any user set a new password through a single-use, time-limited link emailed to their login address, without
revealing which emails are registered.

## 2. UI

### 2.1 Forgot Password (`/forgot-password`, in `AppLayout`)

- `h2` "Forgot Password"; muted text "Enter the email you sign in with and we'll send you a link to choose a new
  password."
- Field: Email (id `forgot-email`, type email, autocomplete `email`, placeholder "your.email@example.com", help
  "The email address you use to sign in"). Editing clears the error.
- Button "Send Reset Link" ("Sending..." while in flight; disabled while sending or the field is empty).
- On submit: invalid email → field error "Please enter a valid email address." (no request). Otherwise
  `POST /auth/forgot-password {email: trimmed}`; on success **replace the form** with a success `StatusMessage`
  showing the server's message; on failure show the error under the field.
- Always: centered link "Back to Home" → `/`.

### 2.2 Choose a New Password (`/reset-password`, in `AppLayout`)

- `h2` "Choose a New Password".
- **No `token` query parameter:** error `StatusMessage` "This page needs the link from your password reset email."
  and link "Request a new reset link" → `/forgot-password`. No form.
- **With a token:** muted text "Type your new password in both boxes."; fields New Password (id
  `reset-new-password`, help "Minimum 8 characters", autocomplete `new-password`) and Confirm New Password
  (id `reset-confirm-password`, help "Re-enter the new password"); both with show/hide toggles. Button
  "Set New Password" ("Saving..."). Link "Link expired? Request a new one" → `/forgot-password`.
  - Validation: length < 8 → "Password must be at least 8 characters long."; mismatch →
    "The two passwords do not match." (shown as an error `StatusMessage` above the form; editing clears it).
  - Submit `POST /auth/reset-password {token, new_password}`; success **replaces the form** with the server's
    message (success style) and a link "Go to sign in" → `/`; failure shows the server message above the form.

## 3. Business rules

- **AUTH-FP-01** The forgot-password reply SHALL be identical — 200
  `{"message": "If an account exists for that email, a password reset link has been sent."}` — whether or not the
  account exists, is active, or the email could be sent.
- **AUTH-FP-02** Only an active, non-deleted account (any tenant, via `login_lookup`) gets an email.
- **AUTH-FP-03 Email.** Subject "Reset your password", plain text:
  ```
  We received a request to reset your password.

  Open this link within {minutes} minutes to choose a new password:
  {FRONTEND_URL}/reset-password?token={token}

  The link works once. If you didn't ask for this, you can ignore this email; your password stays the same.
  ```
  `{minutes}` = `PASSWORD_RESET_MINUTES` (default 30).
- **AUTH-FP-04** If SMTP isn't configured (`SMTP_HOST` or `SMTP_FROM` empty) log a warning
  "Email not sent: SMTP is not configured (set SMTP_HOST and SMTP_FROM/SMTP_USER)." and still reply the same. Send
  failures log only "Email sending failed (<ExceptionType>)." — never the recipient or body. Sending runs off the
  event loop (`asyncio.to_thread`), STARTTLS when `SMTP_TLS`, login when `SMTP_USER` is set, 15 s timeout.
- **AUTH-RP-01 Reset token** (`SEC-PWD`): JWT HS256 signed with `HMAC-SHA256(key=JWT_SECRET, msg="password-reset")`
  (hex digest) — distinct from the access-token key, so neither token type works as the other. Claims:
  `sub` = user id, `purpose` = `"password_reset"`, `pwh` = first 24 hex chars of `SHA-256(current password_hash)`,
  `iat`, `exp = iat + PASSWORD_RESET_MINUTES`.
- **AUTH-RP-02** A reset is accepted only if the token verifies and is unexpired, `purpose` is `password_reset`,
  `sub` and `pwh` are present, the account (via `reset_lookup`) is still active and not deleted, and
  `compare_digest(pwh, fingerprint(current hash))` — i.e. the password hasn't changed since issue. This makes the
  link single-use. Otherwise **400 "This password reset link is invalid or has expired. Please request a new one."**
- **AUTH-RP-03** New password 8–255 characters (Pydantic; shorter → 422 generic message).

## 4. API

### `POST /auth/forgot-password` (public)
Request `{"email": str}`. Steps: `email.strip().lower()`; `rate_limit.hit("reset-ip", ip)`;
`rate_limit.hit("reset-email", email)`; lookup; if found → `set_db_tenant`, create token, send email, audit
(`users`, UPDATE, `{password_reset_requested: true}`, performed_by = that user), commit. Response: the fixed
message (§3). Errors: 429 only.

### `POST /auth/reset-password` (public)
Request `{"token": str, "new_password": str (8..255)}`. Steps: `rate_limit.hit("reset-ip", ip)`; validate token
(§3); `set_db_tenant(account.tenant_id, account.id)`; set `password_hash = hash_password(new)`; audit
(`users`, UPDATE, `{password_reset: true, via: "email_link"}`); commit. Response 200
`{"message": "Your password has been reset. You can now sign in with your new password."}`. Errors: 400 invalid
link, 422 short password, 429.

## 5. Acceptance criteria

- **F03-AC-01** Given a registered and an unregistered email, When each requests a reset, Then both responses are
  identical and only the registered one receives an email.
- **F03-AC-02** Given a valid link, When the password is reset, Then the old password fails, the new one works,
  and using the same link again returns the 400 message.
- **F03-AC-03** Given a token older than 30 minutes, a token with another purpose, or an access token, When used,
  Then 400 with the invalid-link message.
- **F03-AC-04** Given a deactivated account, When it requests a reset, Then no email is sent and the reply is the
  same.
- **F03-AC-05** Given SMTP not configured, When a reset is requested, Then the reply is the same and a warning
  without the address is logged.
- **F03-AC-06** Given `/reset-password` without a token, Then the page shows "This page needs the link from your
  password reset email." and no form.
- **F03-AC-07** Given 6 requests for one email in 15 minutes, Then the 6th gets 429.

## 6. Reference implementation

`backend/app/api/routes/auth.py`, `core/security.py`, `services/email_service.py`,
`frontend/src/components/pages/ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`, `PasswordResetPages.test.tsx`.
