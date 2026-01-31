from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from infra.api.endpoints.models.base import Base


class Approval(Base):
    __tablename__ = "approvals"

    # DB column is "id"
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    execution_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("execution_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    requester_type: Mapped[str] = mapped_column(String(16), nullable=False)
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False)

    mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'single'"))
    required_approvers: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3600"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'"))

    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    approved_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
