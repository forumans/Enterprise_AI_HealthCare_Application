# Prompt: S3 Document Storage

## Prompt

Implement patient document upload and retrieval using AWS S3. Lambda has an ephemeral filesystem (`/tmp`, max 512 MB) — never write patient files to disk. All uploads go directly to S3; downloads return presigned URLs.

---

### S3 Key Format

```
documents/<tenant_id>/<patient_id>/<timestamp>_<original_filename>
```

Example: `documents/abc-tenant-uuid/def-patient-uuid/1704067200_lab_report.pdf`

This structure allows:
- Tenant-level IAM policy restrictions
- Patient-level listing without a DB query
- Collision-free filenames via timestamp prefix

---

### Storage Utility (`backend/app/core/storage.py`)

```python
import boto3
import os
from botocore.exceptions import ClientError

# Module-level singleton — reused across warm Lambda invocations
_s3_client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))

def upload_document(
    file_bytes: bytes,
    key: str,
    content_type: str = "application/octet-stream",
    bucket: str | None = None,
) -> str:
    """Upload bytes to S3. Returns the S3 key."""
    bucket = bucket or settings.s3_bucket_name
    _s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key

def generate_presigned_url(
    key: str,
    expiry_seconds: int = 3600,
    bucket: str | None = None,
) -> str:
    """Generate a presigned GET URL valid for expiry_seconds."""
    bucket = bucket or settings.s3_bucket_name
    return _s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry_seconds,
    )
```

**Why module-level client:** boto3 client creation involves SSL handshake and DNS. Creating it once per execution environment (not per request) significantly reduces latency on warm invocations.

---

### Document Upload Endpoint

The upload endpoint reads the file into memory (not to disk), builds the S3 key, uploads, then saves the metadata record.

```python
# backend/app/api/routes/patients.py

@router.post("/patient/documents")
async def upload_document(
    file: UploadFile,
    identity: CurrentIdentity = Depends(require_roles("PATIENT")),
    db: AsyncSession = Depends(get_db),
):
    # Read into memory — Lambda has no persistent filesystem
    file_bytes = await file.read()

    # Enforce upload size limit (default 10 MB)
    if len(file_bytes) > settings.max_upload_size:
        raise HTTPException(413, "File too large")

    # Build S3 key
    timestamp = int(datetime.utcnow().timestamp())
    safe_name = secure_filename(file.filename)
    key = f"documents/{identity.tenant_id}/{patient.id}/{timestamp}_{safe_name}"

    # Upload to S3
    upload_document(file_bytes, key, content_type=file.content_type)

    # Save metadata to DB
    doc = PatientDocument(
        tenant_id=identity.tenant_id,
        patient_id=patient.id,
        document_name=file.filename,
        document_type=file.content_type,
        file_path=key,
    )
    db.add(doc)
    await db.commit()

    return {"id": str(doc.id), "document_name": doc.document_name, "created_at": doc.created_at}
```

---

### Document List Endpoint

When listing documents, generate a presigned URL for each so the client can download directly from S3 without routing through Lambda.

```python
@router.get("/patient/documents")
async def list_documents(...):
    docs = await get_patient_documents(db, identity)
    return [
        {
            "id": str(doc.id),
            "document_name": doc.document_name,
            "document_type": doc.document_type,
            "created_at": doc.created_at,
            "download_url": generate_presigned_url(doc.file_path, expiry_seconds=3600),
        }
        for doc in docs
    ]
```

Presigned URLs expire after 1 hour. Clients should not cache them longer than that.

---

### IAM Policy

The Lambda execution role needs these permissions on the documents bucket:

```json
{
  "Effect": "Allow",
  "Action": ["s3:PutObject", "s3:GetObject"],
  "Resource": "arn:aws:s3:::healthcare-patient-documents/*"
}
```

This is handled by the SAM template's `S3CrudPolicy` in `backend/template.yaml`.

---

### Environment Variables

| Variable | Description |
|----------|-------------|
| `S3_BUCKET_NAME` | Name of the patient documents S3 bucket |
| `MAX_UPLOAD_SIZE` | Maximum file size in bytes (default `10485760` = 10 MB) |
| `AWS_REGION` | Region where the bucket lives (default `us-east-1`) |

---

### File Type Validation

Validate content type server-side — never trust the client's `Content-Type` header alone:

```python
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "text/plain",
}

if file.content_type not in ALLOWED_CONTENT_TYPES:
    raise HTTPException(415, "Unsupported file type")
```

---

### Deliverables

- `backend/app/core/storage.py` — `upload_document()` and `generate_presigned_url()`
- Document upload and list endpoints in `backend/app/api/routes/patients.py`
- File type and size validation
- `backend/tests/test_storage.py` — unit tests with mocked S3 client

### Acceptance Criteria

- `POST /patient/documents` uploads the file to S3 and saves metadata to DB.
- `GET /patient/documents` returns documents with valid presigned `download_url` fields.
- Files larger than `MAX_UPLOAD_SIZE` are rejected with 413.
- Unsupported file types are rejected with 415.
- No patient file is written to the Lambda filesystem (`/tmp` or otherwise).
- S3 client is instantiated at module level (not per request).
