# Feature 22 — Patient Documents (API; screen planned)

**Roles:** P (own), D, A · **API:** `POST /patient/documents`, `POST /documents?patient_id=`,
`GET /documents/{patient_id}` · **Depends on:** F02, F03, F04 (S3, audit) · **Traces to:** `PAT-DOC-*`,
`SEC-TEN-07`, `SEC-SECRETS-04`

## 1. Purpose

Store patient documents (PDF, JPEG, PNG) in a private S3 bucket and give authorized users short-lived download
links. There is no UI yet; the API is complete.

## 2. Rules

- **DOC-01 Allowed types:** `application/pdf`, `image/jpeg`, `image/png` (by the upload's content type,
  case-insensitive), else **415 "Only PDF, JPEG and PNG documents can be uploaded."**.
- **DOC-02 Size:** at most `MAX_UPLOAD_SIZE` bytes (default 10 MB; read `max+1` bytes to detect), else
  **413 "The document is larger than <N> MB."**.
- **DOC-03 File name:** take the last path segment (after `/` or `\`), replace every character outside
  `A-Za-z0-9._-` with `_`, strip leading dots, truncate to 120; empty → `document`.
- **DOC-04 Key:** `documents/<tenant_id>/<patient_id>/<UTC yyyymmddHHMMSS>_<uploader user_id>_<safe name>` for
  patient self-uploads, and `documents/<tenant_id>/<patient_id>/<UTC yyyymmddHHMMSS>_<safe name>` for staff
  uploads.
- **DOC-05 Storage:** `put_object(Bucket=S3_BUCKET_NAME, Key, Body, ContentType)` with a module-level boto3 client.
  Bucket not configured or S3 error → log the exception and return **500 "The document couldn't be stored. Please
  try again later."** (no details).
- **DOC-06 Access:** patients only their own patient profile; doctors and admins any non-deleted patient of the
  tenant. Another patient's or tenant's id → **404 "Patient not found."** (never confirms existence). Support
  staff → 403.
- **DOC-07 Download links:** presigned `get_object` URLs valid **3,600 s**, generated only after the row passed the
  checks above; if presigning fails, `download_url` is null.
- **DOC-08 Audit:** `patient_documents` INSERT with `{document_name, file_path}` (self-upload) or
  `{patient_id, document_name}` (staff upload).

## 3. API

| Endpoint | Roles | Input | Success | Errors |
|----------|-------|-------|---------|--------|
| `POST /patient/documents` | P | multipart field `file` | **201** `{"message": "Document uploaded"}` | 404 "Patient profile not found."; 413; 415; 500 |
| `POST /documents?patient_id=<uuid>` | P (own), D, A | multipart field `file` | **201** `{"id": "<document id>"}` | 404 "Patient not found."; 413; 415; 500 |
| `GET /documents/{patient_id}` | P (own), D, A | — | `[{id, document_name, document_type, download_url (or null), signed_at (ISO or null)}]` (non-deleted rows) | 404 "Patient not found." |

Row inserted: `{tenant_id, patient_id, document_name: <safe name>, document_type: <content type>, file_path: <key>}`.

## 4. Infrastructure

Private bucket, block all public access, server-side encryption; Lambda role allowed only `s3:PutObject` and
`s3:GetObject` on `documents/*`.

## 5. Acceptance criteria

- **F22-AC-01** Given a 2 MB PDF, When a patient uploads it, Then a row exists, the key starts with
  `documents/<tenant>/<patient>/`, and an audit row exists.
- **F22-AC-02** Given a `.exe` (content type `application/octet-stream`), Then 415; given 11 MB, Then 413.
- **F22-AC-03** Given patient A listing patient B's documents, Then 404.
- **F22-AC-04** Given a file named `../../etc/passwd`, Then the stored name is `passwd`.
- **F22-AC-05** Given a listed document, Then its URL expires after one hour.

## 6. Reference implementation

`backend/app/core/storage.py`, `api/routes/documents.py`, `api/routes/patient.py` (`upload_patient_document`).
