"""Range blocks of a doctor's schedule (see migrations/010_schedule_blocks.sql)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Stored code -> label shown to doctors and staff (patients only ever see "Unavailable")
BLOCK_REASON_CATEGORIES = {
    "VACATION": "Vacation",
    "CONFERENCE": "Conference",
    "SICK": "Sick",
    "PERSONAL": "Personal",
    "ADMINISTRATIVE": "Administrative",
    "OTHER": "Other",
}


class ScheduleBlock(Base):
    """A doctor's blocked range [start_time, end_time) in UTC. Slots it blocks carry its id in block_id.

    Never deleted by the app: when its last future slot is unblocked it gets released_at/released_by.
    """

    __tablename__ = "schedule_blocks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()"))
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    doctor_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason_category: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_note: Mapped[Optional[str]] = mapped_column(String(500))
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    released_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
