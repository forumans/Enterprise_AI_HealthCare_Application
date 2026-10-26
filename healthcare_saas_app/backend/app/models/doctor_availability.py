"""Doctor availability slots."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SlotStatus:
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"


class DoctorAvailability(Base):
    __tablename__ = "doctor_availability"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()"))
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    doctor_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    slot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("AVAILABLE", "BOOKED", "BLOCKED", name="slot_status", create_type=False),
        nullable=False,
        server_default=text("'AVAILABLE'"),
    )
    block_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The range block that wants this hour blocked (migration 010). BOOKED + block_id = needs rescheduling.
    block_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("schedule_blocks.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
