# Feature 23 — Billing Placeholder and Other Stubs

## 1. Billing (`/patients/billing`, PATIENT)

Menu item "Billing" under Patients. The page renders a single line: "Billing Page - To be implemented". No API.

## 2. Out of scope / planned

| Item | Status |
|------|--------|
| Billing and payments | placeholder page only |
| Patient documents screen | API complete ([22](22-patient-documents.md)) |
| Soft delete / restore screen | API complete ([20](20-admin-account-management.md)) |
| Audit log screen | API complete (F04 §2) |
| Tenant onboarding UI | clinics are created by SQL / seed |
| Pharmacy management UI | pharmacies are seeded per tenant |
| Range block/unblock of slots | proposed in `openspec/changes/range-slot-blocking/` |
| Appointment reminders / notifications | only the password-reset email exists |
| Refresh tokens / "remember me" | `remember_me` is accepted and ignored |
| Real-time updates | pages reload after each action |
| Medical news feed | static cards ([01](01-home-page.md)) |
| Several locations in different zones within one clinic | one zone per tenant |
| Decorative header search, bell and profile icons | not interactive |

## 3. Rules for stubs

- Placeholder routes keep their guard (PATIENT only) and breadcrumb.
- Stub icons and pills SHALL NOT look clickable beyond their current styling and SHALL NOT call any endpoint.
