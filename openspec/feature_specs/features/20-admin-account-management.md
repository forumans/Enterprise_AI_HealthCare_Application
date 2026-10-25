# Feature 20 — Admin: Account Management (Password, Email, Activation, Soft Delete, Restore)

**Roles:** A · **Routes:** `/admin/reset-password` ("Reset Password / Email"), `/admin/deactivate` ·
**API:** `GET /admin/roles`, `GET /admin/users/search`, `POST /admin/users/{id}/reset-password`,
`POST /admin/users/{id}/change-email`, `POST /admin/users/{id}/deactivate`, `POST /admin/users/{id}/activate`,
`PATCH /admin/users/{id}/soft-delete`, `PATCH /admin/users/{id}/restore`, legacy `POST /admin/reset-password`,
`POST /admin/change-email` · **Depends on:** 15, F03 (session re-check) · **Traces to:** `BR-ACC-*`, `ADM-ACCT-*`,
`ADM-DEACT-*`, `ADM-DEL-*`

## 1. Account rules (`BR-ACC`)

- **BR-ACC-01 Email uniqueness.** An email SHALL NOT be given to a new or existing account if it belongs to any
  active (non-deleted) account in any tenant, or to any account (even deleted) in the same tenant. →
  **409 "That email is already used by another account."**
- **BR-ACC-03 Deactivate** sets `users.is_active = false`. The person can't sign in and any session they have ends
  at their next request (F03 §4). Records stay visible to staff.
- **BR-ACC-04 Self and last-admin protection.** An admin can't deactivate their own account
  (**400 "You can't deactivate your own account."**). At least one admin per tenant stays active
  (**409 "At least one admin must stay active."**). The tenant's active-admin rows are locked
  (`SELECT … FOR UPDATE ORDER BY id`) **before** reading the target, so two admins deactivating each other at once
  can't leave none. An admin acting while already deactivated (token still valid) gets
  **403 "Your admin account is deactivated."**.
- **BR-ACC-05** (De)activating an account already in that state → **400 "This account is already active."** /
  **"This account is already deactivated."**.
- **BR-ACC-06 Soft delete** sets `deleted_at`/`deleted_by` on the profile, and `is_active=false`, `deleted_at`
  (and `deleted_by` — GAP-05) on the user. The person disappears from lists, searches and booking; their
  appointments and records stay. Same self / last-admin protection (**400 "You can't delete your own account."**,
  409 last admin).
- **BR-ACC-07 Restore** clears `deleted_at`/`deleted_by` on user and profile and sets `is_active=true`. Refused if not
  deleted (**400 "This account is not deleted."**) or another active account now uses the email
  (**409 "Another active account uses this email. Change one of the emails before restoring."**).
- **BR-ACC-08 Change login email.** New email matches `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$` (else 422
  generic message), is lower-cased, differs from the current one (**400 "The new email (<new>) is the same as the
  current one."**) and satisfies BR-ACC-01. The password is kept. A race on the unique constraint → 409 (email
  taken message).
- **BR-ACC-09 Reset password.** At least 8 characters (**400 "Password must be at least 8 characters long"**). The
  email is kept.
- **BR-ACC-10** Every change writes an audit row naming the admin (F04 §1.1). Passwords are never logged, returned
  or audited.
- All actions target users of the admin's own tenant; anything else → **404 "User not found."**.

## 2. UI — Reset Password / Change Email (`/admin/reset-password`)

- `h2` "Reset Password / Change Email"; muted "Select a role and search by name, email or phone number. Click a name
  to change that person's login email or reset their password." (max width 1100 px, centered).
- `AdminUserSearch` (F06 §6.3) with clickable names and hint "Click a name to manage that account.". A new search
  clears the selection.
- After clicking a name:
  - **Selected Account** card: "Name:", "Role:" (Patient / Doctor / Support Staff / Admin), "Email:", "Phone:" ("—").
  - Two side-by-side forms (remounted per selected user), each with its own error/success box:

| | Change Email | Reset Password |
|-|--------------|----------------|
| Description | "Type the new email in both boxes. The user signs in with it from now on; their password stays the same." | "Type the new password in both boxes. The user signs in with it from their next login." |
| Highlight | amber box "CURRENT (OLD) EMAIL" + current email | — |
| Fields | "New Email" (help "Must not be used by any other account"), "Confirm New Email" (help "Re-enter the new email to confirm"); placeholder "new.email@example.com"; **plain text inputs** with `inputMode="email"`, `autoComplete="off"`, `autoCapitalize="none"`, `spellCheck=false`, password-manager opt-outs (`data-lpignore`, `data-1p-ignore`, `data-form-type="other"`), so the browser never pre-fills a saved login | "New Password", "Confirm New Password" (password inputs with toggles, `new-password`, placeholder "Enter new password", help "Minimum 8 characters") |
| Validation | `^[^\s@]+@[^\s@]+\.[^\s@]+$` → "Please enter a valid email address"; same as current (case-insensitive) → "The new email (<v>) is the same as the current one (<current>)"; mismatch → "The two new email entries do not match" | < 8 → "Password must be at least 8 characters long"; mismatch → "The two new password entries do not match" |
| Confirmation | `confirm("Change <name>'s login email from <old> to <new>? They must sign in with the new email from now on.")` (cancel = nothing) | none |
| Submit / busy | "Change Email" / "Changing Email..." | "Reset Password" / "Resetting Password..." |
| Success | "Email changed from <old> to <new>"; the selected account and its search row show the new email; inputs cleared | "Password reset for <name> (<email>)"; inputs cleared |

