# Feature 06 — First Administrator Setup (Bootstrap)

**Roles:** guest · **Route:** `/admin/setup` · **API:** `GET /admin/setup-status`, `POST /admin/register` ·
**Depends on:** 04 (tenant resolution), F05 (zones) · **Traces to:** `AUTH-BOOT-*`

## 1. Purpose

A brand-new deployment has no administrator. This public page creates the very first one and sets the clinic's
time zone. It stops working the moment any active admin exists anywhere, so it can't be used to take over a
running clinic or to claim a clinic the operator just created.

## 2. UI (`/admin/setup`, in `AppLayout`)

`h2` "First-Time Setup". On load call `GET /admin/setup-status` (error → treat as not required).

| State | Content |
|-------|---------|
| Checking | muted "Checking setup status..." |
| Not required | error `StatusMessage` "This system is already set up. Administrator accounts are created by an existing administrator." and link "Go to Admin Login" → `/admin/login`. No form. |
| Required | muted "Create the first administrator account. This page works only until an administrator exists." then the form |
| Done | success `StatusMessage` with the server message and link "Go to Admin Login" |

Form fields (all required, asterisk shown):

| Label | id | Input | Help tooltip |
|-------|----|-------|--------------|
| Full Name | `setup-name` | text | "Name must be 3-80 characters." |
| Email | `setup-email` | email, autocomplete `email` | "Use a valid email format, e.g., name@example.com." |
| Password | `setup-password` | password + toggle, autocomplete `new-password` | "Minimum 8 characters" |
| Confirm Password | `setup-confirm` | password + toggle | "Re-enter the password" |
| Clinic Time Zone | `setup-timezone` | select of `supportedTimeZones(browser zone)`, labels with `_` → space, preset to the browser's zone | note: "Office hours and every time in the app use this zone. Admins can change it later under Clinic Settings." |

Validation on submit, first failure shown as one error `StatusMessage` above the form (editing clears it):
name trimmed < 3 → "Name must be at least 3 characters."; invalid email → "Please provide a valid email address.";
password < 8 → "Password must be at least 8 characters long."; mismatch → "The two passwords do not match.".

Button "Create Administrator" ("Creating..."). Sends `{full_name: trimmed, email: trimmed, password, timezone}`.

## 3. Business rules

- **AUTH-BOOT-01** `GET /admin/setup-status` (public) → `{"setup_required": not app_any_active_admin()}` — true
  while no active, non-deleted admin exists in any tenant.
- **AUTH-BOOT-02** `POST /admin/register` SHALL be refused with **403 "An administrator already exists. Ask an
  administrator to create your account."** as soon as any active admin exists anywhere.
- **AUTH-BOOT-03** `timezone` optional; if given (trimmed) it must be a known IANA zone, else **422 "Unknown time
  zone."**; it is applied to the resolved clinic with the same slot-moving logic as Clinic Settings
  ([21](21-clinic-settings-and-tenants.md)).
- **AUTH-BOOT-04** Clinic resolved as in [04](04-patient-self-registration.md) §3.1 (creates the default tenant
  on an empty deployment). Email rule `BR-ACC-01`.
- **AUTH-BOOT-05** Creates `users(role=ADMIN, is_active=true)` and `admins(full_name trimmed)` in one transaction;
  audit `users` INSERT `{role: "ADMIN", via: "bootstrap"}` performed by the new user.

## 4. API

### `GET /admin/setup-status` (public)
200 `{"setup_required": true|false}`.

### `POST /admin/register` (public, bootstrap only)
Request `{"full_name": str(3..255), "email": str(5..255), "password": str(8..255), "timezone": str(≤64)?}`.
Steps: `rate_limit.hit("register-ip")` → any active admin? 403 → validate zone → hash → resolve tenant → email
availability → set zone → insert user → flush → insert admin → audit → commit.

Responses: **201** `{"message": "Admin registration successful for <full_name>"}` · 400 clinic not resolvable ·
403 already set up · 409 email taken ("Email already registered." on race) · 422 · 429.

## 5. Acceptance criteria

- **F06-AC-01** Given an empty deployment, When the setup form is submitted with zone `America/Chicago`, Then an
  active admin exists, the Default Tenant's zone is `America/Chicago`, and `setup-status` returns false.
- **F06-AC-02** Given any active admin in any clinic, When `POST /admin/register` is called, Then 403 and nothing
  is created.
- **F06-AC-03** Given zone `Mars/Olympus_Mons`, Then 422 "Unknown time zone.".
- **F06-AC-04** Given setup already done, When `/admin/setup` opens, Then the "already set up" message and no form.

## 6. Reference implementation

`frontend/src/components/pages/AdminSetupPage.tsx` (+ test), `backend/app/api/routes/doctor.py`
(`admin_setup_status`, `register_admin`), `core/cross_tenant.py` (`any_active_admin`).
