"""Support staff model (see migrations/005_add_support_staff_role.sql)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, SoftDeleteMixin


class SupportStaff(Base, SoftDeleteMixin):
    """Support staff profile: manages appointments and availability on behalf of patients and doctors."""

    __tablename__ = "support_staff"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()"))
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
