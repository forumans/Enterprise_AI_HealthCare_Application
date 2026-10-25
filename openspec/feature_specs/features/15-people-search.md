# Feature 15 — People Search (shared rules)

**Roles:** S (patients, doctors), A (users of a role), D (patients by name — [14](14-doctor-search-patients.md)) ·
**API:** `GET /support/patients?q=`, `GET /support/doctors?q=`, `GET /admin/users/search?role=&q=`,
`GET /admin/roles` · **UI components:** `SupportSearchPanel`, `AdminUserSearch` (F06 §6.2–6.3) ·
**Traces to:** `BR-SRCH-01…04`, `SUP-SRCH-*`, `ADM-SRCH-*`

## 1. Rules

- **BR-SRCH-01 Minimum term.** After trimming, the term SHALL be at least 2 characters or exactly `*`.
  UI message: "Enter at least 2 characters of <what>, or * to list everyone." where `<what>` is "a name, email or
  phone number" (support and admin) or "a patient name" (doctor). API (support, admin): **422 "Enter at least 2
  characters to search, or * for everyone."**. Doctor patient search returns `[]` instead.
- **BR-SRCH-02 Matching** (`name_phone_or_email_matches`): `*` matches everyone; otherwise a row matches when the
  term is a case-insensitive substring (`ILIKE %term%`) of the full name, **or** of the login email (where
  supported), **or** — when the term contains at least 3 digits — the term's digits appear in the phone's digits
  with all non-digits removed (`regexp_replace(coalesce(phone,''), '\D', '', 'g') LIKE %digits%`), so "555-123"
  finds "(555) 123-4567".
- **BR-SRCH-03 Limits and order.** `*` returns every match with no cap; any other term returns at most 50.
  Results are sorted by full name ascending.
- **BR-SRCH-04 Scope.** Only non-deleted people (profile and, where joined, user) of the caller's tenant.

| Search | Who | Fields matched | Returns |
|--------|-----|----------------|---------|
| Support patient search | S | name, email, phone | contact details only — never clinical data |
| Support doctor search | S | name, email, phone | contact, specialty, license |
| Admin user search | A | name, email, phone within one chosen role | account details, active flag, "is self" |
| Doctor patient search | D, A | name only | demographics + clinical history rows ([14](14-doctor-search-patients.md)) |

## 2. API

### `GET /support/patients?q=` — S
Join `patients` ↔ `users` (for email); tenant; `patients.deleted_at IS NULL`; BR-SRCH-02 with email.
Item `{id (patient id), name, phone ("" if null), email, date_of_birth ("YYYY-MM-DD" or ""), gender (""),
insurance_provider (""), city (""), state ("")}`.

### `GET /support/doctors?q=` — S
Join `doctors` ↔ `users`; tenant; `doctors.deleted_at IS NULL`; BR-SRCH-02 with email.
Item `{id (doctor id), name, phone, email, specialty (""), license_number (""), is_active}` (`is_active` =
the doctor's login). Deactivated doctors (e.g. awaiting approval) are still listed, so staff can manage their
existing appointments and slots; `SupportSearchPanel` shows a muted "(inactive)" after their name, and booking them
is refused by the server ([07](07-appointment-lifecycle.md) BOOK-06).

### `GET /admin/roles` — A
`[{"value":"PATIENT","label":"Patients"}, {"value":"DOCTOR","label":"Doctors"},
{"value":"SUPPORT_STAFF","label":"Support Staff"}, {"value":"ADMIN","label":"Admin"}]`.

### `GET /admin/users/search?role=&q=` — A
- `role` required and one of the four values, else **400 "Invalid role. Must be one of: PATIENT, DOCTOR,
  SUPPORT_STAFF, ADMIN"**.
- Join `users` ↔ the role's profile table; tenant; role; `users.deleted_at IS NULL` and profile not deleted;
  BR-SRCH-02 with email; order by profile name; cap 50 unless `*`. Deactivated users ARE included (so they can be
  re-activated).
- Item `{user_id, role, name (profile name or email), email, phone (""), address (patients: ", "-joined line1,
  line2, city, state, postal, country; others ""), date_of_birth ("YYYY-MM-DD" or ""), specialty (doctors, else ""),
  is_active, is_self (user_id == caller)}`.

## 3. Acceptance criteria

- **F15-AC-01** Given "a", Then 422 with the message (support/admin) and no query runs.
- **F15-AC-02** Given a patient phone "(555) 123-4567", When searching "555-123", Then the patient is found; "55"
  does not match by phone (fewer than 3 digits).
- **F15-AC-03** Given "JANE@EXAMPLE", Then the patient with email jane@example.com is found.
- **F15-AC-04** Given 60 matches, Then 50 are returned; with `*`, Then all 60.
- **F15-AC-05** Given a soft-deleted patient, Then they are never returned; a deactivated admin IS returned by
  admin search with `is_active: false`.
- **F15-AC-06** Given a patient of another clinic with the same name, Then they are never returned.
- **F15-AC-07** Given support patient search results, Then no clinical fields are present.

## 4. Reference implementation

`backend/app/api/search_utils.py`, `routes/support.py`, `routes/admin_password_reset.py` (`search_users`,
`get_available_roles`), `frontend/src/utils/index.ts` (`searchQueryProblem`), `components/common/SupportSearchPanel.tsx`,
`components/common/AdminUserSearch.tsx`, tests `test_search_and_validation.py`, `SupportSearchPanel.test.tsx`.
