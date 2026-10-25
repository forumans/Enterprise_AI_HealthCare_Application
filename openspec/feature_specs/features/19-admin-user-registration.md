# Feature 19 — Admin: Register Users (Doctor, Patient, Admin, Support Staff)

**Roles:** A · **Routes:** `/admin/register-doctor`, `/admin/register-patient`, `/admin/register-admin`,
`/admin/register-support-staff` · **API:** `POST /admin/users`; legacy `POST /patients`, `POST /doctors` ·
**Depends on:** 04 (email rule), F03, F04 · **Traces to:** `ADM-REG-*`

## 1. Purpose

Admins create accounts of every role in their own clinic. Admin-created accounts are active immediately.

## 2. UI (common)

- Each page redirects to `/admin/login` if the session isn't ADMIN; opening it clears the global status.
- Status `StatusMessage` above the form (success when the text contains success/registered/created/… words).
- Errors show under fields after a submit attempt; the form keeps input on failure.
- Buttons right-aligned: **"Cancel"** (outlined) → `/admin/system-dashboard`, and the submit button.
- Shared field rules: Full Name (help "Name must be 3-80 characters.", trimmed ≥ 3 → "Name must be at least 3
  characters."), Email (type email, placeholder "your.email@example.com", help "Use a valid email format, e.g.,
  name@example.com.", → "Please provide a valid email address."), Phone (help "Use 10-15 digits. Country code
  allowed.", → "Phone should be 10-15 digits."), Password (toggle, help "Minimum 8 characters.", → "Password must
  be at least 8 characters long.").

### 2.1 Register Doctor (`h2` "Register Doctor")
Fields: Full Name, Email, Phone, Password (placeholder "Enter your password"), Specialty ("Medical specialty
(optional)."), License Number ("Medical license number (optional)."), Date of Birth (date; help "Doctor must be at
least 18 years old"). DOB validated as the user types and on submit: required → "Date of birth is required."; future
→ "Date of birth cannot be in the future."; older than 120 years → "Please enter a valid date of birth."; age < 18 →
"Doctor must be at least 18 years old. Current age: N". Payload `role: "DOCTOR"`, `specialty`, `license_number`,
`date_of_birth`. Success "Doctor registration successful!"; the message clears after 10 s, the form clears after 3 s.
Errors also clear after 10 s.

### 2.2 Register Patient (`h2` "Register Patient")
Fields: Full Name, Email, Phone, Password (placeholder "Enter password"), Date of Birth \* (help "Select date from
calendar"; same DOB checks as 2.1 without the age rule), Gender \* (select "Select Gender", Male, Female, Other — values
SHALL be `MALE`, `FEMALE`, `OTHER` (GAP-07); missing → "Gender is required."), Address Line 1 ("Street address"),
City ("City name"), State ("State or province"), Postal Code ("ZIP or postal code"), Insurance Provider ("Insurance
company name (optional)"), Insurance Policy Number ("Policy number (optional)"). Country is not shown; the server
defaults it to "USA". Success "Patient registration successful!" with the same 10 s / 3 s timing.

### 2.3 Register Admin / Register Support Staff (one component, `role` prop)

| | Admin | Support staff |
|-|-------|---------------|
| `h2` | "Admin Registration" | "Support Staff Registration" |
| Subtitle | "Register a new administrator to manage the healthcare system" | "Register support staff who manage appointments and doctor availability on behalf of patients and doctors" |
| Submit | "Register Admin" | "Register Support Staff" |
| Success | "Admin registered successfully" | "Support staff registered successfully" |

Fields Full Name, Email, Phone, Password. On success the form clears immediately.

## 3. API — `POST /admin/users` (A)

The body is parsed manually: malformed JSON → **422 "Invalid JSON in request body"**; schema failure → 422 generic
message.

| Field | Rule (default) |
|-------|---------------|
| `role` | `^(PATIENT\|DOCTOR\|ADMIN\|SUPPORT_STAFF)$` |
| `full_name` | 3–255 |
| `email` | 5–255; SHALL match the email pattern; lower-cased and trimmed |
| `password` | 8–255 |
| `phone` | ≤ 50 (`""`) |
| `specialty` | ≤ 255 (`""`) |
| `license_number` | ≤ 100 (`""`) |
| `insurance_provider`, `insurance_policy_number` | ≤ 255 (`""`) |
| `date_of_birth` | `YYYY-MM-DD` or null |
| `gender` | null or one of the gender values |
| `address_line1`, `address_line2` | ≤ 255 (`""`) |
| `city`, `state` | ≤ 100 (`""`) |
| `postal_code` | ≤ 20 (`""`) |
| `country` | ≤ 100 (`"USA"`) |

Processing:
1. Email availability (`BR-ACC-01`) in the **admin's tenant** (body can't choose a tenant) → 409 "That email is
   already used by another account.".
2. Insert user (`is_active=true`); `IntegrityError` → 409 "Email already registered."; enum error while creating
   `SUPPORT_STAFF` → **503 "Support staff accounts aren't available yet: the database needs migration
   005_add_support_staff_role.sql."**.
3. Insert the role profile: PATIENT (all patient fields, empty → NULL, country default "USA"), DOCTOR
   (`specialty`, `license_number`, `phone` or NULL, `date_of_birth`), ADMIN (`full_name`, `phone`), SUPPORT_STAFF
   (`full_name`, `phone` or NULL).
4. Audit `users` INSERT `{email, role}` by the admin (GAP-04). Commit. **201** `{"id": "<user id>"}`.

### Legacy profile attachment (API only)
- `POST /patients` (A) `{user_id, full_name (3..255), phone?, insurance_provider?, insurance_policy_number?}` — user
  must be in the tenant and not deleted (404 "Target user not found."); duplicate → 409 "Patient profile already
  exists."; audit; 201 `{id}`.
- `POST /doctors` (A) `{user_id, full_name, specialty?, license_number?, phone?}` — same rules ("Doctor profile
  already exists."); 201 `{id}`.

## 4. Acceptance criteria

- **F19-AC-01** Given an email used by an active account in another clinic, Then 409.
- **F19-AC-02** Given a body naming another tenant, Then the user is still created in the admin's tenant.
- **F19-AC-03** Given role `SUPPORT_STAFF` before migration 005, Then 503 with the migration message.
- **F19-AC-04** Given an admin-created doctor, Then they can sign in immediately.
- **F19-AC-05** Given `{"role":"NURSE"}`, Then 422.
- **F19-AC-06** Given a patient registered without country, Then `patients.country = "USA"`.

## 5. Reference implementation

`frontend/src/components/pages/AdminRegisterDoctorPage.tsx`, `AdminRegisterPatientPage.tsx`,
`AdminRegistrationPage.tsx`, `backend/app/api/routes/admin.py` (`admin_create_user`), `patients.py`, `doctor.py`.
