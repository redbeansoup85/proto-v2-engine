from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from infra.api.endpoints.models.base import Base


class ApprovalDecisionEvent(Base):
    __tablename__ = "approval_decision_events"
    __table_args__ = ()

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    approval_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("approvals.id", ondelete="CASCADE"),
        nullable=False,
    )

    approver_id: Mapped[str] = mapped_column(String(128), nullable=False)

    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # 'approved' | 'rejected'

    decided_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
