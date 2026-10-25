# F04 — Audit Trail, PHI Hygiene, Error Contract, Web Security and Rate Limits

## 1. Application audit trail (`SEC-AUD`)

`write_audit_log(db, *, tenant_id, table_name, record_id, action_type, old_data, new_data, performed_by)` adds
one `audit_logs` row to the **caller's transaction** (the caller commits). `write_access_log(db, identity,
table_name, record_id)` writes `action_type="READ"`, `new_data={"viewer_role": <role>}`.

- **SEC-AUD-01** Every create, update, delete, cancel, status change, reschedule, slot change, account change,
  profile change and password-reset request SHALL write an audit row in the same transaction as the change.
- **SEC-AUD-02** `old_data` / `new_data` hold only the changed fields. They SHALL NOT contain passwords, hashes or
  tokens (`{"password_reset": true}` is used instead).
- **SEC-AUD-03** Reads of clinical data by staff SHALL be recorded as `READ` access events (HIPAA-style
  accounting of disclosures). Patients reading their own records are not logged.
- **SEC-AUD-04** Audit rows are append-only and visible only to admins of the same tenant (`GET /audit-logs`).
- **SEC-AUD-05** The DB trigger `audit_trigger_function` (F02 §5.2) provides a second full-row trail.

### 1.1 Audit event catalog

| Feature | table_name | action | record | old → new |
|---------|-----------|--------|--------|-----------|
| Patient self-registration | users | INSERT | user | `{email, role}` |
| Doctor self-registration | users | INSERT | user | `{role:"DOCTOR", is_active:false, via:"self_registration"}` |
| First-admin bootstrap | users | INSERT | user | `{role:"ADMIN", via:"bootstrap"}` |
| Admin creates user | users | INSERT | user | `{email, role, created_by_admin:true}` (performed_by = the admin) |
| Forgot password (account exists) | users | UPDATE | user | `{password_reset_requested:true}` (performed_by = that user) |
| Reset via email link | users | UPDATE | user | `{password_reset:true, via:"email_link"}` |
| Admin reset password | users | UPDATE | user | `{password_reset:true}` |
| Admin change email | users | UPDATE | user | `{email:old}` → `{email:new}` |
| Deactivate / activate | users | UPDATE | user | `{is_active:!x}` → `{is_active:x}` |
| Soft delete | <profile table> and users | DELETE | profile, user | `{deleted_at:null}` → `{deleted_at, deleted_by}`; users `{is_active:true, deleted_at:null}` → `{is_active:false, deleted_at}` |
| Restore | users | UPDATE | user | `{deleted:true, is_active:false}` → `{deleted:false, is_active:true}` |
| Book | appointments | INSERT | appointment | `{doctor_id, patient_id, appointment_time}` |
| Confirm | appointments | UPDATE | appointment | `{status:"SCHEDULED"}` → `{status:"CONFIRMED"}` |
| Status change | appointments | UPDATE | appointment | `{status:old}` → `{status:new}` |
| Reschedule | appointments | UPDATE | appointment | `{appointment_time:old}` → `{appointment_time:new}` |
| Edit reason | appointments | UPDATE | appointment | `{notes:old}` → `{notes:new}` |
| Cancel | appointments | DELETE | appointment | `{status:old}` → `{status:"CANCELLED"}` |
| Slot add / block / unblock / delete | doctor_availability | INSERT / UPDATE / DELETE | slot | `{status:old}` → `{status, slot_time}` (DELETE: new = null) |
| Medical record created | medical_records | INSERT | record | `{appointment_id}` (no clinical text) |
| Prescription created | prescriptions | INSERT | prescription | `{medical_record_id}` |
| Document uploaded | patient_documents | INSERT | document | `{document_name, file_path}` or `{patient_id, document_name}` |
| Patient profile (PATCH or PUT) | patients | UPDATE | patient | changed fields only (nothing written when unchanged) |
| Doctor profile | doctors | UPDATE | doctor | changed fields of `full_name, phone, specialty, license_number` |
| Support profile | support_staff | UPDATE | staff | `{full_name, phone}` old → new |
| Clinic time zone changed | tenants | UPDATE | tenant | `{timezone:old}` → `{timezone:new, slots_moved:n}` |
| Doctor views patient history / search results / record | patients / medical_records | READ | patient / record | `{viewer_role}` |

## 2. Audit log query API

| | |
|-|-|
| **Endpoint** | `GET /audit-logs?table=&date_from=&date_to=` |
| **Roles** | A |
| **Filters** | `table` exact `table_name` (trimmed, optional); `date_from`, `date_to` ISO-8601 instants (inclusive, naive = UTC) |
| **Result** | Tenant's newest 200 rows, `performed_at DESC`: `[{action, timestamp (ISO), performed_by (uuid or ""), table, old ({} if null), new ({} if null)}]` |
| **Errors** | 403 non-admin; unparseable `date_from`/`date_to` → 422 "Invalid datetime format." |

There is no endpoint to modify or delete audit rows. There is no audit screen yet.

## 3. PHI and error hygiene (`SEC-PHI`)

- **SEC-PHI-01** Logs SHALL NOT contain names, emails, phone numbers, dates of birth, clinical text, tokens,
  passwords or request bodies. Log ids and exception types instead.
- **SEC-PHI-02 Validation errors** (`RequestValidationError`) → 422
  `{"detail": "Invalid request format. Please check your input and try again."}`. Never echo submitted values.
  Log only `loc: type` pairs.
- **SEC-PHI-03 Unhandled exceptions** → JSON 500
  `{"detail": "Something went wrong on the server. Please try again, or contact support if it keeps happening."}`.
  The catcher sits inside CORS so the browser can read it. Log the stack trace server-side only. No exception
  text, SQL or stack traces in responses.
- **SEC-PHI-04** Responses never include `password_hash` or credentials.
- **SEC-PHI-05** Frontend logs credentials, tokens or PHI to the console never; debug logs only in dev or with
  `VITE_ENABLE_DEBUG_LOGS=true`, paths without query strings, never response bodies.
- **SEC-PHI-06** Emails contain only what is needed (the reset link).
- **SEC-PHI-07** `create_async_engine(..., hide_parameters=True)`; email failures log only the exception type.
- **SEC-PHI-08** Local access logs drop query strings and client addresses (F01 §5.2).

### 3.1 Error response contract (`API-GEN`)

All errors are JSON `{"detail": "<human-readable message>"}`.

| Status | Meaning |
|--------|---------|
| 400 | Business-rule violation |
| 401 | Not authenticated, or session ended |
| 403 | Wrong role, or not the owner |
| 404 | Not found (including other tenants' records) |
| 409 | Conflict: duplicate email, slot taken, double booking, last admin |
| 413 / 415 | Upload too large / type not allowed |
| 422 | Invalid input |
| 429 | Rate limited (with `Retry-After`) |
| 500 | Unexpected error (generic message) |
| 503 | Dependency or migration not ready |

Successful creates return 201; other successes 200. Ids are UUID strings. Timestamps are ISO-8601 with offset.

### 3.2 Field validation catalog (`VAL`)

The same rule applies wherever the field appears. "UI" is the browser check, "API" the server check; both SHALL
enforce the rule. The server checks live in one module (`backend/app/api/validators.py`: `valid_email`,
`valid_phone`, `valid_gender`, `valid_birth_date`, `valid_doctor_birth_date`, `valid_full_name`, `optional_text`),
used by registration, admin user creation and the profile endpoints. Feature files repeat the rule next to each form.

| ID | Field | Rule | Message |
|----|-------|------|---------|
| VAL-01 | Full name | Required; UI 3–80 characters after trimming; API 3–255 | "Name must be at least 3 characters." |
| VAL-02 | Email | UI `^[^\s@]+@[^\s@]+\.[^\s@]+$`; admin email change `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`; stored lower-cased and trimmed | "Please provide a valid email address." (login, forgot password, admin email change: "Please enter a valid email address") |
| VAL-03 | Phone | `^\+?[0-9\-\s]{10,15}$` | "Phone should be 10-15 digits." |
| VAL-04 | New password | At least 8 characters (API max 255) | "Password must be at least 8 characters long" (the login page doesn't check the length; the server decides) |
| VAL-05 | Password / email confirmation | Equal to the first entry | "The two passwords do not match." / "The two new <field> entries do not match" |
| VAL-06 | Patient date of birth | Optional on self-registration and profile, required when an admin registers a patient; not in the future; not more than 120 years ago | "Date of birth cannot be in the future." / "Date of birth cannot be more than 120 years ago." (admin forms: "Date of birth is required." / "Please enter a valid date of birth.") |
| VAL-07 | Doctor date of birth | Required; at least 18 years old today | "Date of birth is required." / "Doctor must be at least 18 years old. Current age: N" |
| VAL-08 | Gender | One of `MALE`, `FEMALE`, `OTHER`, `PREFER_NOT_TO_SAY`; the API accepts any case (and spaces for underscores) and stores the enum value; optional except when an admin registers a patient | "Gender is required." |
| VAL-09 | Appointment reason | Required; at least 5 characters after trimming | "Please provide a reason of at least 5 characters." (patient screen, empty: "Please provide a reason for the appointment."; edit: "Reason must be at least 5 characters.") |
| VAL-10 | Diagnosis | Required; at least 3 characters | "Please fill in at least symptoms and diagnosis fields" |
| VAL-11 | Symptoms | Required; at least 5 characters | same as VAL-10 |
| VAL-12 | Search term | At least 2 characters after trimming, or exactly `*` ([15](../features/15-people-search.md)) | "Enter at least 2 characters of <what>, or * to list everyone." |
| VAL-13 | Slot / appointment time | ISO-8601 instant; naive = UTC | 422 "Invalid slot timestamp." / "Invalid datetime format." |
| VAL-14 | Optional text (address, insurance, specialty, license) | Trimmed; empty stored as NULL; max lengths per F02 | — |
| VAL-15 | Country | Chosen from the fixed country list, "United States" first and default (admin-created patients: "USA") | — |
| VAL-16 | Clinic time zone | Known IANA zone name | 422 "Unknown time zone. Pick one from the list (for example America/Chicago)." |

## 4. Web and transport security (`SEC-WEB`)

- **SEC-WEB-01 Headers on every response** (set with `setdefault`, so a route may override):
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`,
  `Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()`, `Cache-Control: no-store`,
  `Strict-Transport-Security: max-age=31536000; includeSubDomains`; plus `X-Request-ID` from the auth middleware.
