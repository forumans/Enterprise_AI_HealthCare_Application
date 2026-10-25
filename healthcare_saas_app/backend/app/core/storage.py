"""S3-backed document storage.

Replaces local-filesystem uploads so the backend runs correctly on Lambda,
where the local filesystem is ephemeral and not shared across invocations.

All objects are stored as:
  documents/<tenant_id>/<patient_id>/<timestamp>_<safe_filename>

The S3 key is persisted in PatientDocument.file_path so existing DB records
keep a stable reference regardless of bucket or region changes.
"""

from __future__ import annotations

import logging
import re

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile, status

from .config import settings

logger = logging.getLogger(__name__)

# Document types patients and staff may upload
ALLOWED_UPLOAD_TYPES = {"application/pdf", "image/jpeg", "image/png"}
UPLOAD_FAILED = "The document couldn't be stored. Please try again later."


def safe_filename(name: str | None) -> str:
    """Keep letters, digits, dot, dash and underscore; never a path or an empty name."""

    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", (name or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]).lstrip(".")
    return cleaned[:120] or "document"


async def read_validated_upload(file: UploadFile) -> bytes:
    """Read an upload, refusing disallowed types (415) and files over MAX_UPLOAD_SIZE (413)."""

    if (file.content_type or "").lower() not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF, JPEG and PNG documents can be uploaded.")
    content = await file.read(settings.max_upload_size + 1)
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"The document is larger than {settings.max_upload_size // (1024 * 1024)} MB.",
        )
    return content


def store_document(file_bytes: bytes, key: str, content_type: str) -> None:
    """Upload to S3, turning any storage failure into a generic 500 (details are logged, not returned)."""

    try:
        upload_document(file_bytes, key, content_type)
    except RuntimeError:
        logger.exception("Document upload to S3 failed.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=UPLOAD_FAILED)

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
