from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Text, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

from infra.api.endpoints.models.base import Base


class ExecutionRun(Base):
    __tablename__ = "execution_runs"

    # DB column is "id" (not "execution_id")
    execution_id: Mapped[str] = mapped_column(
        "id",
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    project_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # DB uses VARCHAR(64) currently; keep it aligned
    decision_card_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    execution_scope: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'automation'"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    # Phase1 columns
    request_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        server_default=text("'created'"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