- "Important Notes:" box: "Changes apply to the account you clicked, identified by its unique id" · "Passwords must
  be at least 8 characters long" · "An email already used by another account can't be assigned" · "Changing the
  email keeps the password, and resetting the password keeps the email".

## 3. UI — Deactivate / Activate (`/admin/deactivate`)

- `h2` "Deactivate / Activate Accounts"; muted "Select a role and search by name, email or phone number. Deactivated
  accounts can't log in until they are activated again."
- `AdminUserSearch` with role order Support Staff, Doctors, Patients, Admin, and two extra columns:
  - **Status**: pill "Active" or "Deactivated";
  - **Action**: for the admin's own row the muted text "Your account"; otherwise "Deactivate" (red) or "Activate"
    (green), "Saving..." while busy.
- Confirmation: "Deactivate <name> (<email>)? They will no longer be able to log in." / "Activate <name> (<email>)?
  They will be able to log in again." → API → update the row in place → success "<name> has been
  deactivated." / "<name> has been activated."; errors show the server message. A new search clears the message.
- "Important Notes:" — "Deactivated users can't log in; their records and appointments are kept" · "You can't
  deactivate your own account" · "At least one admin account must always stay active" · "Someone already signed in is
  signed out on their next action".
- Self-registered doctors awaiting approval ([05](05-doctor-self-registration.md)) are activated here.

## 4. API (all A)

| Endpoint | Body | Success 200 | Errors |
|----------|------|-------------|--------|
| `POST /admin/users/{user_id}/reset-password` | `{new_password}` | `{message: "Password reset successfully", user_id, user_email, user_role}` | 400 short; 404 |
| `POST /admin/users/{user_id}/change-email` | `{new_email}` | `{message: "Email changed successfully", user_id, old_email, new_email, user_role}` | 400 same; 404; 409; 422 format |
| `POST /admin/users/{user_id}/deactivate` | — | `{message: "Account deactivated successfully", user_id, user_email, user_role, is_active: false}` | 400 self / already; 403 caller deactivated; 404; 409 last admin |
| `POST /admin/users/{user_id}/activate` | — | same with "Account activated successfully", `is_active: true` | 400 already; 403; 404 |
| `PATCH /admin/users/{user_id}/soft-delete` | — | `{message: "<ROLE> soft deleted successfully."}` | 400 self; 404 (missing or already deleted); 409 last admin |
| `PATCH /admin/users/{user_id}/restore` | — | `{message: "User restored."}` | 400 not deleted; 404; 409 email reused |
| `POST /admin/reset-password` (legacy) | `{email, role, new_password}` | `{message, user_email, user_role, reset_by}` | 400 invalid role ("Invalid role. Must be one of: …"); 404 "User not found with the provided email and role combination"; 422 email format |
| `POST /admin/change-email` (legacy) | `{email, role, new_email}` | `{message, old_email, new_email, user_role}` | 400 "The new email is the same as the current one."; plus the above |

User lookups by id: `users.id = :id AND tenant_id = admin's tenant AND deleted_at IS NULL` (restore looks up
deleted users too). Soft delete of an ADMIN or SUPPORT_STAFF also soft-deletes the `admins`/`support_staff` row;
of a PATIENT/DOCTOR the `patients`/`doctors` row. There is no soft-delete/restore screen yet.

## 5. Acceptance criteria

- **F20-AC-01** Given an admin, When deactivating themselves via the API, Then 400; the UI shows "Your account"
  instead of a button.
- **F20-AC-02** Given two active admins deactivating each other concurrently, Then exactly one succeeds and the
  other gets 409 or 403; at least one admin stays active.
- **F20-AC-03** Given a deactivated user with a valid token, When they call any endpoint, Then 401 and the UI shows
  the session-ended notice.
- **F20-AC-04** Given a 7-character new password, Then 400; with 8, Then the old password fails and the new works.
- **F20-AC-05** Given an email change to the current email, Then 400; after a change the user signs in with the new
  email and the unchanged password.
- **F20-AC-06** Given a deleted user whose email was reused by an active account, When restored, Then 409.
- **F20-AC-07** Given a user of tenant B, When an admin of A acts on their id, Then 404.
- **F20-AC-08** Given the change-email form, Then the browser does not pre-fill the inputs with a saved login.

## 6. Reference implementation

`frontend/src/components/pages/AdminResetPasswordPage.tsx`, `AdminDeactivatePage.tsx` (+ tests),
`backend/app/api/routes/admin_password_reset.py`, `admin.py` (`soft_delete_user`, `restore_user`),
`services/account_service.py`.
