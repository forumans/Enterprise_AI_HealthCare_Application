# Feature 18 — Admin: System Dashboard and Reports

**Roles:** A · **Route:** `/admin/system-dashboard` (admin landing page) ·
**API:** `GET /admin/users`, `GET /admin/reports`, `GET /admin/appointment-metrics`, `GET /admin/appointments`,
`GET /tenants/current` · **Depends on:** F03, F05 · **Traces to:** `ADM-DASH-*`

## 1. Purpose

Clinic-wide counts, appointment metrics in clinic-local periods, quick links to registration, and the most
recently created users.

## 2. UI

`h2` "System Dashboard".

1. **Administrator** card (`h3`): "Name" (the signed-in admin's name, `session.userName` from login; "System
   Administrator" if the admin has no profile name), "Role" = "Administrator", "Tenant Name" = clinic name from
   `GET /tenants/current` (fallback: tenant id, then "-").
2. While loading: card "Loading dashboard data...". Data loaded in parallel: `GET /admin/users` (page 1, 25),
   `GET /admin/reports`, `GET /admin/appointment-metrics`.
3. **System Overview** card — 7 tiles (big number over an uppercase muted label), each with its own tint:

| Tile label | Value | Number color |
|------------|-------|--------------|
| Total Doctors | `reports.doctor_count` | `#42b5f5` |
| Total Patients | `reports.patient_count` | `#49d7c2` |
| Appointments (To Date) | `total_appointments_to_date` | `#ff90ab` |
| Appointments YTD | `total_appointments_year_to_date` | `#ffc107` |
| Appointments This Month | `total_appointments_this_month` | `#b542f5` |
| Appointments This Week | `total_appointments_this_week` | `#42f5a6` |
| Appointments Today | `total_appointments_today` | `#f58142` |

   Missing values show 0.
4. **Quick Actions** card — buttons "Register New Support Staff" → `/admin/register-support-staff`,
   "Register New Doctor" → `/admin/register-doctor`, "Register New Patient" → `/admin/register-patient`,
   "Register New Admin" → `/admin/register-admin`.
5. **Recent Users (<N>)** card (only when users exist): the first 10 rows of `GET /admin/users` — Name, Email, Role,
   Status pill "Active" (teal) / "Inactive" (pink) from `is_active`.

## 3. Rules

- **ADM-DASH-03** Doctor and patient totals are **server-side counts** of profiles that aren't deleted and whose
  login isn't deleted or deactivated — never a count of a paged list.
- **ADM-DASH-04** Appointment metrics count non-deleted appointments with `appointment_time <= now`; windows start at
  clinic-local midnights (UTC instants): today; Monday of this week; first of this month; January 1st. Future and
  cancelled (soft-deleted) appointments are not counted.

## 4. API (all A, tenant-scoped)

### `GET /admin/users?page=1&page_size=25`
`page ≥ 1`, `1 ≤ page_size ≤ 500`. One query: users of the tenant, not deleted, `created_at DESC`, with the profile
name from whichever profile matches the role (`coalesce`). Item
`{id, name (profile name or email), email, role, is_deleted, is_active}`.

### `GET /admin/reports?date_from=&date_to=`
Parameters accepted and ignored. Response:
```json
{
  "doctor_count": 12,              // active doctors (profile + user not deleted, user active)
  "patient_count": 340,            // active patients (same rule)
  "monthly_patient_count": 351,    // all non-deleted patient profiles (name kept for compatibility)
  "diagnosis_frequency": 87,       // non-deleted medical records
  "doctor_utilization_rate": 7.25  // completed non-deleted appointments ÷ non-deleted doctors, 2 decimals; 0 when no doctors
}
```

### `GET /admin/appointment-metrics`
```json
{
  "total_appointments_to_date": 0,
  "total_appointments_year_to_date": 0,
  "total_appointments_this_month": 0,
  "total_appointments_this_week": 0,
  "total_appointments_today": 0
}
```
One aggregate query with `SUM(CASE WHEN appointment_time >= <window start> THEN 1 ELSE 0 END)` per window.

### `GET /admin/appointments?page=&page_size=` (API only)
Paged, `appointment_time DESC`, joined to tenant doctors and patients, **including cancelled** visits:
`[{id, date, doctor (id), doctor_name, patient (id), patient_name, status, is_cancelled}]` where
`is_cancelled = status == CANCELLED or deleted_at is not null`.

## 5. Acceptance criteria

- **F18-AC-01** Given 3 active doctors, 1 deactivated and 1 deleted, Then Total Doctors = 3.
- **F18-AC-02** Given appointments yesterday, today at 8 AM (past), today at 6 PM (future) and one cancelled
  today, When viewed at noon, Then Today = 1 and To Date = 2.
- **F18-AC-03** Given a clinic in `America/Los_Angeles` at 11 PM PT on the last day of the month, Then "This Month"
  uses the PT month.
- **F18-AC-04** Given 30 users, Then Recent Users shows 10, newest first.
- **F18-AC-05** Given `page_size=501`, Then 422.

## 6. Reference implementation

`frontend/src/components/pages/SystemDashboardPage.tsx`, `systemDashboardStats.ts` (+ test),
`hooks/useUserData.ts`, `backend/app/api/routes/admin.py`, `tests/test_admin_appointment_metrics.py`.
