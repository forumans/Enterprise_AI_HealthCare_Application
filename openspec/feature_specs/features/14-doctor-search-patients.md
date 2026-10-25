# Feature 14 — Doctor: Search Patients and Clinical History

**Roles:** D (screen), A (API) · **Route:** `/doctors/search-patients` ·
**API:** `GET /patients/search?q=`, `GET /patient/prescriptions-full?patient_id=` · **Depends on:** 13, 15 · **Traces to:** `DOC-SRCH-*`, `SEC-AUD-03`

## 1. Purpose

A doctor finds any patient of the clinic by name and reviews their completed-visit history (care-team model).
Every view of clinical data is recorded in the audit trail.

## 2. UI

1. `h2` "Search Patients".
2. **Doctor Details** card (as in [11](11-doctor-today-appointments.md), phone unformatted).
3. Search form card: `LabeledField` "Search Patient by Name" (id `doctor-search`, help "Use at least first 2 letters
   of patient name, or * to list every patient."), button "Search" ("Searching..." / grey while busy).
   - Validation: trimmed ≥ 2 characters or `*`, else "Enter at least 2 characters of a patient name, or * to list
     everyone." under the field.
   - Changing the text after a search clears the results. Navigating away clears them.
4. Results card, `h3` "PATIENT DETAILS":
   - One line per distinct patient (first occurrence order): name as a button (selected: bold, underlined,
     `#2793d3`), "Age: <full years from DOB, 0 if none>", "Gender: <value or N/A>", "Phone: <formatted as in 11, or
     N/A>", and "Address: …" when present.
   - The first patient is selected automatically and their history loaded via
     `GET /patient/prescriptions-full?patient_id=<id>`; clicking another name loads theirs.
   - History states: loading "Loading prescription records..." (+ "Loading prescription data..." line);
     none "No prescription records found for <name>."; no selection "Select a patient to view their prescription
     records.".
   - History table columns: PRESCRIPTION DATE (date `Oct 22, 2026` over time `09:00 AM EDT`, clinic time),
     DOCTOR ("Unknown"), NOTES, SYMPTOMS, DIAGNOSIS, LAB RESULTS, MEDICATION, PHARMACY — empty cells "-";
     completed visits only, newest first.

## 3. API

### `GET /patients/search?q=` — D, A
- Trimmed `q` shorter than 2 and not `*` → `[]` (not an error).
- Matches `full_name ILIKE %q%` (name only) or everyone for `*`; non-deleted patients of the tenant.
- Returns **one row per patient × appointment × record** (LEFT JOINs to non-deleted appointments, medical records,
  prescriptions, each tenant-filtered), ordered by `full_name ASC, appointment_time DESC`, capped at 50 rows
  (no cap for `*`).
- Item `{id, name, phone, dob (YYYY-MM-DD|""), gender, address (", "-joined non-empty parts line1, line2, city,
  state, postal, country), symptoms, diagnosis, lab_results, medication, prescription_date (appointment time|"")}`.
- Writes one `READ` access event per distinct patient returned.

There is no endpoint listing every patient: people are found through searches (`*` lists everyone).

## 4. Rules

- **DOC-SRCH-05** A doctor may view the clinical history of any non-deleted patient of their tenant; every such
  view is a `READ` audit event (`viewer_role` recorded). Tenants needing stricter rules MAY limit this to patients
  with a past or present appointment with the doctor.
- Support staff never call these endpoints (403).

## 5. Acceptance criteria

- **F14-AC-01** Given patients "Ann Lee" and "Anna Kim", When searching "ann", Then both are listed and Ann Lee's
  history loads automatically.
- **F14-AC-02** Given "a", Then the UI shows the 2-character message; the API returns `[]`.
- **F14-AC-03** Given `*`, Then every patient of the clinic is listed (no cap).
- **F14-AC-04** Given a search returning 3 patients, Then 3 `READ` audit rows exist with the doctor as performer.
- **F14-AC-05** Given a support staff token, When calling `/patients/search`, Then 403.

## 6. Reference implementation

`frontend/src/components/pages/SearchPatientsPage.tsx`, `backend/app/api/routes/patients.py`,
`tests/test_patient_search.py`.
