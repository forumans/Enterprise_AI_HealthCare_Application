# Feature 17 — Update Profile (Patient, Doctor, Support Staff)

**Roles:** P, D, S (own profile only) · **Routes:** `/patients/profile`, `/doctors/profile`, `/support/profile` ·
**API:** `GET/PUT /patient/patient/profile`, `PATCH /patient/profile`, `GET/PUT /doctor/profile`,
`GET/PUT /support/profile` · **Depends on:** F03, F04 · **Traces to:** `PAT-PROF-*`, `DOC-PROF-*`, `SUP-PROF-*`

## 1. Common rules

- The profile is always the caller's own (from the token). Nobody changes their **login email** here; email changes
  go through an admin ([20](20-admin-account-management.md)), which enforces uniqueness.
- Full name: 3–80 characters in the UI ("Name must be at least 3 characters."); server 3–255.
- Phone: `^\+?[0-9\-\s]{10,15}$` ("Phone should be 10-15 digits.").
- Empty full name or phone SHALL NOT overwrite stored values.
- Each successful update writes an audit row with old and new values of the changed fields only (nothing when
  unchanged).
- Errors are generic ("Your profile couldn't be loaded or saved. Please try again.", 500) — never exception text.

## 2. Patient profile (`/patients/profile`)

### UI
`h2` "Update Profile"; card (max 600 px). Success `StatusMessage` "Profile updated successfully!" at the top.

| Label | id | Input | Help | Validation |
|-------|----|-------|------|------------|
| Full Name | `profile-full-name` | text | "Name must be 3-80 characters." | trimmed ≥ 3 |
| Phone | `profile-phone` | text | "Use 10-15 digits. Country code allowed." | pattern |
| Date of Birth | `profile-date-of-birth` | date | "Format: MM/DD/YYYY (optional, max age 120 years)." | if given: not future ("Date of birth cannot be in the future."), ≤ 120 years ("Date of birth cannot be more than 120 years ago.") |
| Gender | select | "Select Gender (Optional)", Male, Female, Other, Prefer not to say (values `MALE` …) | | stored value normalized case-insensitively (`prefer not to say` → `PREFER_NOT_TO_SAY`) |
| Address Line 1 / Address Line 2 / City / State/Province / Postal Code | `profile-address-line1` … | text | as registration ([04](04-patient-self-registration.md)) | |
| Country | select | countries, "United States" first; default "United States" | | |
| Insurance Provider / Policy Number | `profile-insurance-provider` / `profile-insurance-policy` | text | "Insurance company name (optional)." / "Insurance policy number (optional)." | |

Errors show after a submit attempt. Buttons: **"Update Profile"** ("Updating...") and **"Cancel"** →
`/patients/appointments`. Load errors show the message. On success: show the message, refresh the patient
details used by [09](09-patient-schedule-appointments.md), and after 1.5 s navigate to `/patients/appointments`.
On failure: `alert("Failed to update profile. Please try again.")`.

### API
- `GET /patient/patient/profile` — P (other roles 403 "Only patients can access their profile"); 404 "Patient not
  found". `{id, full_name, email: "", phone, date_of_birth, gender, address_line1, address_line2, city, state,
  postal_code, country, insurance_provider, insurance_policy_number, deleted_at}`.
- `PUT /patient/patient/profile` — P; camelCase body, every key optional: `fullName`, `phone`, `dateOfBirth`
  (ISO date), `gender`, `addressLine1`, `addressLine2`, `city`, `state`, `postalCode`, `country`,
  `insuranceProvider`, `insurancePolicyNumber`. `fullName`/`phone`/`dateOfBirth` are applied only when non-empty;
  the other keys are applied when present (an explicit empty string clears the field — the UI SHALL send `""` for
  a cleared optional field, see GAP-15). Invalid date → 422 generic message. The server SHALL validate name length,
  phone pattern, DOB range and gender enum (GAP-15). → `{"message": "Profile updated successfully"}`.
- `PATCH /patient/profile` — P (API only): `{full_name (3..255), phone (pattern)}` → `{"message": "Profile updated"}`.

## 3. Doctor profile (`/doctors/profile`)

### UI
`h2` "Update Profile"; muted "Update your personal and professional information"; status `StatusMessage`
(success when it contains "success"). Fields: Full Name (`profile-full-name`), Phone (`profile-phone`), Specialty
(`profile-specialty`, "Medical specialty (optional)."), License Number (`profile-license-number`, "Medical license
number (optional)."). Buttons **"Update Profile"** ("Updating...") and **"Cancel"** → `/doctors/today-appointments`.
Success: "Profile updated successfully!" then after 1.5 s clear it and navigate to `/doctors/today-appointments`.
Failure: server message.

### API
- `GET /doctor/profile` — D (other roles 403 "Only doctors can access their profile"); 404 "Doctor not found".
  `{id, full_name, email: "", phone, specialty, license_number, date_of_birth: null, gender: null, address_*: null,
  city/state/postal_code/country: null, insurance_provider: null, insurance_policy_id: null, deleted_at}`.
  (Email is in `users`; the extra null fields keep the shape stable.)
- `PUT /doctor/profile` — D; body `{fullName?, phone?, specialty?, licenseNumber?}`; `fullName`/`phone` applied only
  when non-empty, `specialty`/`licenseNumber` when present. Server SHALL validate name length and phone pattern
  (GAP-16). → `{"message": "Profile updated successfully"}`. Audit on `doctors` with changed fields.

## 4. Support staff profile (`/support/profile`)

### UI
`h2` "Update Profile"; muted "Update your contact information". Fields Full Name (`support-profile-full-name`) and
Phone (`support-profile-phone`), then read-only **Email** with the note "Your login email. Ask an administrator to
change it." ("—" if empty). Buttons **"Update Profile"** ("Updating...") and **"Cancel"** →
`/support/patient-appointments`. Success "Profile updated successfully!" then after 1.5 s navigate to
`/support/patient-appointments`; failure shows the server message.

### API
- `GET /support/profile` — S → `{id, full_name, phone ("" if null), email}`; 404 "Support staff profile not found.".
- `PUT /support/profile` — S; `{full_name: str(3..255), phone: str matching ^\+?[0-9\-\s]{10,15}$}` (both
  required, trimmed) → `{"message": "Profile updated successfully", full_name, phone, email}`. Audit
  `support_staff` UPDATE `{full_name, phone}` old → new.

## 5. Acceptance criteria

- **F17-AC-01** Given a patient changing the city, When saved, Then the audit row's old/new contain only `city`.
- **F17-AC-02** Given a phone "12345", Then the UI shows "Phone should be 10-15 digits." and no request; sent
  directly to `PUT /support/profile`, Then 422.
- **F17-AC-03** Given an empty full name sent to `PUT /doctor/profile`, Then the stored name is unchanged.
- **F17-AC-04** Given a doctor token on `GET /patient/patient/profile`, Then 403.
- **F17-AC-05** Given the support profile page, Then the email is displayed and not editable.

## 6. Reference implementation

`frontend/src/components/pages/PatientProfilePage.tsx`, `DoctorProfilePage.tsx`, `SupportProfilePage.tsx`,
`backend/app/api/routes/patient.py`, `doctor.py`, `support.py`.
