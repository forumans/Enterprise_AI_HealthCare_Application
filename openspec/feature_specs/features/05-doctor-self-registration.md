# Feature 05 — Doctor Self-Registration and Admin Approval

**Roles:** guest (registers), admin (approves) · **Route:** `/doctors/register` · **API:** `POST /doctors/register`
· **Depends on:** 04 (tenant resolution, email rule), 20 (activation) · **Traces to:** `AUTH-REGD-*`

## 1. Purpose

A doctor can request an account themselves. The account starts **deactivated**, so nobody can pose as a clinic
doctor by registering; an admin activates it on Admin > Deactivate ([20](20-admin-account-management.md)).

## 2. UI (`/doctors/register`, in `AppLayout`)

- `h2` "Doctor Registration"; muted text "Register as a healthcare provider to manage appointments and
  consultations".
- Status area: `StatusMessage` (success or error type set by the outcome). Opening the page clears the status.
- Form (`form-stack`), errors shown only after a submit attempt:

| Label | id | Input | Help tooltip | Validation & message |
|-------|----|-------|--------------|----------------------|
| Full Name | `doctor-full-name` | text | "Name must be 3-80 characters." | trimmed ≥ 3 → "Name must be at least 3 characters." |
| Email | `doctor-email` | email, placeholder "your.email@example.com" | "Use a valid email format, e.g., name@example.com." | pattern → "Please provide a valid email address." |
| Phone | `doctor-phone` | text | "Use 10-15 digits. Country code allowed." | `^\+?[0-9\-\s]{10,15}$` → "Phone should be 10-15 digits." |
| Password | `doctor-password` | password + toggle, placeholder "Enter your password" | "Minimum 8 characters." | ≥ 8 → "Password must be at least 8 characters long." |
| Specialty | `doctor-specialty` | text | "Medical specialty (optional)." | — |
| License Number | `doctor-license-number` | text | "Medical license number (optional)." | — |
| Date of Birth | `doctor-date-of-birth` | date | "Doctor must be at least 18 years old" | required → "Date of birth is required."; age (full years today) ≥ 18 → "Doctor must be at least 18 years old. Current age: N" |

- Button "Register" (primary). Below: "Already have an account? " + link-style button "Sign In" → `/doctors/login`.
- Payload: `{full_name, email, password, phone, specialty?, license_number?, date_of_birth?}` (trimmed; empty
  optional values omitted).
- Success: show the server message (success style) and navigate to `/doctors/login` after **6 seconds** (long
  enough to read that an admin must activate the account). Failure: show the server message (error style).

## 3. Business rules

- **AUTH-REGD-01** Clinic resolution and email rule as [04](04-patient-self-registration.md) §3.
- **AUTH-REGD-02** Create `users(role=DOCTOR, is_active=false)` and a `doctors` profile (`full_name` trimmed;
  `specialty`, `license_number`, `phone` trimmed, empty → NULL; `date_of_birth`).
- **AUTH-REGD-03** Server validation SHALL mirror the UI: name 3–255, email 5–255 and pattern, password 8–255,
  phone pattern, DOB required and age ≥ 18 (current code checks only name, email length and password: GAP-06).
- **AUTH-REGD-04** A pending doctor cannot sign in (generic 401) and SHALL NOT appear in patient/support doctor
  lists or be bookable until activated: `GET /doctors` leaves them out, booking returns 409 "This doctor isn't
  accepting appointments.", and support doctor search shows them marked "(inactive)".
- **AUTH-REGD-05** Audit: `users` INSERT `{role: "DOCTOR", is_active: false, via: "self_registration"}`, performed
  by the new user.
- Admin-created doctors ([19](19-admin-user-registration.md)) are active immediately.

## 4. API — `POST /doctors/register` (public)

Request `{"full_name": str(3..255), "email": str(5..255), "password": str(8..255), "specialty": str?,
"license_number": str?, "phone": str?, "date_of_birth": "YYYY-MM-DD"?}`.
Steps: `rate_limit.hit("register-ip")` → hash → resolve tenant → email availability → insert user → flush →
insert doctor → flush → audit → commit.

Responses: **201** `{"message": "Registration received. An administrator must activate your account before you
can sign in."}` · 400 clinic not resolvable · 409 "That email is already used by another account." (race:
"Email already registered." / "Doctor profile already exists.") · 422 · 429.

## 5. Acceptance criteria

- **F05-AC-01** Given a successful self-registration, When the doctor tries to sign in, Then 401
  "Authentication failed".
- **F05-AC-02** Given an admin activates the account, When the doctor signs in, Then they land on
  `/doctors/appointments`.
- **F05-AC-03** Given a DOB 17 years ago, When submitted in the UI, Then "Doctor must be at least 18 years old.
  Current age: 17" and no request.
- **F05-AC-04** Given a pending doctor, When a patient opens the doctor dropdown, Then the pending doctor is not
  listed.
- **F05-AC-05** Given success, Then the page shows the server message and navigates to `/doctors/login` after 6 s.

## 6. Reference implementation

`frontend/src/components/pages/DoctorRegistrationPage.tsx`, `backend/app/api/routes/doctor.py`
(`register_doctor`).
