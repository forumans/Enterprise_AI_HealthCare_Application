# Known Gaps — Current Code vs. Feature Specifications

Found while reverse-engineering the code at commit `bc3b34c` (2026-10-25). The feature specs state the
**intended** behavior; this file records where the running code differs, so that:

- an agent rebuilding from the specs knows these are deliberate corrections, not omissions, and
- the existing application can be fixed one gap at a time.

Severity: **High** = security or data integrity · **Medium** = wrong behavior users can hit · **Low** = cosmetic,
consistency, or dead code · **Info** = documented limitation.

## 1. Open

None. Every gap found in the review is fixed (§2). Add new ones here as they are found.

## 2. Fixed

| ID | Fixed in | What changed |
|----|----------|--------------|
| GAP-01 | this change | Health endpoints are also served unprefixed (`/health`, `/health/ready`, `/health/live`). |
| GAP-02 | `aaa6535` | Only the appointment's own doctor can confirm it. |
| GAP-03 | `aaa6535` | Deactivated doctors aren't listed for patients or bookable; support search flags them "(inactive)". |
| GAP-04 | this change | Admin-created users get a `users` INSERT audit row naming the admin. |
| GAP-05 | this change | Soft delete sets `users.deleted_by`. |
| GAP-06 | this change | Registration (patient, doctor) validates email, phone, gender, date of birth and doctor age ≥ 18 on the server. |
| GAP-07 | this change | The admin patient form sends gender enum values; the server stores any-case input as the enum value. |
| GAP-08 | this change | Patient registration failures show the server's message. |
| GAP-09 | this change | The consultation form checks symptoms ≥ 5 and diagnosis ≥ 3 characters before saving. |
| GAP-10 | this change | Manage Availability's "Next Week" stops at week 4. |
| GAP-11 | this change | Every route has a breadcrumb label (stale entries removed). |
| GAP-12 | this change | Unblocking asks for confirmation instead of a reason that was thrown away. |
| GAP-13 | this change | Cancelled appointments are listed with `include_cancelled=true`: patients see them under Past, doctors in their week. |
| GAP-14 | this change | Login returns `user_name` for every role, so the dashboard shows the admin's name; Recent Users status comes from `is_active`. |
| GAP-15 | this change | Patient profile updates are validated, and cleared optional fields are stored as NULL. |
| GAP-16 | this change | Doctor profile updates are validated and trimmed. |
| GAP-17 | this change | Bad audit-log date filters return 422 "Invalid datetime format.". |
| GAP-18 | this change | Support appointment lists leave out deleted doctors. |
| GAP-20 | this change | Unused components and helpers removed. |
| GAP-21 | this change | The login page no longer checks password length; the server decides. |
| GAP-22 | this change | 14 duplicate or legacy endpoints removed; `DELETE /doctor/availability/{id}` and `GET /admin/appointments` kept as supported API (no other endpoint does what they do). |
| GAP-23 | this change | Appointment status only moves forward; a completed visit can't be reopened. |
| GAP-24 | this change | Doctor appointment details refuse any non-UUID id with 400. |
| GAP-25 | this change | Rate-limit counters live in PostgreSQL (migration 009), shared by all instances; in-memory fallback before the migration. |
| GAP-26 | this change | The patient appointments page loads the appointment list once. |

IDs are never reused.

## 3. Closing a gap

1. Fix the code and add the tests named in the matching acceptance criterion.
2. Move the row to §2 with the commit id.
3. If the intended behavior changed instead, update the feature spec and move the row to §2 with a note.
