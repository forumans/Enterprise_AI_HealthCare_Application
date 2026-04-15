## ADDED Requirements

### Requirement: Patient documents stored in S3, never on Lambda filesystem
The system SHALL upload patient documents directly to S3 using an in-memory byte stream. Files SHALL NOT be written to the Lambda filesystem (`/tmp` or any other path). The S3 object key SHALL follow the format `documents/<tenant_id>/<patient_id>/<timestamp>_<sanitised_filename>`.

#### Scenario: Document upload goes to S3
- **GIVEN** a patient uploads a file via `POST /patient/documents`
- **WHEN** the upload handler processes the request
- **THEN** the file bytes SHALL be sent to S3 via `put_object` and no temporary file SHALL be created on the Lambda filesystem

#### Scenario: S3 key format is correct
- **GIVEN** a patient in tenant `abc-uuid` with patient ID `def-uuid` uploading `lab report.pdf`
- **WHEN** the upload handler constructs the S3 key
- **THEN** the key SHALL match the pattern `documents/abc-uuid/def-uuid/<unix_timestamp>_lab_report.pdf` with the filename sanitised (spaces replaced, special characters removed)

---

### Requirement: Module-level S3 client singleton
The boto3 S3 client SHALL be instantiated once at module level in `backend/app/core/storage.py`. It SHALL NOT be created per request. This pattern reuses the existing SSL connection and DNS resolution across warm Lambda invocations.

#### Scenario: S3 client reused across warm invocations
- **GIVEN** a Lambda execution environment that has processed at least one request
- **WHEN** a second document upload request arrives
- **THEN** the same module-level `_s3_client` instance SHALL be used, not a newly created client

---

### Requirement: Presigned URLs for document downloads
WHEN a patient retrieves their document list via `GET /patient/documents`, each document entry SHALL include a `download_url` field containing a presigned S3 GET URL. The URL SHALL expire after 3600 seconds. Clients SHALL NOT cache presigned URLs longer than their expiry.

#### Scenario: Presigned URL in document list
- **GIVEN** a patient with documents stored in S3
- **WHEN** `GET /patient/documents` is called
- **THEN** each document in the response SHALL include a non-empty `download_url` that resolves to the correct S3 object and expires in 3600 seconds

#### Scenario: Expired presigned URL rejected by S3
- **GIVEN** a presigned URL that has passed its expiry time
- **WHEN** the client attempts to use the URL to download the document
- **THEN** S3 SHALL reject the request with 403 — the system does not need to handle this; the client should call the list endpoint again to obtain a fresh URL

---

### Requirement: File size limit enforced server-side
The system SHALL reject document uploads whose file size exceeds `MAX_UPLOAD_SIZE` bytes (default 10 MB). The size check SHALL occur after reading the file into memory. IF the file exceeds the limit the system SHALL return `413 Request Entity Too Large`.

#### Scenario: File within size limit accepted
- **GIVEN** `MAX_UPLOAD_SIZE` is 10,485,760 bytes (10 MB)
- **WHEN** a patient uploads a 5 MB PDF
- **THEN** the system SHALL accept the file and upload it to S3

#### Scenario: File exceeding size limit rejected
- **GIVEN** `MAX_UPLOAD_SIZE` is 10,485,760 bytes
- **WHEN** a patient attempts to upload a 15 MB file
- **THEN** the system SHALL return `413 Request Entity Too Large` and SHALL NOT upload anything to S3

---

### Requirement: File type validation server-side
The system SHALL validate the `Content-Type` of uploaded files against an allowlist: `application/pdf`, `image/jpeg`, `image/png`, `image/tiff`, `text/plain`. IF the content type is not in the allowlist the system SHALL return `415 Unsupported Media Type`. The server SHALL NOT rely solely on the client-provided `Content-Type` header.

#### Scenario: PDF upload accepted
- **GIVEN** a patient uploads a file with content type `application/pdf`
- **WHEN** the upload handler validates the content type
- **THEN** the upload SHALL proceed

#### Scenario: Disallowed file type rejected
- **GIVEN** a patient attempts to upload a file with content type `application/zip`
- **WHEN** the upload handler validates the content type
- **THEN** the system SHALL return `415 Unsupported Media Type` and SHALL NOT store the file

---

### Requirement: Lambda execution role has S3 permissions
The Lambda execution role SHALL have `s3:PutObject` and `s3:GetObject` permissions scoped to the patient documents S3 bucket ARN (`arn:aws:s3:::healthcare-patient-documents/*`). The SAM template SHALL grant these via `S3CrudPolicy`.

#### Scenario: Upload succeeds with correct IAM role
- **GIVEN** the Lambda execution role has the required S3 permissions
- **WHEN** the upload handler calls `_s3_client.put_object()`
- **THEN** the call SHALL succeed without an AccessDenied error
