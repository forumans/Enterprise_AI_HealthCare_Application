"""Prescription model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, SoftDeleteMixin


class Prescription(Base, SoftDeleteMixin):
    __tablename__ = "prescriptions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()"))
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    medical_record_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("medical_records.id", ondelete="CASCADE"), nullable=False, unique=True)
    pharmacy_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("pharmacies.id", ondelete="SET NULL"))
    medication_details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
