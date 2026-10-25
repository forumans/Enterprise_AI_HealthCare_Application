# Feature 13 — Patient: Prescriptions and Medical History

**Roles:** P (own data); D uses the same endpoint with `patient_id` ([14](14-doctor-search-patients.md)) ·
**Route:** `/patients/prescriptions` · **API:** `GET /patient/me`, `GET /patient/prescriptions-full` · **Depends on:** 12 ·
**Traces to:** `PAT-RX-*`, `BR-CLIN-07`

## 1. Purpose

The patient reviews their completed visits with symptoms, diagnoses, lab results, medications and pharmacies.

## 2. UI

- `h2` "My Prescriptions & Medical Records"; muted text "View your completed appointments, prescriptions, and
  medical history". Opening the page clears the global status.
- Loading: "Loading your prescriptions and medical records..." (centered muted). Error: the server message in a
  pink box; nothing else.
- **Patient Information** card (`h2` 18 px): small uppercase labels "Name", "Email", "Phone", "Date of Birth"
  (shown as `M/D/YYYY` in UTC so the date doesn't shift), each "N/A" when empty. Source `GET /patient/me`.
- **Summary cards** (3, grid): "Total Prescriptions" = number of rows; "Completed Appointments" = rows with
  `appointment_status = COMPLETED`; "Active Medications" = rows with non-empty `medication_details`.
- **Table** card: empty → "No completed appointments or prescriptions found." and smaller "Your prescriptions and
  medical records will appear here after you complete appointments." Otherwise columns: Appointment Time (bold,
  `Oct 22, 2026, 09:00 AM EDT` clinic time), Doctor ("N/A"), Status (pill), Notes, Symptoms, Diagnosis,
  Lab Results, Medication, Pharmacy — empty cells show "-". Alternate rows faintly striped.

## 3. API

### `GET /patient/me` — P
Own profile (404 "Patient profile not found."):
`{id, name, email, phone, date_of_birth (YYYY-MM-DD|null), insurance_provider, insurance_policy_number,
address: "<line1> <line2> <city> <state> <postal> <country>" trimmed, emergency_contact: null, emergency_phone: null}`.

### `GET /patient/prescriptions-full?patient_id=` — P (own; parameter ignored), D (`patient_id` required)
- PATIENT → own profile. DOCTOR → `patient_id` required (**400 "patient_id is required for doctors"**), a
  non-deleted patient of the tenant (**404 "Patient not found"**); writes a `READ` access event on `patients`.
  Other roles → 403.
- Query (one statement): appointments of that patient with `status = 'COMPLETED'` and `deleted_at IS NULL`,
  joined to the doctor, LEFT JOIN the non-deleted medical record, its non-deleted prescription and the non-deleted
  pharmacy; ordered by `appointment_time DESC`.
- Item `{appointment_time, doctor_name, appointment_status, appointment_note, symptoms, diagnosis, lab_results,
  medication_details, pharmacy_name, appointment_created_at}` (strings default to "").

## 4. Acceptance criteria

- **F13-AC-01** Given a completed, a scheduled and a cancelled appointment, Then only the completed one is listed.
- **F13-AC-02** Given a completed visit without a prescription, Then Medication and Pharmacy show "-" and "Active
  Medications" doesn't count it.
- **F13-AC-03** Given a patient passing another patient's id, Then their own data is returned (parameter ignored).
- **F13-AC-04** Given a doctor without `patient_id`, Then 400; with an id of another tenant, Then 404.

## 5. Reference implementation

`frontend/src/components/pages/PatientPrescriptionsPage.tsx`, `backend/app/api/routes/patient.py`.
