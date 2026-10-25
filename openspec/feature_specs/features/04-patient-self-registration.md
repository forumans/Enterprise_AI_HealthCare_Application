# Feature 04 — Patient Self-Registration and Clinic (Tenant) Resolution

**Roles:** guest · **Route:** `/patients/register` · **API:** `POST /auth/register` ·
**Depends on:** F02 (tables), F03, F04 (rate limit, audit), F06 · **Traces to:** `AUTH-REGP-*`, `AUTH-TENANT-*`,
`BR-ACC-01/02`, `VAL-01…15` (catalog: [F04 §3.2](../foundation/F04-audit-privacy-errors-security.md))

## 1. Purpose

A person creates their own patient account in the clinic whose website they are on, then signs in.

## 2. UI (`/patients/register`, in `AppLayout`)

`h2` "Patient Registration"; a card (max width 600 px, centered, padding 24 px) holding the form. Fields in order:

| Label | id | Input | Required | Help tooltip | Client validation & message |
|-------|----|-------|:-:|--------------|------------------------------|
| Full Name | `register-name` | text | yes | "Name must be 3-80 characters." | trimmed length ≥ 3 → "Name must be at least 3 characters." |
| Email | `register-email` | text | yes | "Use a valid email format, e.g., name@example.com." | `^[^\s@]+@[^\s@]+\.[^\s@]+$` → "Please provide a valid email address." |
| Phone | `register-phone` | text | yes | "Use 10-15 digits. Country code allowed." | `^\+?[0-9\-\s]{10,15}$` → "Phone should be 10-15 digits." |
| Password | `register-password` | password + show/hide | yes | "Minimum 8 characters." | length ≥ 8 → "Password must be at least 8 characters long." |
| Date of Birth | `register-date-of-birth` | date | no | "Format: MM/DD/YYYY (optional, max age 120 years)." | if given: not after today → "Date of birth cannot be in the future."; not before today − 120 years → "Date of birth cannot be more than 120 years ago." |
| Gender | (select) | select | no | — | options: "Select Gender (Optional)" (""), "Male" (`MALE`), "Female" (`FEMALE`), "Other" (`OTHER`), "Prefer not to say" (`PREFER_NOT_TO_SAY`) |
| Address Line 1 | `register-address-line1` | text | no | "Street address (optional)." | |
| Address Line 2 | `register-address-line2` | text | no | "Apartment, suite, unit, building, floor, etc. (optional)." | |
| City | `register-city` | text | no | "City name (optional)." | |
| State/Province | `register-state` | text | no | "State or province (optional)." | |
| Postal Code | `register-postal-code` | text | no | "ZIP or postal code (optional)." | |
| Country | (select) | select of all countries, "United States" first | no (default "United States") | — | |
| Insurance Provider | `register-insurance` | text | no | "Insurance company name (optional)." | |
| Policy Number | `register-policy` | text | no | "Insurance policy number (optional)." | |

Buttons (side by side, equal width): **"Create Account"** (primary `#42b5f5`; "Creating Account..." and grey while
in flight) and **"Cancel"** (grey `#6c757d`) → `/patients/login`. Both disabled while in flight.

Errors appear above each field; all errors are computed together on submit; input is kept.

On success: `alert("Registration successful! Please log in.")`, then navigate to `/patients/login`.
On failure: show the server's `detail` (e.g. "That email is already used by another account.") — `alert` or an
inline error `StatusMessage` — and keep the form.

Request body sent: `full_name` (trimmed), `email` (trimmed), `phone` (trimmed), `password`, and, only when
non-empty, `date_of_birth` (`YYYY-MM-DD`), `gender`, `address_line1`, `address_line2`, `city`, `state`,
`postal_code`, `country`, `insurance_provider`, `insurance_policy_number` (trimmed).

## 3. Business rules

### 3.1 Which clinic the registration joins (`AUTH-TENANT`)

- **AUTH-TENANT-01** Host = hostname of the `Origin` header (browsers send it on POST); else the first entry of
  `X-Forwarded-Host`; else `Host` — with any `:port` removed (IPv6 bracket hosts kept as is), trimmed,
  lower-cased, trailing dot removed.