- **SEC-WEB-02 CORS** only in the app: origins = `CORS_ORIGINS` split on commas and trimmed; credentials allowed;
  all methods and headers.
- **SEC-WEB-03** HTTPS everywhere (CloudFront viewer protocol "redirect-to-https"); DB and Lambda in private
  subnets.
- **SEC-WEB-04** External links use `target="_blank"` with `rel="noopener noreferrer"` (and
  `window.open(url, '_blank', 'noopener,noreferrer')`).
- **SEC-WEB-05** The SPA SHOULD ship a Content-Security-Policy restricting scripts to its own origin.

### 4.1 Middleware order (outermost → innermost)

1. CORS
2. Unhandled-error catcher (JSON 500 that passes back through CORS)
3. Security headers (outside auth, so 401s carry them)
4. Tenant/JWT context (F03 §3)
5. Audit context — stores `{tenant_id, performed_by, method, path, is_write}` on `request.state.audit_context`
6. Router → dependencies (`get_current_identity`, `require_roles`)

With Starlette `add_middleware`, the last added is outermost: add them in reverse.

## 5. Rate limiting of public endpoints (`AUTH-RATE`)

Sliding windows counted in PostgreSQL (table `rate_limit_events`, migration 009), so all Lambda instances share
the counts and the limits hold globally. Keys (lower-cased email or client address) are stored only as SHA-256
hashes. Each recorded event is committed immediately, so it counts even when the request then fails (a wrong
password's 401 rolls the request back). Rows older than the longest window (1 hour) are deleted as new events are
recorded. Until migration 009 is applied (or without a database, as in unit tests) the same limits are counted in
memory per process.

| Limit name | Max events | Window | Counts | Used by |
|------------|-----------:|--------|--------|---------|
| `login-email` | 10 | 15 min | failed logins per email | `POST /auth/login` |
| `login-ip` | 50 | 15 min | failed logins per client address | `POST /auth/login` |
| `reset-email` | 5 | 15 min | reset requests per email | `POST /auth/forgot-password` |
| `reset-ip` | 20 | 15 min | reset requests and reset submissions per address | forgot + reset |
| `register-ip` | 10 | 60 min | registrations per address | `POST /auth/register`, `/doctors/register`, `/admin/register` |

- Login **checks** both limits before verifying, **records** both only on failure, and **clears** the email's
  counter on success (a correct user is never throttled). Other endpoints check-then-record every request.
- Over the limit → 429 `{"detail": "Too many attempts. Please wait a few minutes and try again."}` with
  `Retry-After: <seconds until the oldest event leaves the window, +1>`.
- Client address = first `X-Forwarded-For` hop, else the socket peer, else "unknown".
- An AWS WAF rate-based rule on CloudFront MAY be added on top (per-IP flood protection before requests reach
  the app); it isn't needed for these limits.

## 6. Secrets and configuration (`SEC-SECRETS`)

- `DATABASE_URL`, `JWT_SECRET`, `SMTP_PASSWORD` come from environment variables / SAM `NoEcho` parameters, never
  committed files. `JWT_SECRET` ≥ 32 random bytes, different per environment.
- The repository is public: account ids, subnet and security-group ids, bucket names and endpoints live in a
  git-ignored `aws-config.local.json` with a committed `aws-config.example.json`.
- Documents bucket: block all public access, server-side encryption, reachable only by the Lambda role
  (`s3:PutObject`, `s3:GetObject` on `documents/*`). Download URLs expire after 1 hour.
- The app DB user holds DML privileges only.

## 7. Compliance posture

The controls support HIPAA-style safeguards (access control, audit, integrity, transmission security). A
production launch additionally needs a BAA with the cloud provider, encryption at rest for RDS and S3, backup and
retention policy, breach-notification procedure, workforce access reviews and periodic penetration tests.

## 8. Acceptance criteria

- **F04-AC-01** Given a body with an invalid email type, When posted, Then 422 with the generic message and the
  submitted value appears nowhere in the response or logs.
- **F04-AC-02** Given a route that raises, When called from an allowed origin, Then JSON 500 with the generic
  message and an `Access-Control-Allow-Origin` header.
- **F04-AC-03** Given any response (including 401 from the middleware), Then all §4 headers are present.
- **F04-AC-04** Given 10 failed logins for one email within 15 minutes, When the 11th is attempted (even with the
  right password), Then 429 with `Retry-After`; after a success the email's counter resets.
- **F04-AC-05** Given each event in §1.1, When it happens, Then exactly the documented audit row exists, with
  `performed_by` = the acting user, in the same transaction (rolled back together on failure).
- **F04-AC-06** Given audit rows of tenants A and B, When an admin of A calls `/audit-logs`, Then only A's rows
  (max 200, newest first).

## 9. Reference implementation

`backend/app/main.py` (handlers, middleware order), `middleware/security_headers_middleware.py`,
`middleware/audit_context_middleware.py`, `core/rate_limit.py`, `services/audit_service.py`,
`api/routes/audit_logs.py`.
