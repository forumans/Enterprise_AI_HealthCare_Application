# Feature 12 — Consultation and Clinical Records

**Roles:** D (own appointments); A and P have read access to parts of the API ·
**Route:** `/doctors/consultation/:appointmentId` ·
**API:** `GET /doctor/appointments/{id}`, `GET /prescriptions/pharmacies`, `POST /medical-records`,
`GET /medical-records/{appointment_id}`, `POST /prescriptions`, `GET /prescriptions/{id}`,
`PATCH /appointments/{id}/status` · **Depends on:** 07, 11 · **Traces to:** `BR-CLIN-*`, `DOC-CONS-*`

## 1. Purpose

During a confirmed visit the doctor records symptoms, lab results and diagnosis, optionally prescribes a
medication routed to a pharmacy, and completes the appointment.

## 2. UI

### 2.1 Loading
While loading: `h2` "Consultation" and a card "Loading appointment details...". The page loads in parallel
`GET /doctor/appointments/{id}` and `GET /prescriptions/pharmacies`.

### 2.2 Load failure
- Server message "Appointment not found" (cancelled, deleted or not this doctor's) → bold pink box
  "Appointment was cancelled by the patient. Cannot start consultation." with the line "Please navigate back to
  your appointments list to continue." **No form.**
- Any other failure → the server message in a pink box; the form is still shown.

### 2.3 Page
`h2` "Patient Consultation".

**Appointment Details** card (`h3`): "Patient:" name · "Date & Time:" (`Thu, Oct 22, 09:00 AM EDT` style, clinic
time) · "Reason for Visit:" (notes, or "No reason provided").

**Consultation Details** card (`h3`), success/error boxes above the form:

| Label | Control | Required | Placeholder |
|-------|---------|:-:|-------------|
| Symptoms | textarea, 4 rows | yes | "Enter patient symptoms..." |
| Lab Results | textarea, 3 rows | no | "Enter lab results (if any)..." |
| Diagnosis | textarea, 3 rows | yes | "Enter diagnosis..." |
| *Prescription (Optional)* — bordered group, `h4` | | | |
| Medication | text | no | "Enter medication name..." |
| Dosage | text | no | "e.g., 500mg, 1 tablet, 5ml..." |
| Instructions | textarea, 2 rows | no | "e.g., Take twice daily with food..." |
| Pharmacy | select | no | first option "Select a pharmacy (optional)"; then "<name> - <address>" (address part omitted when empty). With no pharmacies: a disabled option "No pharmacies available" and the italic note "No pharmacies are currently available in the system." |

Buttons (equal width): **"Complete Consultation"** (primary; "Saving..." and disabled while saving) and
**"Cancel"** (slate `#64748b`) → `/doctors/today-appointments`.

### 2.4 Save flow
1. Client check: symptoms and diagnosis non-empty, else "Please fill in at least symptoms and diagnosis fields".
   Then, after trimming: symptoms < 5 → "Symptoms must be at least 5 characters."; diagnosis < 3 → "Diagnosis must be
   at least 3 characters." (the server's minimums). No request is sent in these cases.
2. `POST /medical-records {appointment_id, patient_id: <from details>, diagnosis, notes: symptoms, lab_results:
   value or null}`.
   - If the error message contains "Medical record already exists for appointment": show success text
     "Medical record already exists. Fetching existing record..." and load `GET /medical-records/{appointment_id}`
     to reuse its id (re-save after a partial failure).
3. If **both** medication and dosage are filled and a record id is known: `POST /prescriptions
   {medical_record_id, medication_details: "<medication> - <dosage>. <instructions or 'Take as prescribed'>",
   pharmacy_id: selected or null}`.
4. `PATCH /appointments/{id}/status {status: "COMPLETED"}`.
5. Show "Consultation completed successfully!" and after 2 s navigate to `/doctors/today-appointments`.
6. Any failure in 2–4 (other than the handled 409) → "Failed to save consultation details"; the form keeps its
   values.

## 3. Business rules

- **BR-CLIN-01** Only the appointment's own doctor opens and saves its consultation. The UI enables the entry only
  for `CONFIRMED` ([11](11-doctor-today-appointments.md)); the server accepts a record only when the appointment
  is `CONFIRMED` or `COMPLETED` (the latter so a re-save after partial failure works), else
  **400 "Only confirmed appointments can be consulted."**.
- **BR-CLIN-02** Symptoms ≥ 5 characters (`notes` `min_length=5`), diagnosis ≥ 3 (`min_length=3`); lab results
  optional. Values are trimmed.
- **BR-CLIN-03** One medical record per appointment (unique `appointment_id`) → second insert
  **409 "Medical record already exists for appointment."**.
- **BR-CLIN-04** One prescription per record (unique `medical_record_id`) → **409 "Prescription already
  exists."**. The pharmacy, if given, must be a non-deleted pharmacy of the tenant (**404 "Pharmacy not found."**).
- **BR-CLIN-05** After saving, the appointment becomes `COMPLETED` (terminal).
- **BR-CLIN-06** Clinical text never appears in application logs; audit rows record ids only.
- **BR-CLIN-07** Reads of a medical record by a doctor or admin write a `READ` access event.

## 4. API

### `GET /doctor/appointments/{appointment_id}` — D
- `appointment_id` that isn't a UUID (e.g. `all`) → **400 "Invalid appointment ID"**, before any query.
- Caller's doctor profile (none → 404 "Doctor not found"); appointment of that doctor in the tenant, not
  soft-deleted, with a non-deleted patient, else **404 "Appointment not found"**.
- 200 `{id, time, patient_id, patient_name, status, notes}`.

### `POST /medical-records` — D
Request `{appointment_id: str, patient_id?: str, diagnosis: str(min 3), notes: str(min 5), lab_results?: str}`.
- Caller's doctor profile, else 403 "Doctor profile not found.".
- Appointment: `id`, tenant, `doctor_id = caller`, not deleted, and `patient_id` match when given; else
  **404 "Appointment not found."**. Status check BR-CLIN-01.
- Insert `{tenant, appointment_id, diagnosis, symptoms: notes, lab_results or NULL}` (trimmed); unique violation →
  409. Audit `medical_records` INSERT `{appointment_id}`.
- **201** `{"id": "<uuid>", "message": "Medical record saved."}`.

### `GET /medical-records/{appointment_id}` — P (own), D (own), A
Record of that appointment (tenant, not deleted); patients only for their own appointments, doctors only for
their own; else **404 "Medical record not found."** (never confirms existence). D/A reads are access-logged.
200 `{id, appointment_id, symptoms, diagnosis, lab_results}`.

### `POST /prescriptions` — D (own record), A
Request `{medical_record_id: str, pharmacy_id?: str, medication_details: str(min 1)}`.
- Record in tenant and not deleted, else 404 "Medical record not found."; for doctors the record's appointment
  must be theirs (else the same 404). Pharmacy check (BR-CLIN-04).
- Insert (trimmed details); unique violation → 409. Audit `prescriptions` INSERT `{medical_record_id}`.
- **201** `{"id": "<uuid>"}`.

### `GET /prescriptions/pharmacies` — P, D, A
Non-deleted pharmacies of the tenant: `[{id, name, address ("" if null), phone ("" if null)}]`; unexpected error →
500 "Failed to fetch pharmacies".

### `GET /prescriptions/{prescription_id}` — P (own), D, A
Tenant, not deleted; for patients joined through record → appointment → patient = caller. Else
**404 "Prescription not found."**. 200 `{id, medical_record_id, pharmacy_id, medication_details}`.

## 5. Acceptance criteria

- **F12-AC-01** Given a `CONFIRMED` appointment, When the doctor saves symptoms, diagnosis and a prescription,
  Then exactly one record and one prescription exist, the appointment is `COMPLETED`, and the visit appears on the
  patient's prescriptions page.
- **F12-AC-02** Given medication without dosage, Then no prescription is created; the record and completion still
  happen.
- **F12-AC-03** Given a `SCHEDULED` appointment, When `POST /medical-records` is called, Then 400 "Only confirmed
  appointments can be consulted.".
- **F12-AC-04** Given another doctor's appointment, When the record is posted, Then 404 "Appointment not found.".
- **F12-AC-05** Given a record already saved but the status update failed, When the doctor saves again, Then the
  existing record is reused and the appointment becomes `COMPLETED`.
- **F12-AC-06** Given a cancelled appointment URL, When opened, Then "Appointment was cancelled by the patient.
  Cannot start consultation." and no form.
- **F12-AC-07** Given diagnosis "ab", Then the server returns 422.
- **F12-AC-08** Given a pharmacy of another tenant, Then 404 "Pharmacy not found.".

## 6. Reference implementation

`frontend/src/components/pages/ConsultationForm.tsx`, `backend/app/api/routes/medical_records.py`,
`prescriptions.py`, `doctor.py` (`doctor_get_appointment_details`).
