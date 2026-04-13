"""Document routes required by backend prompt.

UI currently uploads via `/patient/documents`; this route adds generic
`/documents` operations while keeping tenant checks and auditability.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...core.storage import generate_presigned_url, upload_document
from ...models import Patient, PatientDocument
from ...services.audit_service import write_audit_log

router = APIRouter(prefix="/documents")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_document(
    patient_id: str,
    file: UploadFile = File(...),
    identity: CurrentIdentity = Depends(require_roles("ADMIN", "DOCTOR", "PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    patient = (
        await db.execute(
            select(Patient).where(
                and_(
                    Patient.id == patient_id,
                    Patient.tenant_id == identity.tenant_id,
                    Patient.deleted_at.is_(None),
                )
            )
        )
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = (file.filename or "document.bin").replace("/", "_").replace("\\", "_")
    s3_key = f"documents/{identity.tenant_id}/{patient_id}/{timestamp}_{safe_name}"

    try:
        upload_document(await file.read(), s3_key, file.content_type or "application/octet-stream")
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    record = PatientDocument(
        tenant_id=identity.tenant_id,
        patient_id=patient_id,
        document_name=file.filename,
        document_type=file.content_type,
        file_path=s3_key,
    )
    db.add(record)
    await db.flush()

    await write_audit_log(
        db,
        tenant_id=identity.tenant_id,
        table_name="patient_documents",
        record_id=record.id,
        action_type="INSERT",
        old_data=None,
        new_data={"patient_id": patient_id, "document_name": record.document_name},
        performed_by=identity.user_id,
    )
    await db.commit()
    return {"id": record.id}


@router.get("/{patient_id}")
async def list_documents(
    patient_id: str,
    identity: CurrentIdentity = Depends(require_roles("ADMIN", "DOCTOR", "PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(PatientDocument).where(
        PatientDocument.tenant_id == identity.tenant_id,
        PatientDocument.patient_id == patient_id,
        PatientDocument.deleted_at.is_(None),
    )
    rows = (await db.execute(stmt)).scalars().all()
    results = []
    for row in rows:
        try:
            download_url = generate_presigned_url(row.file_path)
        except RuntimeError:
            download_url = None
        results.append(
            {
                "id": row.id,
                "document_name": row.document_name,
                "document_type": row.document_type,
                "download_url": download_url,
                "signed_at": row.signed_at.isoformat() if row.signed_at else None,
            }
        )
    return results
