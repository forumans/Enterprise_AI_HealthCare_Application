"""Document routes required by backend prompt.

UI currently uploads via `/patient/documents`; this route adds generic
`/documents` operations while keeping tenant checks and auditability.
"""

from __future__ import annotations


from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import CurrentIdentity, get_current_identity, require_roles
from ...core.database import get_db
from ...core.timeutils import utc_now
from ...core.storage import generate_presigned_url, read_validated_upload, safe_filename, store_document
from ...models import Patient, PatientDocument
from ...services.audit_service import write_audit_log

router = APIRouter(prefix="/documents")


async def _accessible_patient(db: AsyncSession, identity: CurrentIdentity, patient_id: str) -> Patient:
    """The patient whose documents the caller may use: patients only their own, staff any in the tenant.

    Another patient's id (or another tenant's) is reported as not found, without confirming it exists.
    """

    conditions = [Patient.id == patient_id, Patient.tenant_id == identity.tenant_id, Patient.deleted_at.is_(None)]
    if (identity.role or "").upper() == "PATIENT":
        conditions.append(Patient.user_id == identity.user_id)
    patient = (await db.execute(select(Patient).where(and_(*conditions)))).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return patient


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_document(
    patient_id: str,
    file: UploadFile = File(...),
    identity: CurrentIdentity = Depends(require_roles("ADMIN", "DOCTOR", "PATIENT")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    patient = await _accessible_patient(db, identity, patient_id)
    content = await read_validated_upload(file)

    timestamp = utc_now().strftime("%Y%m%d%H%M%S")
    s3_key = f"documents/{identity.tenant_id}/{patient.id}/{timestamp}_{safe_filename(file.filename)}"
    store_document(content, s3_key, file.content_type)

    record = PatientDocument(
        tenant_id=identity.tenant_id,
        patient_id=patient.id,
        document_name=safe_filename(file.filename),
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
        new_data={"patient_id": patient.id, "document_name": record.document_name},
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
    patient = await _accessible_patient(db, identity, patient_id)
    stmt = select(PatientDocument).where(
        PatientDocument.tenant_id == identity.tenant_id,
        PatientDocument.patient_id == patient.id,
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