- **AUTH-TENANT-02** Clinic = tenant whose `lower(domain)` equals the host.
- **AUTH-TENANT-03** No match: if no tenant exists, create `Tenant(name="Default Tenant", domain="default.local",
  timezone=CLINIC_TIMEZONE)`; if exactly one tenant exists, use it; if several exist, refuse with
  **400 "Registration isn't available at this address. Please use your clinic's website or contact the clinic."**
- **AUTH-TENANT-04** Once resolved, the request's DB work is scoped to that tenant (`set_db_tenant`, F03 §8).
- **AUTH-TENANT-05** The same resolution is used by doctor self-registration and the first-admin bootstrap.

### 3.2 Account creation

- **BR-ACC-01 Email uniqueness.** Lower-cased/trimmed email SHALL NOT belong to any **active (non-deleted)**
  account in **any** tenant, nor to **any** account (even deleted) in the **same** tenant
  (`app_email_in_use`). → **409 "That email is already used by another account."** A race caught by the
  `(tenant_id, email)` unique constraint → 409 "User already exists in tenant.".
- **BR-ACC-02** User (`role=PATIENT`, `is_active=true`, PBKDF2 hash) and patient profile are created in one
  transaction.
- **AUTH-REGP-SRV** The server SHALL enforce the same field rules as the UI: `full_name` 3–255 after trim;
  password 8–255; email pattern; phone pattern when given (the UI requires it); DOB not in the future and ≤ 120
  years; gender ∈ `MALE|FEMALE|OTHER|PREFER_NOT_TO_SAY`, any case accepted and stored upper-case; length limits
  from F02. Optional text fields are trimmed and empty → NULL. Violations → 422 generic message (F04 §3.2).
- Audit: `users` INSERT `{email, role}` performed by the new user.

## 4. API — `POST /auth/register` (public)

Request:
```json
{
  "full_name": "Jane Doe",           // 3..255
  "email": "jane@example.com",
  "phone": "555-123-4567",
  "password": "********",            // 8..255
  "insurance_provider": "Acme", "insurance_policy_number": "P-1",
  "date_of_birth": "1985-03-07",     // YYYY-MM-DD, optional
  "gender": "FEMALE",
  "address_line1": "1 Main St", "address_line2": null, "city": "Austin", "state": "TX",
  "postal_code": "73301", "country": "United States"
}
```
Steps: `rate_limit.hit("register-ip", ip)` → resolve tenant → email availability → insert user → flush → insert
patient → audit → commit.

Responses: **201** `{"message": "Registration successful"}` · 400 clinic not resolvable · 409 email taken ·
422 generic validation · 429 rate limit.

## 5. Acceptance criteria

- **F04-AC-01** Given a single-clinic deployment, When a patient registers from any host, Then the account
  belongs to that clinic and can sign in at once.
- **F04-AC-02** Given clinics A (`a.example.com`) and B, When a browser on `https://a.example.com` registers,
  Then the patient belongs to A.
- **F04-AC-03** Given several clinics and an unknown host, Then 400 with the "isn't available at this address"
  message and nothing is created.
- **F04-AC-04** Given an email used by an active account in another clinic, Then 409 "That email is already used
  by another account."; given an email of a deleted account in another clinic, Then registration succeeds.
- **F04-AC-05** Given a 2-character name or a 7-character password sent directly to the API, Then 422.
- **F04-AC-06** Given an empty database, When the first registration arrives, Then a "Default Tenant" with domain
  `default.local` and zone `CLINIC_TIMEZONE` is created.
- **F04-AC-07** Given the UI with phone "12345", When submitted, Then "Phone should be 10-15 digits." and no
  request.
- **F04-AC-08** Given 11 registrations from one address within an hour, Then the 11th gets 429.

## 6. Reference implementation

`frontend/src/components/pages/PatientRegistrationPage.tsx`, `backend/app/api/routes/auth.py` (`register`),
`services/tenant_service.py` (`request_host`, `resolve_registration_tenant`), `services/account_service.py`
(`ensure_email_available`).
