"""S3-backed document storage.

Replaces local-filesystem uploads so the backend runs correctly on Lambda,
where the local filesystem is ephemeral and not shared across invocations.

All objects are stored as:
  documents/<tenant_id>/<patient_id>/<timestamp>_<safe_filename>

The S3 key is persisted in PatientDocument.file_path so existing DB records
keep a stable reference regardless of bucket or region changes.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from .config import settings

# Module-level client is reused across warm Lambda invocations (no re-auth overhead).
_s3_client = None


def _get_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def upload_document(
    file_bytes: bytes,
    key: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload *file_bytes* to S3 under *key* and return the key.

    Raises RuntimeError if S3_BUCKET_NAME is not configured or the upload fails.
    """
    bucket = settings.s3_bucket_name
    if not bucket:
        raise RuntimeError(
            "S3_BUCKET_NAME environment variable is not set. "
            "Document uploads require an S3 bucket."
        )
    try:
        _get_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
    except ClientError as exc:
        raise RuntimeError(f"Failed to upload document to S3: {exc}") from exc
    return key


def generate_presigned_url(key: str, expiry_seconds: int = 3600) -> str:
    """Return a presigned GET URL for *key* valid for *expiry_seconds*.

    Raises RuntimeError if S3_BUCKET_NAME is not configured or presigning fails.
    """
    bucket = settings.s3_bucket_name
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME environment variable is not set.")
    try:
        return _get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry_seconds,
        )
    except ClientError as exc:
        raise RuntimeError(f"Failed to generate presigned URL: {exc}") from exc
